"""모델에 키링 고리 / 받침대 추가 (캐릭터 굿즈 폼팩터).

AI 메쉬는 불완전할 수 있어 boolean union이 실패할 수 있음 →
실패 시 원본 유지(예외 전파 안 함). manifold3d 엔진 사용.
"""

from __future__ import annotations

from pathlib import Path


def _combine(mesh, part) -> tuple[object, str]:
    """robust boolean union → 실패 시 concat 폴백.
    반환: (결과 mesh | None, 방법 'union'|'concat'|'fail')."""
    import trimesh

    for engine in ("manifold", None):
        try:
            kw = {"engine": engine} if engine else {}
            out = trimesh.boolean.union([mesh, part], **kw)
            if out is not None and not out.is_empty:
                return out, "union"
        except Exception:  # noqa: BLE001
            continue
    # union 실패 시: 두 메쉬를 그냥 합쳐서 STL 안에 함께 둠.
    # 두 메쉬가 충분히 겹치면 슬라이서가 동일 perimeter로 묶어 한 파트로 출력됨.
    try:
        return trimesh.util.concatenate([mesh, part]), "concat"
    except Exception:  # noqa: BLE001
        return None, "fail"


def add_keychain_loop(stl_in: Path, stl_out: Path) -> str:
    """모델 상단 중앙에 키링 고리(torus) 부착.
    반환: 성공 방식 'union'|'concat' 또는 '' (실패, 진위는 truthy로 판단)."""
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

    out, method = _combine(mesh, loop)
    if out is None:
        return False
    out.export(stl_out)
    return method  # type: ignore[return-value]


def add_base(stl_in: Path, stl_out: Path) -> str:
    """모델 하단에 원형 받침대 부착(세워두는 피규어용).
    반환: 'union'|'concat' 또는 '' (실패)."""
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

    out, method = _combine(mesh, base)
    if out is None:
        return ""
    out.export(stl_out)
    return method


def _subtract(mesh, part):
    """boolean difference. 실패 시 None (concat 폴백 불가능 — 빈공간이 목적)."""
    import trimesh

    for engine in ("manifold", None):
        try:
            kw = {"engine": engine} if engine else {}
            out = trimesh.boolean.difference([mesh, part], **kw)
            if out is not None and not out.is_empty:
                return out, "subtract"
        except Exception:  # noqa: BLE001
            continue
    return None, "fail"


def add_magnet_cavity(stl_in: Path, stl_out: Path,
                      diameter_mm: float, height_mm: float,
                      clearance_d: float = 0.4,
                      clearance_h: float = 0.2) -> dict:
    """모델 바닥 부근에 자석 삽입용 원통 공동을 차감.
    반환: {method, top_z, ok}. top_z = 슬라이서 좌표(bed기준)의 공동 천장 Z."""
    import trimesh

    mesh = trimesh.load(stl_in, force="mesh")
    bmin, bmax = mesh.bounds
    cx = (bmin[0] + bmax[0]) / 2
    cy = (bmin[1] + bmax[1]) / 2

    cav_d = diameter_mm + clearance_d
    cav_h = height_mm + clearance_h
    # 공동 바닥을 모델 바닥과 일치 (살짝 내려 cut 보장)
    cyl = trimesh.creation.cylinder(radius=cav_d / 2, height=cav_h)
    cyl.apply_translation([cx, cy, bmin[2] + cav_h / 2 - 0.05])

    out, method = _subtract(mesh, cyl)
    if out is None:
        return {"ok": False, "method": method, "top_z": 0.0}
    out.export(stl_out)
    # 슬라이서가 모델 바닥을 z=0에 놓는다고 가정 → 공동 천장 Z=cav_h
    return {"ok": True, "method": method, "top_z": float(cav_h)}


def add_nfc_cavity(stl_in: Path, stl_out: Path,
                   diameter_mm: float = 27.0,
                   depth_mm: float = 1.0) -> dict:
    """NFC 태그(25mm) 삽입용 27mm × 1mm 디스크 공동."""
    return add_magnet_cavity(stl_in, stl_out, diameter_mm, depth_mm,
                             clearance_d=0.0, clearance_h=0.2)


