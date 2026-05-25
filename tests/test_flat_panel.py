from pathlib import Path

import pytest

trimesh = pytest.importorskip("trimesh")
pytest.importorskip("cv2")
from PIL import Image, ImageDraw

from bambu_auto.services.mesh.flat_panel import make_flat_panel


def _char(p: Path) -> None:
    img = Image.new("RGBA", (300, 300), (0, 0, 0, 0))
    dr = ImageDraw.Draw(img)
    dr.ellipse([40, 40, 260, 260], fill=(255, 200, 150, 255))
    dr.ellipse([100, 120, 130, 150], fill=(20, 20, 20, 255))
    dr.ellipse([170, 120, 200, 150], fill=(20, 20, 20, 255))
    img.save(p)


def test_flat_panel_size_and_thickness(tmp_path: Path) -> None:
    src = tmp_path / "c.png"
    out = tmp_path / "flat.stl"
    _char(src)
    r = make_flat_panel(src, out, size_mm=50, thickness_mm=3.5)
    assert r["ok"] is True
    m = trimesh.load(out, force="mesh")
    # 최대 치수 ≈ 50mm 이하(실루엣 비율), 두께 정확히 3.5mm
    assert max(m.extents[0], m.extents[1]) <= 50.5
    assert abs(m.extents[2] - 3.5) < 0.01


def test_flat_panel_empty_image_fails(tmp_path: Path) -> None:
    src = tmp_path / "blank.png"
    Image.new("RGBA", (100, 100), (0, 0, 0, 0)).save(src)  # 완전 투명
    r = make_flat_panel(src, tmp_path / "o.stl")
    assert r["ok"] is False
