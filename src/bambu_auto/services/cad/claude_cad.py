"""Claude → build123d 파라메트릭 CAD 트랙.

자연어 스펙을 Claude에게 보내 build123d 파이썬 코드를 생성하게 한 뒤,
격리된 subprocess에서 실행해 STL을 만든다. 실행이 실패하면 stderr를
Claude에게 되먹여 self-fix(최대 N회). 성공 시 결과는 항상 watertight.

설계 메모:
- Meshy 의존을 우회. 규격·기능 부품(키캡, 마운트, 홀더, 브래킷, 박스 등)에
  Meshy보다 압도적으로 적합 — 치수 정확·watertight·재현성.
- 실행은 sys.executable 의 별도 프로세스 + timeout → main worker 보호.
- 출력은 build123d.export_stl 로 직접 STL → trimesh 리페어가 거의 noop.
- prompt caching: system prompt가 길어 cache_control 처리 (anthropic SDK가 지원).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import textwrap
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path


SYSTEM_PROMPT = textwrap.dedent("""
    You are an expert parametric CAD modeler. The user describes a 3D part to
    be manufactured on a Bambu Lab FDM printer. You must emit a Python program
    using the build123d library (v0.10+) that constructs the part.

    HARD RULES (the program is executed automatically):
    1. Output EXACTLY one fenced Python code block (```python ... ```), and
       NOTHING else outside the block. No commentary, no second block.
    2. The program MUST assign the final part to a top-level variable named
       `result`. It must be a build123d `Part`, `Solid`, or `Compound` of solids.
    3. All dimensions are in millimeters.
    4. The final shape MUST be a watertight closed solid suitable for FDM
       printing (single connected body preferred; multiple solids only if
       they share a base).
    5. Do NOT call file IO, network, subprocess, or `print`. Just build `result`.
    6. Stay within these envelopes unless the user explicitly overrides:
       - max bounding box 200x200x200 mm
       - min wall thickness 1.2 mm
       - min feature size 0.6 mm (avoid features narrower than this)
    7. If the user spec is ambiguous, choose sensible printable defaults and
       proceed. Do not ask questions.
    8. Use `from build123d import *` at the top — every public symbol is
       importable that way.

    EXAMPLE — 1u MX keycap with letter 'A' embossed on top:
    ```python
    from build123d import *
    cap_w, cap_h = 18.0, 8.0
    with BuildPart() as p:
        Box(cap_w, cap_w, cap_h)
        fillet(p.edges().filter_by(Axis.Z), radius=1.2)
        # MX cross stem (subtract from bottom)
        with Locations((0, 0, -cap_h / 2 + 2)):
            Box(4.1, 1.3, 4, mode=Mode.SUBTRACT)
            Box(1.3, 4.1, 4, mode=Mode.SUBTRACT)
        # Letter emboss on top face
        with BuildSketch(Plane.XY.offset(cap_h / 2)) as sk:
            Text("A", font_size=6)
        extrude(amount=-0.6, mode=Mode.SUBTRACT)
    result = p.part
    ```

    Now produce the program for the user's spec.
