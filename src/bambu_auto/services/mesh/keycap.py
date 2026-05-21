"""기계식 키보드 키캡 생성 (Meshy Creative Lab '키캡' 대응).

생성된 모델을 표준 MX 스템이 달린 키캡 위에 올림.
스템: Cherry MX 십자(cross) — 두 박스의 union, 천장에서 아래로 돌출.

주의(인쇄): 키캡+토퍼는 방향/서포트가 중요. Bambu Studio에서
프리뷰로 방향 확인 권장 (보통 윗면을 베드로, 또는 서포트 사용).
"""

from __future__ import annotations

from pathlib import Path


def _boolean(op: str, meshes: list):
    import trimesh

    fn = {"union": trimesh.boolean.union,
          "difference": trimesh.boolean.difference}[op]
    for engine in ("manifold", None):
        try:
            kw = {"engine": engine} if engine else {}
            out = fn(meshes, **kw)
            if out is not None and not out.is_empty:
                return out
        except Exception:  # noqa: BLE001
            continue
    return None


def make_keycap(
    model_stl: Path, out_stl: Path, *,
    top_mm: float = 18.0,
    height_mm: float = 9.0,
    wall_mm: float = 1.6,
    top_thickness_mm: float = 2.0,
    stem_height_mm: float = 4.0,
    topper_mm: float = 14.0,
) -> dict:
    """모델을 MX 키캡 위에 얹어 인쇄용 키캡 생성. 반환 {ok, method}."""
    import trimesh

    # 1) 외곽 본체 (바닥 z=0)
    body = trimesh.creation.box((top_mm, top_mm, height_mm))
    body.apply_translation((0, 0, height_mm / 2))

    # 2) 내부 비움 (바닥에서 천장까지) → 벽+윗판만 남김
    inner_h = height_mm - top_thickness_mm
    inner = trimesh.creation.box(
        (top_mm - 2 * wall_mm, top_mm - 2 * wall_mm, inner_h))
    inner.apply_translation((0, 0, inner_h / 2 - 0.01))
    cap = _boolean("difference", [body, inner])
    if cap is None:
        return {"ok": False, "method": "hollow_failed"}

    # 3) MX 십자 스템 (천장에서 아래로 돌출)
    a = trimesh.creation.box((4.1, 1.35, stem_height_mm))
    b = trimesh.creation.box((1.35, 4.1, stem_height_mm))
    stem = _boolean("union", [a, b])
    if stem is None:
        return {"ok": False, "method": "stem_failed"}
    # 스템 윗면이 내부 천장(inner_h)에 닿고 아래로 stem_height 만큼
    stem.apply_translation((0, 0, inner_h - stem_height_mm / 2 + 0.01))
    cap = _boolean("union", [cap, stem])
    if cap is None:
        return {"ok": False, "method": "stem_union_failed"}

    # 4) 토퍼: 모델을 키캡 윗면 크기에 맞춰 축소 후 윗면(z=height_mm)에 배치
    model = trimesh.load(model_stl, force="mesh")
    if model.is_empty:
        return {"ok": False, "method": "empty_model"}
    ext = model.extents
    longest_xy = max(float(ext[0]), float(ext[1]))
    if longest_xy > 0:
        model.apply_scale(topper_mm / longest_xy)
    mb = model.bounds
    mcx = (mb[0][0] + mb[1][0]) / 2
    mcy = (mb[0][1] + mb[1][1]) / 2
    # 토퍼 바닥을 키캡 윗면에 살짝 겹치게 (융합)
    model.apply_translation((-mcx, -mcy, height_mm - mb[0][2] - 0.3))

    out = _boolean("union", [cap, model])
    if out is None:
        return {"ok": False, "method": "topper_union_failed"}
    out.export(out_stl)
    return {"ok": True, "method": "keycap"}
