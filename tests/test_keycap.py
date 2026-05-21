from pathlib import Path

import pytest

trimesh = pytest.importorskip("trimesh")

from bambu_auto.services.mesh.keycap import make_keycap


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
