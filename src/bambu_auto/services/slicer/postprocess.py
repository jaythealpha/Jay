"""슬라이싱된 .gcode.3mf 후처리 — M400 U1로 일시정지 삽입.

자석/NFC 등을 모델 내부에 삽입하려면 출력 중간에 멈춰야 함.
Bambu(P1S/A1/P2S)는 펌웨어 일시정지 명령 `M400 U1` 지원.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

PAUSE_CMD = "M400 U1"
_ZH = re.compile(r"^; Z_HEIGHT:\s*([\d.]+)")
_MOVE_Z = re.compile(r"^\s*G[01].*\sZ([\d.]+)")


def inject_pause(gcode_3mf: Path, z_mm: float) -> dict:
    """gcode.3mf 안의 G-code에 z_mm 도달 시점 직전에 M400 U1 삽입.

    반환: {"injected": bool, "at_line": int|None, "marker": str}.
    """
    if z_mm <= 0:
        return {"injected": False, "reason": "z_mm<=0"}
    gcode_3mf = Path(gcode_3mf)
    with zipfile.ZipFile(gcode_3mf, "r") as z:
        names = z.namelist()
        target = next((n for n in names if n.endswith(".gcode")), None)
        if not target:
            return {"injected": False, "reason": "gcode not found in 3mf"}
        blobs = {n: z.read(n) for n in names}

    text = blobs[target].decode("utf-8", "ignore")
    lines = text.split("\n")
    insert_at = _find_insert_line(lines, z_mm)
    if insert_at is None:
        return {"injected": False, "reason": f"no Z>={z_mm}mm marker"}

    new_lines = (
        lines[:insert_at]
        + [
            f"; --- bambu_auto pause @ Z={z_mm}mm (insert magnet/NFC) ---",
            PAUSE_CMD,
            "; --- resume ---",
        ]
        + lines[insert_at:]
    )
    blobs[target] = "\n".join(new_lines).encode("utf-8")

    tmp = gcode_3mf.with_suffix(gcode_3mf.suffix + ".tmp")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for n, data in blobs.items():
            z.writestr(n, data)
    tmp.replace(gcode_3mf)
    return {"injected": True, "at_line": insert_at, "marker": PAUSE_CMD}


def _find_insert_line(lines: list[str], z_mm: float) -> int | None:
    """우선 ; Z_HEIGHT: 마커, 실패 시 첫 G1 Zh (모델 인쇄 시작 후) 사용."""
    for i, ln in enumerate(lines):
        m = _ZH.match(ln)
        if m and float(m.group(1)) >= z_mm:
            return i
    saw_layer = False
    for i, ln in enumerate(lines):
        if not saw_layer and ("; LAYER" in ln or "; layer num" in ln):
            saw_layer = True
            continue
        if saw_layer:
            mv = _MOVE_Z.match(ln)
            if mv and float(mv.group(1)) >= z_mm:
                return i
    return None


def compute_total_z(gcode_3mf: Path) -> float:
    """gcode.3mf의 최대 Z (모델 총 높이, mm). 마커 우선 → 이동명령 fallback."""
    with zipfile.ZipFile(gcode_3mf, "r") as z:
        name = next((n for n in z.namelist() if n.endswith(".gcode")), None)
        if not name:
            return 0.0
        text = z.read(name).decode("utf-8", "ignore")
    max_z = 0.0
    for ln in text.split("\n"):
        m = _ZH.match(ln)
        if m:
            max_z = max(max_z, float(m.group(1)))
            continue
        mv = _MOVE_Z.match(ln)
        if mv:
            max_z = max(max_z, float(mv.group(1)))
    return max_z