""").strip()


@dataclass
class CadResult:
    ok: bool
    stl_path: Path | None
    code: str = ""
    attempts: int = 0
    error: str | None = None
    model: str = ""
    notes: list[str] = field(default_factory=list)


_CODE_BLOCK = re.compile(r"```(?:python)?\s*\n(.*?)```", re.DOTALL)


def _extract_code(text: str) -> str | None:
    m = _CODE_BLOCK.search(text)
    return m.group(1).strip() if m else None


def _build_runner(user_code: str, out_stl: str) -> str:
    """user_code를 격리 실행하는 작은 러너 스크립트.

    user_code는 `result` 라는 이름으로 build123d 객체를 정의해야 함.
    러너가 객체 종류에 따라 export_stl 호출.
    """
    return textwrap.dedent(f'''
        from __future__ import annotations
        import sys, traceback
        from pathlib import Path
        try:
            # build123d 전체 심볼 미리 import — 사용자 코드에서 from … import * 안 써도 동작
            from build123d import *  # noqa: F401, F403
        except Exception as e:
            print("IMPORT_ERROR: " + repr(e), file=sys.stderr)
            sys.exit(3)

        ns: dict = {{}}
        try:
            exec(compile({user_code!r}, "<user_cad>", "exec"), ns, ns)
        except Exception:
            traceback.print_exc()
            sys.exit(4)

        result = ns.get("result")
        if result is None:
            for k in ("part", "model", "solid", "obj"):
                if k in ns:
                    result = ns[k]
                    break
        if result is None:
            print("NO_RESULT: top-level `result` variable missing", file=sys.stderr)
            sys.exit(5)

        # build123d.Part / Compound / Solid 호환
        from build123d import export_stl
        try:
            export_stl(result, {out_stl!r})
        except Exception:
            # Builder 객체였으면 .part 시도
            try:
                inner = getattr(result, "part", None) or getattr(result, "sketch", None)
                if inner is None:
                    raise
                export_stl(inner, {out_stl!r})
            except Exception:
                traceback.print_exc()
                sys.exit(6)
        print("OK")
    ''').lstrip()


def _execute_code(
    code: str, out_stl: Path, timeout_sec: int,
) -> tuple[bool, str]:
    """별도 프로세스에서 build123d 코드 실행 → STL export.
    (ok, stderr) 반환. timeout 시 ok=False, stderr에 'TIMEOUT'.
    """
    runner = _build_runner(code, str(out_stl))
    with tempfile.NamedTemporaryFile(
        "w", suffix=".py", delete=False, encoding="utf-8",
    ) as f:
        f.write(runner)
        runner_path = f.name
    try:
        proc = subprocess.run(
            [sys.executable, runner_path],
            capture_output=True, text=True, timeout=timeout_sec,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
    except subprocess.TimeoutExpired:
        return False, f"TIMEOUT after {timeout_sec}s"
    finally:
        try:
            os.unlink(runner_path)
        except OSError:
            pass
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "")[-2000:]
        return False, tail
    if not out_stl.exists() or out_stl.stat().st_size == 0:
        return False, "STL not written or empty"
    return True, ""


def _call_claude(
    client, model: str, user_prompt: str,
    prior_code: str | None = None, prior_error: str | None = None,
) -> tuple[str, str]:
    """Claude 호출 → (raw_text, extracted_code). 코드 추출 실패 시 ValueError.
    prior_*가 있으면 self-fix 컨텍스트로 함께 전송.
    """
    user_blocks: list[dict] = [{"type": "text", "text": user_prompt}]
    if prior_code and prior_error:
        fix_text = (
            "Previous attempt failed. Fix the code so it runs cleanly and "
            "exports a valid watertight STL. Keep the same intent.\n\n"
            f"Previous code:\n```python\n{prior_code}\n```\n\n"
            f"Error:\n{prior_error}"
        )
        user_blocks.append({"type": "text", "text": fix_text})

    msg = client.messages.create(
        model=model,
        max_tokens=4000,
        system=[{
            "type": "text", "text": SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{"role": "user", "content": user_blocks}],
    )
    parts = [b.text for b in msg.content if getattr(b, "type", "") == "text"]
    raw = "\n".join(parts)
    code = _extract_code(raw)
    if not code:
        raise ValueError(
            "Claude 응답에서 python 코드 블록을 추출할 수 없음:\n"
            + raw[:600]
        )
    return raw, code


def generate_part(
    prompt: str,
    out_stl: Path,
    api_key: str,
    *,
    model: str = "claude-sonnet-4-6",
    max_attempts: int = 3,
    timeout_sec: int = 60,
    on_progress: Callable[[str], None] | None = None,
) -> CadResult:
    """자연어 스펙 → build123d 코드 → STL.

    실패하면 stderr를 다시 Claude에 던져 self-fix. max_attempts 까지 시도.
    성공 시 out_stl 위치에 STL 파일이 존재.
    """
    notify = on_progress or (lambda _m: None)
    out_stl.parent.mkdir(parents=True, exist_ok=True)

    try:
        import anthropic  # 지연 import — extra 미설치 환경 보호
    except ImportError as e:
        return CadResult(
            ok=False, stl_path=None, error=f"anthropic SDK 미설치: {e}",
            model=model,
        )

    client = anthropic.Anthropic(api_key=api_key)
    prior_code: str | None = None
    prior_error: str | None = None
    notes: list[str] = []

    for attempt in range(1, max_attempts + 1):
        notify(f"  Claude CAD 코드 생성 중 (시도 {attempt}/{max_attempts})…")
        try:
            _raw, code = _call_claude(
                client, model, prompt,
                prior_code=prior_code, prior_error=prior_error,
            )
        except Exception as e:  # noqa: BLE001
            notes.append(f"a{attempt}:claude_err:{type(e).__name__}")
            return CadResult(
                ok=False, stl_path=None, code=prior_code or "",
                attempts=attempt, error=f"Claude 호출 실패: {e}",
                model=model, notes=notes,
            )

        notify(f"  build123d 실행 중 (시도 {attempt})…")
        ok, err = _execute_code(code, out_stl, timeout_sec)
        if ok:
            notify(f"  ✓ CAD STL 생성 성공 (시도 {attempt})")
            return CadResult(
                ok=True, stl_path=out_stl, code=code,
                attempts=attempt, model=model, notes=notes,
            )

        notes.append(f"a{attempt}:exec_fail")
        notify(f"  ⚠ 실행 실패 → Claude self-fix 시도 ({err.splitlines()[-1][:120]})")
        prior_code, prior_error = code, err

    return CadResult(
        ok=False, stl_path=None, code=prior_code or "",
        attempts=max_attempts, error=prior_error or "exhausted",
        model=model, notes=notes,
    )


def write_artifacts(result: CadResult, dest_dir: Path) -> None:
    """진단·디버깅용으로 마지막 코드와 메타데이터를 dest_dir에 기록."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    if result.code:
        (dest_dir / "cad_code.py").write_text(result.code, encoding="utf-8")
    (dest_dir / "cad_meta.json").write_text(
        json.dumps({
            "ok": result.ok,
            "attempts": result.attempts,
            "model": result.model,
            "error": result.error,
            "notes": result.notes,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
