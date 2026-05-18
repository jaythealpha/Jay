"""OrcaSlicer 내장 BBL 프로파일 구조 스캔.

목적: 사용자 맥의 OrcaSlicer 버전에 어떤 P2S/A1 machine·process·filament
프로파일이 있는지 파악 → flatten 로직을 정확히 작성하기 위함.

사용: uv run python scripts/inspect_orca.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

MAC_CANDIDATES = [
    "/Applications/OrcaSlicer.app/Contents/Resources/profiles",
    str(Path.home() / "Library/Application Support/OrcaSlicer/system"),
]


def find_profiles_root() -> Path | None:
    for c in MAC_CANDIDATES:
        p = Path(c)
        if p.exists():
            return p
    return None


def show(title: str, items: list[str]) -> None:
    print(f"\n=== {title} ({len(items)}) ===")
    for i in sorted(items):
        print(f"  {i}")


def main() -> int:
    root = find_profiles_root()
    if not root:
        print("OrcaSlicer 프로파일 폴더를 못 찾음. 후보:")
        for c in MAC_CANDIDATES:
            print(f"  {c}")
        print("OrcaSlicer Help → Show Configuration Folder 경로를 알려주세요.")
        return 1

    print(f"PROFILES_ROOT={root}")
    bbl = root / "BBL"
    if not bbl.exists():
        # 일부 버전은 root 바로 아래 vendor 폴더
        print(f"BBL 폴더 없음. root 하위: {[p.name for p in root.iterdir()][:20]}")
        return 1

    for sub in ("machine", "process", "filament"):
        d = bbl / sub
        if not d.exists():
            print(f"\n[{sub}] 폴더 없음: {d}")
            continue
        names = [p.name for p in d.glob("*.json")]
        # 관심 키워드만 필터해서 노이즈 감소
        kw = {
            "machine": ["P2S", "P1S", "A1", "X1C"],
            "process": ["0.20", "Standard", "P2S", "P1S", "A1"],
            "filament": ["PLA Basic", "PLA @", "Generic PLA", "P2S", "A1"],
        }[sub]
        hits = [n for n in names if any(k in n for k in kw)]
        show(f"{sub}: 키워드 매칭", hits)
        print(f"  (전체 {len(names)}개 중 {len(hits)}개 표시)")

    # machine 프로파일 하나의 inherits 체인 샘플
    mdir = bbl / "machine"
    sample = None
    for pref in ("P2S", "P1S", "A1"):
        cands = list(mdir.glob(f"*{pref}*0.4*.json")) or list(mdir.glob(f"*{pref}*.json"))
        if cands:
            sample = cands[0]
            break
    if sample:
        print(f"\n=== machine 샘플: {sample.name} ===")
        data = json.loads(sample.read_text())
        for key in ("name", "inherits", "from", "type", "printer_model",
                    "nozzle_diameter", "printable_area", "printable_height"):
            if key in data:
                print(f"  {key}: {data[key]}")
        print(f"  (총 키 {len(data)}개)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
