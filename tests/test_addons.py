from pathlib import Path

import pytest

trimesh = pytest.importorskip("trimesh")

from bambu_auto.services.mesh.addons import add_base, add_keychain_loop


def _box(p: Path) -> None:
    trimesh.creation.box((30, 30, 40)).export(p)


def test_keychain_loop_adds_geometry(tmp_path: Path) -> None:
    src = tmp_path / "in.stl"
    out = tmp_path / "k.stl"
    _box(src)
    base_faces = len(trimesh.load(src, force="mesh").faces)
    assert add_keychain_loop(src, out) is True
    assert out.exists()
    assert len(trimesh.load(out, force="mesh").faces) > base_faces


def test_base_adds_geometry(tmp_path: Path) -> None:
    src = tmp_path / "in.stl"
    out = tmp_path / "s.stl"
    _box(src)
    assert add_base(src, out) is True
    m = trimesh.load(out, force="mesh")
    # 받침으로 바닥 면적(둘레)이 원본보다 커짐
    assert m.extents[2] > 39  # 높이 = 원본40 + 받침 일부
