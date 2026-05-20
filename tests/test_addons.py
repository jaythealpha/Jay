from pathlib import Path

import pytest

trimesh = pytest.importorskip("trimesh")

from bambu_auto.services.mesh.addons import (
    add_base,
    add_keychain_loop,
    add_magnet_cavity,
    add_nfc_cavity,
)


def _box(p: Path) -> None:
    trimesh.creation.box((30, 30, 40)).export(p)


def test_keychain_loop_adds_geometry(tmp_path: Path) -> None:
    src = tmp_path / "in.stl"
    out = tmp_path / "k.stl"
    _box(src)
    base_faces = len(trimesh.load(src, force="mesh").faces)
    method = add_keychain_loop(src, out)
    assert method in ("union", "concat")
    assert out.exists()
    assert len(trimesh.load(out, force="mesh").faces) > base_faces


def test_base_adds_geometry(tmp_path: Path) -> None:
    src = tmp_path / "in.stl"
    out = tmp_path / "s.stl"
    _box(src)
    assert add_base(src, out) in ("union", "concat")


def test_magnet_cavity_creates_pocket_and_returns_top_z(tmp_path: Path) -> None:
    src = tmp_path / "in.stl"
    out = tmp_path / "m.stl"
    _box(src)
    r = add_magnet_cavity(src, out, diameter_mm=5, height_mm=2)
    assert r["ok"] is True
    # 5×2 자석 + clearance 0.2mm → 천장 Z ≈ 2.2mm
    assert abs(r["top_z"] - 2.2) < 0.01
    assert out.exists()


def test_nfc_cavity_uses_27mm(tmp_path: Path) -> None:
    src = tmp_path / "in.stl"
    out = tmp_path / "n.stl"
    # NFC 27mm 캐비티를 담을 수 있는 박스
    trimesh.creation.box((40, 40, 6)).export(src)
    r = add_nfc_cavity(src, out)
    assert r["ok"] is True
    assert abs(r["top_z"] - 1.2) < 0.01  # 1mm depth + 0.2 clearance
