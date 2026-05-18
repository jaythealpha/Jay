"""Mesh 검증 + 자동 리페어.

Meshy 생성물은 출력 불가한 경우가 많음 (non-manifold, 구멍, 뒤집힌 normal).
trimesh로 기본 리페어 수행 후, 출력 가능성 메트릭을 반환.

trimesh 미설치(mesh extra) 시 ImportError 대신 명확한 안내 예외.
"""

from __future__ import annotations

from dataclasses import dataclass
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

    @property
    def max_dimension_mm(self) -> float:
        return max(self.bbox_mm)

    @property
    def has_geometry(self) -> bool:
        """슬라이서에 넘길 최소 조건: 삼각형 존재 + 크기 합리적.
        watertight가 아니어도 OrcaSlicer/Bambu가 자체 복구하므로 통과."""
        return self.triangle_count > 0 and self.max_dimension_mm > 1.0

    @property
    def printable(self) -> bool:
        """엄격 기준: 완전 watertight + 부피 확보."""
        return self.watertight and self.volume_mm3 > 1.0 and self.max_dimension_mm > 1.0


def repair_mesh(src: Path, dest_dir: Path, scale_to_mm: float | None = None) -> MeshReport:
    """src 메쉬를 리페어해서 dest_dir에 STL로 저장. MeshReport 반환.

    scale_to_mm: 지정 시 최대 치수를 이 값(mm)에 맞춰 스케일.
    """
    try:
        import numpy as np  # noqa: F401
        import trimesh
    except ImportError as e:
        raise MeshToolingMissing(
            "trimesh/numpy 필요. `uv sync --extra mesh` 실행."
        ) from e

    mesh = trimesh.load(src, force="mesh")
    if mesh.is_empty:
        raise ValueError(f"Empty mesh: {src}")

    repaired = False
    if not mesh.is_watertight:
        trimesh.repair.fix_inversion(mesh)
        trimesh.repair.fix_winding(mesh)
        trimesh.repair.fill_holes(mesh)
        try:
            mesh.fill_holes()  # Trimesh 인스턴스 메서드 (추가 hole 처리)
        except Exception:  # noqa: BLE001
            pass
        trimesh.repair.fix_normals(mesh)
        repaired = True

    # trimesh 4.x는 remove_duplicate_faces() 제거됨 → update_faces(mask) 방식.
    # 버전차로 일부 메서드가 없어도 핵심 리페어는 계속되도록 방어적 처리.
    try:
        if hasattr(mesh, "unique_faces"):
            mesh.update_faces(mesh.unique_faces())
        if hasattr(mesh, "nondegenerate_faces"):
            mesh.update_faces(mesh.nondegenerate_faces())
        mesh.remove_unreferenced_vertices()
        mesh.merge_vertices()
    except Exception:  # noqa: BLE001 — cleanup은 best-effort
        pass

    if scale_to_mm is not None:
        cur_max = float(mesh.extents.max())
        if cur_max > 0:
            mesh.apply_scale(scale_to_mm / cur_max)
            repaired = True

    dest_dir.mkdir(parents=True, exist_ok=True)
    out = dest_dir / f"{src.stem}_repaired.stl"
    mesh.export(out)

    ext = mesh.extents
    # 부피: watertight면 실측, 아니면 convex hull로 근사 (정보용)
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
    )
