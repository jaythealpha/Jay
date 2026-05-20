from pathlib import Path

import pytest

trimesh = pytest.importorskip("trimesh")
pytest.importorskip("cv2")

from bambu_auto.services.mesh.branding import ICON_LABELS, add_bottom_branding


def _box(p: Path) -> None:
    trimesh.creation.box((50, 50, 8)).export(p)


def test_text_deboss_changes_geometry(tmp_path: Path) -> None:
    src = tmp_path / "in.stl"
    out = tmp_path / "out.stl"
    _box(src)
    base_faces = len(trimesh.load(src, force="mesh").faces)
    r = add_bottom_branding(src, out, content="YOGIBO",
                            size_mm=30, depth_mm=0.6)
    assert r["ok"] is True
    m = trimesh.load(out, force="mesh")
    assert len(m.faces) > base_faces  # 텍스트 디보스로 면 추가


def test_wifi_icon_label_present_and_succeeds(tmp_path: Path) -> None:
    assert "wifi" in ICON_LABELS
    src = tmp_path / "in.stl"
    out = tmp_path / "out.stl"
    _box(src)
    r = add_bottom_branding(src, out, content="wifi",
                            size_mm=20, depth_mm=0.5)
    assert r["ok"] is True
