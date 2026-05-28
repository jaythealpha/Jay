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


def _build_cap_base(
    top_mm: float, height_mm: float, wall_mm: float,
    top_thickness_mm: float, stem_height_mm: float,
):
    """속이 빈 키캡 본체 + MX 십자 스템. 반환 (cap, inner_h) 또는 (None, reason)."""
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
        return None, "hollow_failed"

    # 3) MX 십자 스템 (천장에서 아래로 돌출)
    a = trimesh.creation.box((4.1, 1.35, stem_height_mm))
    b = trimesh.creation.box((1.35, 4.1, stem_height_mm))
    stem = _boolean("union", [a, b])
    if stem is None:
        return None, "stem_failed"
    # 스템 윗면이 내부 천장(inner_h)에 닿고 아래로 stem_height 만큼
    stem.apply_translation((0, 0, inner_h - stem_height_mm / 2 + 0.01))
    cap = _boolean("union", [cap, stem])
    if cap is None:
        return None, "stem_union_failed"
    return cap, inner_h


def _load_topper(model_path: Path, topper_mm: float, height_mm: float):
    """토퍼 모델 로드 → 키캡 윗면 크기에 맞춰 축소 후 윗면에 배치. visual 보존."""
    import trimesh

    model = trimesh.load(model_path, force="mesh")
    if model.is_empty:
        return None
    ext = model.extents
    longest_xy = max(float(ext[0]), float(ext[1]))
    if longest_xy > 0:
        model.apply_scale(topper_mm / longest_xy)
    mb = model.bounds
    mcx = (mb[0][0] + mb[1][0]) / 2
    mcy = (mb[0][1] + mb[1][1]) / 2
    # 토퍼 바닥을 키캡 윗면에 살짝 겹치게 (융합)
    model.apply_translation((-mcx, -mcy, height_mm - mb[0][2] - 0.3))
    return model


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
    cap, inner_h = _build_cap_base(
        top_mm, height_mm, wall_mm, top_thickness_mm, stem_height_mm)
    if cap is None:
        return {"ok": False, "method": inner_h}

    model = _load_topper(model_stl, topper_mm, height_mm)
    if model is None:
        return {"ok": False, "method": "empty_model"}

    out = _boolean("union", [cap, model])
    if out is None:
        return {"ok": False, "method": "topper_union_failed"}
    out.export(out_stl)
    return {"ok": True, "method": "keycap"}


def _topper_face_colors(mesh):
    """토퍼 메쉬에서 면(face)별 RGB(uint8) 추출. 색 정보가 없으면 None.

    텍스처(TextureVisuals)는 to_color()로 정점색 변환 후 면 평균.
    단색/무색이면(분산 거의 0) None → 멀티컬러 불가로 처리.
    """
    import numpy as np

    vis = getattr(mesh, "visual", None)
    if vis is None or len(mesh.faces) == 0:
        return None
    cv = vis
    try:
        if hasattr(vis, "to_color"):
            cv = vis.to_color()
    except Exception:  # noqa: BLE001
        cv = vis

    fc = getattr(cv, "face_colors", None)
    if fc is not None and len(fc) == len(mesh.faces):
        arr = np.asarray(fc)[:, :3].astype(float)
        if arr.std() > 3:
            return arr.astype(int)
    vc = getattr(cv, "vertex_colors", None)
    if vc is not None and len(vc) == len(mesh.vertices):
        vca = np.asarray(vc)[:, :3].astype(float)
        fcol = vca[mesh.faces].mean(axis=1)
        if fcol.std() > 3:
            return fcol.astype(int)
    return None


