import zipfile
from pathlib import Path

from bambu_auto.services.slicer.postprocess import compute_total_z, inject_pause


def _build_3mf(p: Path, gcode_text: str) -> None:
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("Metadata/plate_1.gcode", gcode_text)
        z.writestr("3D/3dmodel.model", b"<model/>")


def test_inject_pause_at_z_height(tmp_path: Path) -> None:
    g = (
        "; start\n"
        "G1 Z0.2 F600\n"
        "; Z_HEIGHT: 0.2\n"
        "G1 X10 Y10 E1\n"
        "; Z_HEIGHT: 5.4\n"
        "G1 X20 Y20 E2\n"
    )
    p = tmp_path / "test.gcode.3mf"
    _build_3mf(p, g)
    res = inject_pause(p, 5.0)
    assert res["injected"] is True
    with zipfile.ZipFile(p) as z:
        out = z.read("Metadata/plate_1.gcode").decode()
    assert "M400 U1" in out
    # 일시정지가 Z=5.4 마커 '앞'에 있어야 함
    pause_pos = out.index("M400 U1")
    z5_pos = out.index("; Z_HEIGHT: 5.4")
    assert pause_pos < z5_pos
    # Z=0.2 마커 다음에 위치 (모델 인쇄 도중)
    assert out.index("; Z_HEIGHT: 0.2") < pause_pos


def test_no_injection_if_target_too_high(tmp_path: Path) -> None:
    g = "G1 Z0.2\n; Z_HEIGHT: 0.2\nG1 X1 Y1\n"
    p = tmp_path / "test.gcode.3mf"
    _build_3mf(p, g)
    res = inject_pause(p, 100.0)
    assert res["injected"] is False


def test_compute_total_z(tmp_path: Path) -> None:
    g = "; Z_HEIGHT: 0.2\nG1 Z0.2\n; Z_HEIGHT: 5.4\nG1 Z5.4\n; Z_HEIGHT: 12.0\n"
    p = tmp_path / "test.gcode.3mf"
    _build_3mf(p, g)
    assert abs(compute_total_z(p) - 12.0) < 0.001
