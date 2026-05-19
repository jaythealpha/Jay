"""모델에 키링 고리 / 받침대 추가 (캐릭터 굿즈 폼팩터).

AI 메쉬는 불완전할 수 있어 boolean union이 실패할 수 있음 →
실패 시 원본 유지(예외 전파 안 함). manifold3d 엔진 사용.
"""

from __future__ import annotations

from pathlib import Path


def _union(mesh, part):
    """robust boolean union. 실패 시 None."""
    import trimesh

    for engine in ("manifold", None):
        try:
            kw = {"engine": engine} if engine else {}
            out = trimesh.boolean.union([mesh, part], **kw)
            if out is not None and not out.is_empty:
                return out
        except Exception:  # noqa: BLE001
            continue
    return None


def add_keychain_loop(stl_in: Path, stl_out: Path) -> bool:
    """모델 상단 중앙에 키링 고리(torus) 부착. 성공 시 True."""
    import numpy as np
    import trimesh

    mesh = trimesh.load(stl_in, force="mesh")
    ext = mesh.extents
    bmin, bmax = mesh.bounds
    cx = (bmin[0] + bmax[0]) / 2
    cy = (bmin[1] + bmax[1]) / 2
    top_z = bmax[2]

    # 고리 크기: 모델 크기에 비례하되 최소치 보장 (키링 핀 통과용)
    minor = max(1.2, float(ext.max()) * 0.03)
    major = max(3.5, float(ext.max()) * 0.08)
    loop = trimesh.creation.torus(major, minor)
    # 기본 torus는 XY평면(구멍축=Z). 매달리려면 구멍축=Y로 회전.
    loop.apply_transform(trimesh.transformations.rotation_matrix(
        np.pi / 2, [1, 0, 0]))
    # 상단에 약간 겹치게 배치 (융합 보장)
    loop.apply_translation([cx, cy, top_z + major - minor])

    out = _union(mesh, loop)
    if out is None:
        return False
    out.export(stl_out)
    return True


def add_base(stl_in: Path, stl_out: Path) -> bool:
    """모델 하단에 원형 받침대 부착(세워두는 피규어용). 성공 시 True."""
    import trimesh

    mesh = trimesh.load(stl_in, force="mesh")
    ext = mesh.extents
    bmin, bmax = mesh.bounds
    cx = (bmin[0] + bmax[0]) / 2
    cy = (bmin[1] + bmax[1]) / 2

    radius = max(float(max(ext[0], ext[1])) * 0.6, 6.0)
    height = max(float(ext.max()) * 0.05, 3.0)
    base = trimesh.creation.cylinder(radius=radius, height=height)
    # 받침 윗면이 모델 바닥과 살짝 겹치도록
    base.apply_translation([cx, cy, bmin[2] + height / 2 - 0.5])

    out = _union(mesh, base)
    if out is None:
        return False
    out.export(stl_out)
    return True


ADDONS = {
    "keychain": add_keychain_loop,
    "stand": add_base,
}