def make_keycap_multicolor(
    model_path: Path, ddir: Path, stem: str, *,
    top_mm: float = 18.0,
    height_mm: float = 9.0,
    wall_mm: float = 1.6,
    top_thickness_mm: float = 2.0,
    stem_height_mm: float = 4.0,
    topper_mm: float = 14.0,
    n_colors: int = 4,
) -> dict:
    """텍스처가 있는 토퍼로 멀티컬러 키캡 산출물 생성.

    토퍼 면색을 k-means로 n_colors개로 군집 → 베이스(키캡 본체+스템)는
    최다 색(extruder 1)에 합치고, 나머지 색 영역을 extruder 2..N 파트로.
    산출(ddir):
      - {stem}.bambu.3mf : Bambu/Orca 멀티컬러 (파트별 익스트루더)
      - {stem}.color.3mf : 정점색 입힌 미리보기
      - {stem}_c{n}.stl  : 색 파트별 STL
      - {stem}.palette.json : 익스트루더↔색 매핑
    반환 {ok, method, colors}.
    """
    import json

    import numpy as np
    import trimesh

    from bambu_auto.services.mesh.bambu3mf import write_bambu_multicolor_3mf

    cap, inner_h = _build_cap_base(
        top_mm, height_mm, wall_mm, top_thickness_mm, stem_height_mm)
    if cap is None:
        return {"ok": False, "method": inner_h}

    topper = _load_topper(model_path, topper_mm, height_mm)
    if topper is None:
        return {"ok": False, "method": "empty_model"}

    face_colors = _topper_face_colors(topper)
    if face_colors is None:
        return {"ok": False, "method": "no_color"}

    # 대표색 추출: 면색을 ~40 단위로 양자화 후 빈도 상위 distinct N개.
    # 각 면을 최근접 대표색에 스냅 → 경계 혼색이 새 색을 만들지 않음
    # (flat_panel.build_multicolor와 동일 철학).
    k = max(2, min(int(n_colors), 8))
    fc = face_colors.astype(int)
    q = np.clip((fc // 40) * 40 + 20, 0, 255)
    keys, cnts = np.unique(q.reshape(-1, 3), axis=0, return_counts=True)
    keep: list = []
    for i in np.argsort(-cnts):
        c = keys[i].astype(float)
        if all(float(np.sqrt(((c - kk) ** 2).sum())) > 45 for kk in keep):
            keep.append(c)
        if len(keep) >= k:
            break
    if not keep:
        return {"ok": False, "method": "no_palette"}
    palette = np.array(keep)

    def _assign(pal):
        return np.argmin(
            ((fc[:, None, :] - pal[None, :, :]) ** 2).sum(2), axis=1)

    labels = _assign(palette)
    # 비중 작은 색(<4%)은 버리고 남은 주요색으로 재스냅 (잡색/경계 혼색 제거)
    n_faces = len(fc)
    shares = np.array([(labels == i).sum() / n_faces
                       for i in range(len(palette))])
    keep_idx = [i for i in range(len(palette)) if shares[i] >= 0.04]
    if len(keep_idx) < 2:
        keep_idx = list(np.argsort(-shares)[:2])
    if len(keep_idx) < len(palette):
        palette = palette[keep_idx]
        labels = _assign(palette)

    # 면적(면 수) 내림차순 → 최다 색이 베이스(extruder 1)
    used = sorted((i for i in range(len(palette)) if (labels == i).any()),
                  key=lambda i: -int((labels == i).sum()))

    ddir = Path(ddir)
    ddir.mkdir(parents=True, exist_ok=True)

    parts: list = []          # 익스트루더 순서대로 (mesh, color)
    palette_hex: list[str] = []
    for rank, ci in enumerate(used):
        fidx = np.where(labels == ci)[0]
        if len(fidx) == 0:
            continue
        sub = topper.submesh([fidx], append=True, repair=False)
        col = tuple(int(x) for x in palette[ci])
        if rank == 0:
            # 베이스(키캡 본체+스템)를 최다 색 토퍼 영역과 한 파트로
            sub = trimesh.util.concatenate([cap, sub])
        parts.append((sub, col))
        palette_hex.append("#%02x%02x%02x" % col)

    if not parts:
        return {"ok": False, "method": "no_parts"}

    # 색 파트별 STL (다운로드/검수용)
    for i, (mesh, _col) in enumerate(parts, start=1):
        try:
            mesh.export(ddir / f"{stem}_c{i}.stl")
        except Exception:  # noqa: BLE001
            pass

    # 정점색 미리보기 (.color.3mf / glb)
    try:
        colored = []
        for mesh, col in parts:
            m = mesh.copy()
            m.visual = trimesh.visual.ColorVisuals(
                face_colors=np.tile([*col, 255], (len(m.faces), 1)))
            colored.append(m)
        merged = trimesh.util.concatenate(colored)
        merged.export(ddir / f"{stem}.color.3mf")
        merged.export(ddir / f"{stem}.glb")
    except Exception:  # noqa: BLE001
        pass

    # Bambu/Orca 멀티컬러 3MF (파트별 익스트루더)
    try:
        write_bambu_multicolor_3mf([m for m, _ in parts],
                                   ddir / f"{stem}.bambu.3mf")
    except Exception:  # noqa: BLE001
        pass

    (ddir / f"{stem}.palette.json").write_text(json.dumps({
        "colors": palette_hex,
        "filament_map": [{"extruder": i + 1, "hex": h}
                         for i, h in enumerate(palette_hex)],
    }))
    return {"ok": True, "method": "keycap_multicolor", "colors": palette_hex}


def fit_mx_socket(
    model_stl: Path, out_stl: Path, *,
    target_u_mm: float = 18.0,
    uniform_scale: bool = True,
    post_d_mm: float = 5.5,
    cross_len_mm: float = 4.1,
    cross_w_mm: float = 1.35,
    socket_depth_mm: float = 4.0,
) -> dict:
    """이미 '키캡 형태'인 모델(예: Meshy 생성)을 1u 크기로 스케일하고
    바닥 중앙에 규격 Cherry MX 암(female) 십자 소켓을 새로 차감한다.

    Meshy가 붙인 부정확한 소켓은 규격 솔리드 기둥(Ø5.5)으로 덮어 무력화한 뒤
    그 기둥에 규격 십자(+) 구멍을 파서 실제 스위치에 장착되게 만든다.
    소켓 치수는 모델 크기와 무관한 절대 규격이라 스케일하지 않는다.
    반환 {ok, method, scale, base_mm, height_mm}."""
    import trimesh

    mesh = trimesh.load(model_stl, force="mesh")
    if mesh.is_empty:
        return {"ok": False, "method": "empty_model"}

    # 1) 1u 크기로 스케일 (footprint = 긴 XY 변 → target). 소켓은 그대로.
    ext = mesh.extents
    base = max(float(ext[0]), float(ext[1]))
    scale = (target_u_mm / base) if base > 0 else 1.0
    mesh.apply_scale(scale if uniform_scale else [scale, scale, 1.0])

    bmin, bmax = mesh.bounds
    cx = (bmin[0] + bmax[0]) / 2
    cy = (bmin[1] + bmax[1]) / 2
    z0 = float(bmin[2])  # 바닥(스위치가 들어오는 개구부)
    cap_h = float(bmax[2] - bmin[2])

    # 2) 규격 기둥(Ø post_d)을 바닥~천장 근처까지 union → Meshy 부정확 소켓을
    #    덮고 캡 천장과 확실히 연결(끊김 방지). 캡 내부에 숨으므로 외관 무영향.
    post_h = max(socket_depth_mm + 1.5, cap_h - 1.5)
    post = trimesh.creation.cylinder(radius=post_d_mm / 2, height=post_h)
    post.apply_translation([cx, cy, z0 + post_h / 2])
    capped = _boolean("union", [mesh, post]) or mesh

    # 3) 규격 십자(+) 암 소켓을 바닥(z0)에서 위로 socket_depth 만큼 차감
    depth = socket_depth_mm
    a = trimesh.creation.box((cross_len_mm, cross_w_mm, depth + 0.4))
    b = trimesh.creation.box((cross_w_mm, cross_len_mm, depth + 0.4))
    cross = _boolean("union", [a, b])
    if cross is None:
        return {"ok": False, "method": "cross_failed"}
    # 바닥 면에서 열려 위로 depth (아래로 0.2 더 내려 깔끔히 관통)
    cross.apply_translation([cx, cy, z0 + depth / 2 - 0.2])
    out = _boolean("difference", [capped, cross])
    if out is None:
        return {"ok": False, "method": "socket_cut_failed"}

    out.export(out_stl)
    nb = out.bounds
    return {
        "ok": True, "method": "mx_socket",
        "scale": round(float(scale), 3),
        "base_mm": round(float(max(nb[1][0] - nb[0][0], nb[1][1] - nb[0][1])), 2),
        "height_mm": round(float(nb[1][2] - nb[0][2]), 2),
    }
