"""Mesh 검증 + 자동 리페어 (2단계 strategy).

Meshy 생성물은 출력 불가한 경우가 많음 (non-manifold, 구멍, 뒤집힌 normal).
다음 순서로 watertight 보장을 시도:

  L1: trimesh 빠른 리페어 (fix_inversion/winding/normals + fill_holes)
       → 작은 구멍·뒤집힌 면은 거의 다 잡힘. 메쉬 디테일 100% 유지.
  L2: voxelize → marching_cubes 재구성 (force_watertight=True 일 때만)
       → 큰 구멍·자기교차·non-manifold edge 등도 강제로 닫음.
       → 트레이드오프: 표면이 약간 매끈해지고 폴리곤 수 증가.
  V : manifold3d로 위상 검증 (status/genus/volume)
       → 슬라이서가 거부할 만한 위상 결함을 결정적으로 감지.

각 단계의 결과는 MeshReport.method 로 노출.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


class MeshToolingMissing(RuntimeError):
    """mesh extra 미설치. `uv sync --extra mesh` 필요."""


@dataclass
class MeshReport:
    path: Path
    watertight: bool
    volume_mm3: float
    bbox_mm: tuple[float, float, float]
    triangle_count: int
    repaired: bool
    method: str = "trimesh"  # 'trimesh' | 'voxel_remesh' | 'noop'
    manifold_ok: bool = False
    genus: int = -1
    notes: list[str] = field(default_factory=list)

    @property
    def max_dimension_mm(self) -> float:
        return max(self.bbox_mm)

    @property
    def has_geometry(self) -> bool:
        """슬라이서에 넘길 최소 조건: 삼각형 존재 + 크기 합리적."""
        return self.triangle_count > 0 and self.max_dimension_mm > 1.0

    @property
    def printable(self) -> bool:
        """엄격 기준: watertight + manifold + 부피·크기 확보."""
        return (
            self.watertight
            and self.manifold_ok
            and self.volume_mm3 > 1.0
            and self.max_dimension_mm > 1.0
        )


def repair_mesh(
    src: Path,
    dest_dir: Path,
    scale_to_mm: float | None = None,
    force_watertight: bool = True,
    voxel_pitch_ratio: float = 0.01,
) -> MeshReport:
    """src 메쉬를 리페어해서 dest_dir에 STL로 저장. MeshReport 반환.

    scale_to_mm: 지정 시 최대 치수를 이 값(mm)에 맞춰 스케일.
    force_watertight: L1 후에도 watertight 아니면 voxel-remesh로 강제 (디테일 약간 손실).
    voxel_pitch_ratio: voxel 크기 = bbox_max × ratio. 0.01 → 100³ voxel = 디테일/속도 균형.
    """
    try:
        import numpy as np
        import trimesh
    except ImportError as e:
        raise MeshToolingMissing(
            "trimesh/numpy 필요. `uv sync --extra mesh` 실행."
        ) from e

    mesh = trimesh.load(src, force="mesh")
    if mesh.is_empty:
        raise ValueError(f"Empty mesh: {src}")

    notes: list[str] = []
    repaired = False
    method = "trimesh"

    # ---- L1: trimesh 빠른 리페어 ----
    if not mesh.is_watertight:
        trimesh.repair.fix_inversion(mesh)
        trimesh.repair.fix_winding(mesh)
        trimesh.repair.fill_holes(mesh)
        try:
            mesh.fill_holes()  # 인스턴스 메서드(추가 hole 처리)
        except Exception:  # noqa: BLE001
            pass
        trimesh.repair.fix_normals(mesh)
        repaired = True
        notes.append("L1:trimesh")

    # trimesh 4.x 호환 cleanup
    try:
        if hasattr(mesh, "unique_faces"):
            mesh.update_faces(mesh.unique_faces())
        if hasattr(mesh, "nondegenerate_faces"):
            mesh.update_faces(mesh.nondegenerate_faces())
        mesh.remove_unreferenced_vertices()
        mesh.merge_vertices()
    except Exception:  # noqa: BLE001
        pass

    # ---- L2: voxel-remesh로 강제 watertight ----
    if force_watertight and not mesh.is_watertight:
        try:
            mesh = _voxel_remesh(mesh, pitch_ratio=voxel_pitch_ratio)
            method = "voxel_remesh"
            repaired = True
            notes.append(f"L2:voxel(pitch_ratio={voxel_pitch_ratio})")
        except Exception as e:  # noqa: BLE001
            notes.append(f"L2-fail:{type(e).__name__}")

    # ---- 스케일 ----
    if scale_to_mm is not None:
        cur_max = float(mesh.extents.max())
        if cur_max > 0:
            mesh.apply_scale(scale_to_mm / cur_max)
            repaired = True

    # ---- 검증: manifold3d ----
    manifold_ok, genus = _verify_manifold(mesh)
    if not manifold_ok:
        notes.append("V:non-manifold")

    dest_dir.mkdir(parents=True, exist_ok=True)
    out = dest_dir / f"{src.stem}_repaired.stl"
    mesh.export(out)

    ext = mesh.extents
    if mesh.is_watertight:
        vol = abs(float(mesh.volume))
    else:
        try:
            vol = abs(float(mesh.convex_hull.volume))
        except Exception:  # noqa: BLE001
            vol = 0.0

    return MeshReport(
        path=out,
        watertight=bool(mesh.is_watertight),
        volume_mm3=vol,
        bbox_mm=(float(ext[0]), float(ext[1]), float(ext[2])),
        triangle_count=int(len(mesh.faces)),
        repaired=repaired,
        method=method,
        manifold_ok=manifold_ok,
        genus=genus,
        notes=notes,
    )


def _voxel_remesh(mesh, pitch_ratio: float = 0.01, min_pitch_mm: float = 0.1):
    """voxelize 후 fill + marching_cubes로 watertight 메쉬 재구성.

    pitch는 bbox 최대 치수의 ratio에 비례. 너무 작으면 메모리/시간 폭발,
    너무 크면 디테일 손실 → 0.01(=100³ 셀)이 PLA 1mm 노즐 출력 적정.
    """
    bbox_max = float(mesh.extents.max())
    if bbox_max <= 0:
        raise ValueError("zero-size bbox")
    pitch = max(bbox_max * pitch_ratio, min_pitch_mm)
    vox = mesh.voxelized(pitch=pitch).fill()
    out = vox.marching_cubes
    if out.is_empty or len(out.faces) == 0:
        raise ValueError("voxel_remesh produced empty mesh")
    return out


def _verify_manifold(mesh) -> tuple[bool, int]:
    """manifold3d로 위상 검증. (ok, genus) 반환.
    실패해도 ImportError가 아니면 False·-1로 graceful 처리.
    """
    try:
        import manifold3d as m3
        import numpy as np

        m = m3.Mesh(
            vert_properties=np.asarray(mesh.vertices, dtype=np.float32),
            tri_verts=np.asarray(mesh.faces, dtype=np.uint32),
        )
        M = m3.Manifold(m)
        if M.is_empty():
            return False, -1
        status = M.status()
        if status != m3.Error.NoError:
            return False, -1
        return True, int(M.genus())
    except ImportError:
        return False, -1
    except Exception:  # noqa: BLE001
        return False, -1
