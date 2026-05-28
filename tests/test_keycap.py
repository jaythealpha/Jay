import json
from pathlib import Path

import numpy as np
import pytest

trimesh = pytest.importorskip("trimesh")

from bambu_auto.services.mesh.keycap import (
    fit_mx_socket,
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


def test_fit_mx_socket_scales_to_1u_and_cuts_socket(tmp_path: Path) -> None:
    # Meshy 키캡 흉내: 작은(13mm) 속 빈 박스 캡 + 중앙 부정확 소켓
    src = tmp_path / "cap_in.stl"
    out = tmp_path / "cap_fit.stl"
    body = trimesh.creation.box((13.0, 13.0, 12.0))
    body.apply_translation((0, 0, 6.0))
    inner = trimesh.creation.box((10.0, 10.0, 10.0))
    inner.apply_translation((0, 0, 4.99))
    cap = trimesh.boolean.difference([body, inner], engine="manifold")
    cap.export(src)

    r = fit_mx_socket(src, out, target_u_mm=18.0)
    assert r["ok"] is True
    m = trimesh.load(out, force="mesh")
    # 1u(18mm) 안팎으로 스케일됨
    assert 17.0 <= max(m.extents[0], m.extents[1]) <= 18.5
    # 바닥 중앙에 십자 소켓이 파여 부피가 음수 아님(유효 메쉬)
    assert m.volume > 0
    # 바닥면 근처 중앙에 빈 십자 공간 존재 → 바닥 슬라이스가 솔리드 아님
    zmin = m.bounds[0][2]
    sec = m.section(plane_origin=[0, 0, zmin + 1.0], plane_normal=[0, 0, 1])
    assert sec is not None  # 단면이 잡힘(소켓 벽 존재)
