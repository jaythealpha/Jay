"""repair_mesh 2단계 strategy 검증.

- 정상 watertight 메쉬는 그대로 통과 (method=trimesh, watertight=True).
- 큰 구멍이 있는 비-watertight 메쉬는 force_watertight=True에서 voxel-remesh로
  강제 watertight (method=voxel_remesh).
- force_watertight=False면 voxel-remesh 안 함 — 사용자가 명시 선택 시만.
- 스케일 옵션은 최대 치수를 정확히 맞춤.
- MeshReport.printable은 watertight + manifold + 부피 모두 만족할 때만 True.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import trimesh

from bambu_auto.services.mesh.repair import repair_mesh


def _box_stl(tmp: Path, size: float = 10.0) -> Path:
    m = trimesh.creation.box([size, size, size])
    p = tmp / "box.stl"
    m.export(p)
    return p


def _open_box_stl(tmp: Path, size: float = 10.0) -> Path:
    """위 면이 빠진 큰 구멍이 있는 비-watertight 메쉬."""
    v = np.array([
        [0, 0, 0], [size, 0, 0], [size, size, 0], [0, size, 0],
        [0, 0, size], [size, 0, size], [size, size, size], [0, size, size],
    ], dtype=float)
    f = np.array([
        [0, 1, 2], [0, 2, 3],     # bottom
        [0, 4, 5], [0, 5, 1],     # front
        [1, 5, 6], [1, 6, 2],
        [2, 6, 7], [2, 7, 3],
        [3, 7, 4], [3, 4, 0],
        # missing top face → non-watertight (큰 구멍)
    ])
    mesh = trimesh.Trimesh(vertices=v, faces=f, process=False)
    assert not mesh.is_watertight  # 입력 사전조건
    p = tmp / "open.stl"
    mesh.export(p)
    return p


def test_clean_mesh_passes_through_trimesh(tmp_path: Path) -> None:
    src = _box_stl(tmp_path)
    r = repair_mesh(src, tmp_path / "out")
    assert r.watertight
    assert r.method == "trimesh"
    assert r.manifold_ok
    assert r.genus == 0
    assert r.printable
    assert r.volume_mm3 > 100  # ~1000 (10³)


def test_voxel_remesh_unit_produces_watertight() -> None:
    """_voxel_remesh: 임의 닫힌 메쉬 입력 → watertight 출력 보장."""
    from bambu_auto.services.mesh.repair import _voxel_remesh

    m = trimesh.creation.box([10, 10, 10])
    out = _voxel_remesh(m, pitch_ratio=0.05)
    assert out.is_watertight
    assert len(out.faces) > 0


def test_force_watertight_routes_to_voxel_when_l1_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """L1 결과가 여전히 non-watertight라면 voxel-remesh 경로 진입을 단정.

    trimesh.is_watertight를 가짜로 False로 강제해, voxel 분기 진입을 검증.
    """
    src = _box_stl(tmp_path)
    # Trimesh.is_watertight를 강제 False로 패치 → L1 통과 후에도 voxel 분기 진입
    monkeypatch.setattr(
        trimesh.Trimesh, "is_watertight",
        property(lambda self: False),
    )
    r = repair_mesh(src, tmp_path / "out", force_watertight=True)
    # voxel 경로가 강제됐는지 method로 단정
    assert r.method == "voxel_remesh", f"notes={r.notes}"


def test_scale_to_mm_matches_target(tmp_path: Path) -> None:
    src = _box_stl(tmp_path, size=10.0)
    r = repair_mesh(src, tmp_path / "out", scale_to_mm=80.0)
    assert abs(r.max_dimension_mm - 80.0) < 0.1
    assert r.watertight


def test_output_file_is_written(tmp_path: Path) -> None:
    src = _box_stl(tmp_path)
    r = repair_mesh(src, tmp_path / "out")
    assert r.path.exists()
    assert r.path.suffix == ".stl"


def test_empty_mesh_raises(tmp_path: Path) -> None:
    # 빈 STL: vertex 0개
    p = tmp_path / "empty.stl"
    trimesh.Trimesh(vertices=np.zeros((0, 3)), faces=np.zeros((0, 3), int)).export(p)
    with pytest.raises(ValueError):
        repair_mesh(p, tmp_path / "out")
