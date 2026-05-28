import json
from pathlib import Path

import numpy as np
import pytest

trimesh = pytest.importorskip("trimesh")

from bambu_auto.services.mesh.keycap import (
    make_keycap,
    make_keycap_multicolor,
)


def test_make_keycap_produces_valid_mesh(tmp_path: Path) -> None:
    src = tmp_path / "in.stl"
    out = tmp_path / "cap.stl"
    # 토퍼로 쓸 작은 구
    trimesh.creation.icosphere(subdivisions=2, radius=10).export(src)
    r = make_keycap(src, out, top_mm=18, height_mm=9)
    assert r["ok"] is True
    m = trimesh.load(out, force="mesh")
    # 키캡 외곽이 18mm 안팎, 높이는 본체+토퍼로 9mm 초과
    assert m.extents[0] <= 19.5
    assert m.extents[2] > 9.0


def _two_color_glb(path: Path) -> None:
    """정점색이 2색(위=빨강, 아래=파랑)인 토퍼 GLB."""
    sph = trimesh.creation.icosphere(subdivisions=3, radius=10)
    top = sph.vertices[:, 2] >= 0
    cols = np.zeros((len(sph.vertices), 4), dtype=np.uint8)
    cols[:, 3] = 255
    cols[top] = [220, 30, 30, 255]
    cols[~top] = [30, 30, 220, 255]
    sph.visual = trimesh.visual.ColorVisuals(vertex_colors=cols)
    sph.export(path)


def test_keycap_multicolor_emits_bambu_3mf(tmp_path: Path) -> None:
    glb = tmp_path / "topper.glb"
    _two_color_glb(glb)
    ddir = tmp_path / "download"
    r = make_keycap_multicolor(glb, ddir, "abcd1234", n_colors=4)

    assert r["ok"] is True, r
    # 최소 2색은 잡혀야 함
    assert len(r["colors"]) >= 2
    assert (ddir / "abcd1234.bambu.3mf").exists()
    assert (ddir / "abcd1234.color.3mf").exists()
    assert (ddir / "abcd1234_c1.stl").exists()
    assert (ddir / "abcd1234_c2.stl").exists()

    pal = json.loads((ddir / "abcd1234.palette.json").read_text())
    assert len(pal["filament_map"]) == len(r["colors"])
    assert pal["filament_map"][0]["extruder"] == 1


def test_keycap_multicolor_skips_when_no_color(tmp_path: Path) -> None:
    src = tmp_path / "plain.stl"
    trimesh.creation.icosphere(subdivisions=2, radius=10).export(src)
    r = make_keycap_multicolor(src, tmp_path / "dl", "deadbeef")
    assert r["ok"] is False
    assert r["method"] == "no_color"