def _keyring_ring(mesh, hole_d: float = 3.0, wall: float = 2.0):
    """캐릭터 메쉬의 '상단에서 재질이 가장 많은 지점'에 고리(구멍 뚫린 링)를
    깊게 겹쳐 부착하도록 위치시킨 ring 메쉬 반환. (중앙 빈공간 부착 방지)"""
    import numpy as np
    import trimesh

    v = mesh.vertices
    bmin, bmax = mesh.bounds
    cz = (bmin[2] + bmax[2]) / 2
    height = bmax[1] - bmin[1]
    r = hole_d / 2 + wall

    # 상단 밴드(위 12%)에서 x 히스토그램 피크 → 재질 많은 부착 x
    band = v[v[:, 1] >= bmax[1] - max(0.12 * height, r)]
    if len(band) == 0:
        band = v
    hist, edges = np.histogram(band[:, 0], bins=24)
    bi = int(hist.argmax())
    attach_x = (edges[bi] + edges[bi + 1]) / 2
    # 그 x 컬럼 부근의 실제 상단 y (표면)
    near = v[np.abs(v[:, 0] - attach_x) <= r]
    local_top = float(near[:, 1].max()) if len(near) else float(bmax[1])
    embed = min(r * 1.4, 4.5)            # 본체에 깊게 박아 자연스럽게 융합
    cy = local_top - embed + r

    outer = trimesh.creation.cylinder(radius=r, height=max(bmax[2] - bmin[2], 1))
    outer.apply_translation([attach_x, cy, cz])
    hole = trimesh.creation.cylinder(radius=hole_d / 2,
                                     height=(bmax[2] - bmin[2]) + 2)
    hole.apply_translation([attach_x, cy, cz])
    for eng in ("manifold", None):
        try:
            kw = {"engine": eng} if eng else {}
            ring = trimesh.boolean.difference([outer, hole], **kw)
            if ring is not None and not ring.is_empty:
                return ring, hole          # hole도 반환 → 부착 후 깔끔히 관통
        except Exception:  # noqa: BLE001
            continue
    return None, None


def attach_keyring(mesh, hole_d: float = 3.0, wall: float = 2.0):
    """mesh에 고리 탭을 union하고, 고리 구멍을 전체에 관통(캐릭터 솔기 제거).
    반환: (결과 mesh | None, method str)."""
    import trimesh

    ring, hole = _keyring_ring(mesh, hole_d, wall)
    if ring is None:
        return None, "ring_failed"
    out = None
    for eng in ("manifold", None):
        try:
            kw = {"engine": eng} if eng else {}
            u = trimesh.boolean.union([mesh, ring], **kw)
            if u is not None and not u.is_empty:
                out = u
                break
        except Exception:  # noqa: BLE001
            continue
    if out is None:
        out = trimesh.util.concatenate([mesh, ring])
        method = "keyring_tab(concat)"
    else:
        method = "keyring_tab"
    # 고리 구멍을 전체 관통 (구멍 안에 비치던 캐릭터 솔기 제거)
    for eng in ("manifold", None):
        try:
            kw = {"engine": eng} if eng else {}
            cut = trimesh.boolean.difference([out, hole], **kw)
            if cut is not None and not cut.is_empty:
                out = cut
                break
        except Exception:  # noqa: BLE001
            continue
    return out, method


def add_keyring_tab(stl_in: Path, stl_out: Path,
                    hole_d: float = 3.0, wall: float = 2.0) -> dict:
    """캐릭터 상단(재질 많은 지점)에 고리 탭을 깊게 겹쳐 '추가' + 구멍 관통."""
    import trimesh

    mesh = trimesh.load(stl_in, force="mesh")
    out, method = attach_keyring(mesh, hole_d, wall)
    if out is None:
        return {"ok": False, "method": method}
    out.export(stl_out)
    return {"ok": True, "method": method}


ADDONS = {
    "keychain": add_keychain_loop,
    "stand": add_base,
    # 'magnet'/'nfc'/'keyring' 는 별도 시그니처 — pipeline에서 직접 호출
}
