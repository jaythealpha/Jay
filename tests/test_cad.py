"""CAD 트랙(Claude → build123d) 핵심 동작 검증.

- _extract_code: ```python … ``` 추출
- _execute_code: 정상 코드 → STL, 잘못된 코드 → fail+stderr, 결과 변수 누락 → fail
- generate_part: Claude SDK를 mock으로 주입 — 첫 시도 실패 → self-fix 성공 확인
- CadSpecAdapter: params를 prompt에 잘 합치고 안정적 input_hash
- Pipeline 통합: kind=='cad' 분기에서 Meshy 우회
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
import trimesh

from bambu_auto.adapters.sources.cad_spec import CadSpecAdapter
from bambu_auto.services.cad import claude_cad


# ---------- 코드 추출 ----------

def test_extract_code_python_block() -> None:
    raw = "blah\n```python\nresult = 42\n```\ntail"
    assert claude_cad._extract_code(raw) == "result = 42"


def test_extract_code_unlabeled_block() -> None:
    raw = "```\nresult = 1\n```"
    assert claude_cad._extract_code(raw) == "result = 1"


def test_extract_code_none() -> None:
    assert claude_cad._extract_code("no code here") is None


# ---------- 코드 실행 ----------

def test_execute_code_valid_produces_watertight_stl(tmp_path: Path) -> None:
    code = (
        "from build123d import *\n"
        "with BuildPart() as p:\n"
        "    Box(15, 15, 5)\n"
        "result = p.part\n"
    )
    out = tmp_path / "x.stl"
    ok, err = claude_cad._execute_code(code, out, timeout_sec=30)
    assert ok, err
    m = trimesh.load(out)
    assert m.is_watertight
    assert abs(m.volume - 15 * 15 * 5) < 1.0


def test_execute_code_syntax_error_returns_stderr(tmp_path: Path) -> None:
    ok, err = claude_cad._execute_code(
        "result = (\n",  # 의도적 syntax error
        tmp_path / "x.stl", timeout_sec=15,
    )
    assert not ok
    assert err  # stderr 비어있지 않음


def test_execute_code_missing_result_var_fails(tmp_path: Path) -> None:
    ok, err = claude_cad._execute_code(
        "x = 1\n",  # result 변수 없음
        tmp_path / "x.stl", timeout_sec=15,
    )
    assert not ok
    assert "NO_RESULT" in err or "missing" in err.lower()


# ---------- generate_part (Claude mock) ----------

def _make_mock_anthropic(code_sequence: list[str]):
    """messages.create를 호출할 때마다 code_sequence에서 하나씩 꺼내 응답."""
    calls = {"n": 0}

    def fake_create(**kw):
        i = calls["n"]
        calls["n"] += 1
        code = code_sequence[min(i, len(code_sequence) - 1)]
        msg = MagicMock()
        block = MagicMock()
        block.type = "text"
        block.text = f"```python\n{code}\n```"
        msg.content = [block]
        return msg

    client = MagicMock()
    client.messages.create.side_effect = fake_create
    return client, calls


def test_generate_part_first_try_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    code = (
        "from build123d import *\n"
        "with BuildPart() as p:\n    Box(10, 10, 10)\n"
        "result = p.part\n"
    )
    client, calls = _make_mock_anthropic([code])
    fake_anthropic = MagicMock()
    fake_anthropic.Anthropic.return_value = client
    monkeypatch.setitem(__import__("sys").modules, "anthropic", fake_anthropic)

    out = tmp_path / "cad.stl"
    r = claude_cad.generate_part("test box", out, api_key="sk-fake", max_attempts=3)
    assert r.ok, r.error
    assert r.attempts == 1
    assert r.stl_path == out
    assert out.exists()
    assert calls["n"] == 1  # self-fix 호출 없음


def test_generate_part_self_fix_on_second_try(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    bad = "result = undefined_symbol\n"   # NameError
    good = (
        "from build123d import *\n"
        "with BuildPart() as p:\n    Box(8, 8, 8)\n"
        "result = p.part\n"
    )
    client, calls = _make_mock_anthropic([bad, good])
    fake_anthropic = MagicMock()
    fake_anthropic.Anthropic.return_value = client
    monkeypatch.setitem(__import__("sys").modules, "anthropic", fake_anthropic)

    out = tmp_path / "cad.stl"
    r = claude_cad.generate_part("test", out, api_key="sk-fake", max_attempts=3)
    assert r.ok, r.error
    assert r.attempts == 2
    assert calls["n"] == 2


def test_generate_part_exhausts_attempts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    bad = "result = undefined_symbol\n"
    client, calls = _make_mock_anthropic([bad])
    fake_anthropic = MagicMock()
    fake_anthropic.Anthropic.return_value = client
    monkeypatch.setitem(__import__("sys").modules, "anthropic", fake_anthropic)

    out = tmp_path / "cad.stl"
    r = claude_cad.generate_part("test", out, api_key="sk-fake", max_attempts=2)
    assert not r.ok
    assert r.attempts == 2
    assert calls["n"] == 2
    assert r.error  # 마지막 stderr


# ---------- CadSpecAdapter ----------

def test_cad_adapter_compose_with_params(tmp_path: Path) -> None:
    a = CadSpecAdapter("키캡 1u", params={"cap_mm": 18, "letter": "A"})
    ps = a.prepare(tmp_path)
    assert ps.kind == "cad"
    assert ps.prompt is not None and "cap_mm = 18" in ps.prompt
    assert ps.prompt and "letter = A" in ps.prompt
    assert ps.cad_params == {"cap_mm": 18, "letter": "A"}
    assert len(ps.input_hash) == 16


def test_cad_adapter_empty_prompt_raises() -> None:
    with pytest.raises(ValueError):
        CadSpecAdapter("   ")


def test_cad_adapter_hash_stable(tmp_path: Path) -> None:
    h1 = CadSpecAdapter("box", params={"x": 1}).prepare(tmp_path / "a").input_hash
    h2 = CadSpecAdapter("box", params={"x": 1}).prepare(tmp_path / "b").input_hash
    assert h1 == h2
    h3 = CadSpecAdapter("box", params={"x": 2}).prepare(tmp_path / "c").input_hash
    assert h1 != h3
