"""OrcaSlicer CLI용 얇은 사용자 프리셋 생성 (시스템 프리셋 상속).

전략 전환: 시스템 프로파일을 평탄화하면 OrcaSlicer의 호환성 그래프
(inherits 기반 process↔printer 매칭)가 깨져 'process not compatible'
발생. 대신 OrcaSlicer가 의도한 방식 그대로 — from:User + inherits로
번들 시스템 프리셋을 참조하는 얇은 프리셋을 만든다. OrcaSlicer CLI가
번들 시스템 프로파일을 자동 해소하므로 호환성이 보존된다.

사용: uv run python scripts/build_profiles.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROFILES_ROOT = Path("/Applications/OrcaSlicer.app/Contents/Resources/profiles")
VENDOR = "BBL"
OUT_DIR = Path("config/slicer_profiles")

# (출력 프로파일명, machine 시스템 프리셋명, process 시스템 프리셋명,
#  filament 시스템 프리셋명)
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


def system_preset_exists(category: str, name: str) -> bool:
    """번들 시스템 프리셋이 실제 존재하는지 (name 필드 기준) 확인."""
    cat_dir = PROFILES_ROOT / VENDOR / category
    if not cat_dir.exists():
        return False
    for p in cat_dir.glob("*.json"):
        try:
            if json.loads(p.read_text()).get("name") == name:
                return True
        except Exception:  # noqa: BLE001
            continue
    return False


def thin_preset(kind: str, name: str, inherits: str,
                machine_names: list[str] | None = None) -> dict:
    """시스템 프리셋을 상속하는 최소 사용자 프리셋.

    process/filament는 명시적 compatible_printers 리스트를 추가.
    CLI 호환성 판정이 process.compatible_printers에 프린터명(또는
    그 inherits)이 있는지로 동작하는 것으로 보임 → 우리 machine
    프리셋명 + 시스템 machine명 둘 다 넣어 어느 쪽이든 매칭.
    """
    preset = {
        "type": kind,
        "name": name,
        "from": "User",
        "is_custom_defined": "1",
        "setting_id": "",
        "inherits": inherits,
        "version": "2.3.0.0",
    }
    if kind == "machine":
        # 시스템 A1/P2S 프리셋은 relative E 모드 → CLI 검증이 layer_gcode에
        # G92 E0 요구. 절대 E로 오버라이드하면 요구 자체가 사라지고
        # Bambu 펌웨어는 절대 E로 정상 출력. (belt&suspenders로 layer
        # 변경 시 G92 E0도 추가해 어느 검증 경로든 통과)
        preset["use_relative_e_distances"] = "0"
        preset["before_layer_change_gcode"] = "G92 E0\n"
    if kind in ("process", "filament") and machine_names:
        preset["compatible_printers"] = machine_names
        preset["compatible_printers_condition"] = ""
    return preset


def main() -> int:
    if not PROFILES_ROOT.exists():
        print(f"OrcaSlicer 프로파일 폴더 없음: {PROFILES_ROOT}")
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    failed = False

    for out_name, m, pr, f in TARGETS:
        print(f"\n[{out_name}]")
        specs = [
            ("machine", "machine", m),
            ("process", "process", pr),
            ("filament", "filament", f),
        ]
        # process/filament가 호환 매칭할 machine 후보: 우리 프리셋명 + 시스템명
        machine_names = [f"{out_name}_machine", m]
        for kind, cat, sys_name in specs:
            ok = system_preset_exists(cat, sys_name)
            mark = "✓" if ok else "✗"
            print(f"  {mark} 시스템 {kind} 프리셋: {sys_name!r} "
                  f"{'존재' if ok else '없음(이름 확인 필요)'}")
            if not ok:
                failed = True
                continue
            preset = thin_preset(kind, f"{out_name}_{kind}", sys_name,
                                 machine_names=machine_names)
            out = OUT_DIR / f"{out_name}.{kind}.json"
            out.write_text(json.dumps(preset, ensure_ascii=False, indent=2))
            extra = "" if kind == "machine" else f", compatible={machine_names}"
            print(f"    → {out}  (inherits {sys_name!r}{extra})")

    if failed:
        print("\n일부 시스템 프리셋명을 못 찾음. scripts/inspect_orca.py 로 "
              "정확한 name을 확인 후 TARGETS 수정 필요.")
        return 1
    print("\n완료. 다음: bambu-auto submit ... --run 으로 슬라이싱 검증")
    return 0


if __name__ == "__main__":
    sys.exit(main())
