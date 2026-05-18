"""OrcaSlicer 시스템 프로파일을 평탄화(flatten)해 CLI용 독립 JSON 생성.

OrcaSlicer 시스템 프로파일은 "inherits" 상속 체인 + "from":"system"
메타데이터가 있어 CLI --load-settings로 직접 로드 시 거부됨.
이 스크립트가 상속을 해소해 self-contained JSON 3종(machine/process/
filament)을 config/slicer_profiles/ 에 생성.

사용: uv run python scripts/build_profiles.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROFILES_ROOT = Path("/Applications/OrcaSlicer.app/Contents/Resources/profiles")
VENDOR = "BBL"
OUT_DIR = Path("config/slicer_profiles")

# (출력 프로파일명, machine 파일 stem, process 파일 stem, filament 파일 stem)
TARGETS = [
    (
        "p2s_pla_standard",
        "Bambu Lab P2S 0.4 nozzle",
        "0.20mm Standard @BBL P2S",
        "Bambu PLA Basic @BBL P2S",
    ),
    (
        "a1_pla_standard",
        "Bambu Lab A1 0.4 nozzle",
        "0.20mm Standard @BBL A1",
        "Bambu PLA Basic @BBL A1",
    ),
]

# 평탄화 후 제거할 메타 키 (CLI 로드 시 방해)
# 평탄화 후 제거할 메타 키. inherits는 평탄화로 불필요, instantiation은
# 추상 프로파일 표식이라 제거. 'from'은 제거하면 OrcaSlicer가 빈 값으로
# 읽어 'from  unsupported' 거부 → 삭제 대신 'User'로 강제 설정(아래 finalize).
STRIP_KEYS = {"inherits", "instantiation"}

# 평탄화 결과에 강제 설정할 키 (CLI 로드 가능한 사용자 프리셋으로 위장)
FORCE_KEYS = {"from": "User", "is_custom_defined": "1"}


def build_name_index(category_dir: Path) -> dict[str, Path]:
    """category 디렉토리의 모든 json을 name → path 로 색인.
    inherits는 파일명이 아니라 프로파일 'name'을 참조하므로 필요."""
    index: dict[str, Path] = {}
    for p in category_dir.glob("*.json"):
        try:
            data = json.loads(p.read_text())
        except Exception:  # noqa: BLE001
            continue
        nm = data.get("name")
        if nm:
            index[nm] = p
        index.setdefault(p.stem, p)  # 파일명 stem으로도 접근 가능하게
    return index


def deep_merge(base: dict, child: dict) -> dict:
    out = dict(base)
    for k, v in child.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def flatten(name: str, index: dict[str, Path], seen: set[str] | None = None) -> dict:
    """name 프로파일을 inherits 체인 해소해 평탄화."""
    seen = seen or set()
    if name in seen:
        raise RuntimeError(f"inherits 순환 감지: {name}")
    seen.add(name)

    path = index.get(name)
    if not path:
        raise FileNotFoundError(f"프로파일을 찾을 수 없음: {name!r}")
    data = json.loads(path.read_text())

    parent = data.get("inherits")
    if parent:
        base = flatten(parent, index, seen)
        merged = deep_merge(base, data)
    else:
        merged = data
    return merged


def clean(data: dict, kind: str, machine_name: str = "") -> dict:
    out = {k: v for k, v in data.items() if k not in STRIP_KEYS}
    out.update(FORCE_KEYS)   # from=User 등 CLI 로드 호환 메타 강제
    if kind in ("process", "filament"):
        # debug5 로그: OrcaSlicer는 compatible_printers_condition을 평가해
        # 호환 결정. 빈문자열/제거 둘 다 'compatible 0'. from 때와 동일
        # 패턴 — 키가 존재하며 '유효한 참 조건식'이어야 함.
        # nozzle_diameter[0]>0 = 모든 프린터에 참인 정식 Bambu 문법.
        out["compatible_printers_condition"] = "nozzle_diameter[0]>0"
        out["compatible_printers"] = [machine_name] if machine_name else []
        if kind == "filament":
            out["compatible_prints_condition"] = "layer_height>0"
            out["compatible_prints"] = []
    return out


def main() -> int:
    if not PROFILES_ROOT.exists():
        print(f"OrcaSlicer 프로파일 폴더 없음: {PROFILES_ROOT}")
        print("scripts/inspect_orca.py 로 경로 먼저 확인하세요.")
        return 1

    bbl = PROFILES_ROOT / VENDOR
    idx = {
        "machine": build_name_index(bbl / "machine"),
        "process": build_name_index(bbl / "process"),
        "filament": build_name_index(bbl / "filament"),
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for out_name, m, pr, f in TARGETS:
        print(f"\n[{out_name}]")
        try:
            machine = clean(flatten(m, idx["machine"]), "machine")
            mname = machine.get("name", m)
            process = clean(flatten(pr, idx["process"]), "process", mname)
            filament = clean(flatten(f, idx["filament"]), "filament", mname)
        except Exception as e:  # noqa: BLE001
            print(f"  ✗ 실패: {e}")
            return 1

        for kind, payload in (("machine", machine), ("process", process),
                              ("filament", filament)):
            out = OUT_DIR / f"{out_name}.{kind}.json"
            out.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
            # 재읽기 검증: 금지 키가 정말 사라졌는지 확인
            reread = json.loads(out.read_text())
            leftover = sorted(set(reread) & STRIP_KEYS)
            status = "✓" if not leftover else "✗"
            extra = f"  ⚠ 잔존 금지키: {leftover}" if leftover else ""
            print(f"  {status} {out}  ({len(payload)} keys){extra}")
            if leftover:
                print(f"     → clean 로직 버그. 키: {leftover}")
                return 1

    print("\n완료. 다음: bambu-auto submit ... --run 으로 슬라이싱 검증")
    return 0


if __name__ == "__main__":
    sys.exit(main())
