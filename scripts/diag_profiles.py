"""생성된 슬라이서 프로파일의 호환성 관련 키 덤프 (진단용).

'process not compatible with printer' 원인 파악:
machine identity vs process/filament 호환 조건을 눈으로 대조.

사용: uv run python scripts/diag_profiles.py [profile_name]
기본: a1_pla_standard
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

OUT_DIR = Path("config/slicer_profiles")

MACHINE_KEYS = [
    "name", "from", "type", "printer_model", "printer_variant",
    "nozzle_diameter", "printer_settings_id", "inherits", "printer_technology",
]
PROCESS_KEYS = [
    "name", "from", "type", "compatible_printers", "compatible_printers_condition",
    "print_settings_id", "inherits", "printer_model",
]
FILAMENT_KEYS = [
    "name", "from", "type", "compatible_printers", "compatible_printers_condition",
    "compatible_prints", "compatible_prints_condition", "filament_id", "inherits",
]


def dump(path: Path, keys: list[str]) -> None:
    print(f"\n=== {path.name} ===")
    if not path.exists():
        print("  (파일 없음)")
        return
    data = json.loads(path.read_text())
    print(f"  총 키 {len(data)}개")
    for k in keys:
        if k in data:
            v = data[k]
            sv = json.dumps(v, ensure_ascii=False)
            if len(sv) > 200:
                sv = sv[:200] + "…"
            print(f"  {k}: {sv}")
        else:
            print(f"  {k}: <없음>")


def main() -> int:
    name = sys.argv[1] if len(sys.argv) > 1 else "a1_pla_standard"
    dump(OUT_DIR / f"{name}.machine.json", MACHINE_KEYS)
    dump(OUT_DIR / f"{name}.process.json", PROCESS_KEYS)
    dump(OUT_DIR / f"{name}.filament.json", FILAMENT_KEYS)
    return 0


if __name__ == "__main__":
    sys.exit(main())
