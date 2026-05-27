"""2D 이미지 → 평면 패널 (자석/NFC/플랫 키링용). Meshy 미사용·크레딧 0.

전략: 배경 제거된 이미지의 실루엣을 두께만큼 압출(단색 평판) +
이미지의 어두운 주요 선을 상단에 음각(deboss). 자석/NFC 공동은
이후 addon 단계에서 바닥에 추가.
"""

from __future__ import annotations

from pathlib import Path

from bambu_auto.services.mesh.branding import _mask_to_polygons, _polygons_to_mesh


def _fill_holes(mask):
    """실루엣 내부 구멍 채움 (외곽선만 채워 솔리드화). cv2 uint8 mask 입력."""
    import cv2
    import numpy as np

    out = np.zeros_like(mask)
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(out, cnts, -1, 255, thickness=cv2.FILLED)
    return out


def make_flat_panel(
    image_path: Path, out_stl: Path, *,
    size_mm: float = 50.0,
    thickness_mm: float = 3.5,
    line_depth_mm: float = 0.6,
) -> dict:
    """이미지 실루엣을 평판으로 압출 + 어두운 선 음각. 반환 {ok, method}."""
    import cv2
    import numpy as np
    import trimesh
    from PIL import Image

    img = Image.open(image_path).convert("RGBA")
    arr = np.array(img)
    alpha = arr[:, :, 3]
    gray = np.array(img.convert("L"))

    # 실루엣 마스크: 투명도 있으면 alpha, 없으면(배경 흰색) 비백색 영역
    if int(alpha.min()) == 255:
        sil = gray < 245
    else:
        sil = alpha > 128
    sil_mask = _fill_holes((sil.astype("uint8")) * 255)  # 내부 구멍 채움
    if int(sil_mask.max()) == 0:
        return {"ok": False, "method": "empty_silhouette"}

    h_px, w_px = sil_mask.shape
    scale = size_mm / max(h_px, w_px)

    sil_polys = _mask_to_polygons(sil_mask, scale)
    if not sil_polys:
        return {"ok": False, "method": "no_silhouette_polygons"}
    base = _polygons_to_mesh(sil_polys, thickness_mm)  # z=[0, thickness]
    if base is None:
        return {"ok": False, "method": "extrude_failed"}

    # 라인 음각: 실루엣 내부의 어두운 픽셀 = 주요 선/윤곽
    dark = ((gray < 100) & sil).astype("uint8") * 255
    dark = cv2.dilate(dark, np.ones((3, 3), np.uint8), iterations=1)  # 인쇄 가능 폭
    out_mesh = base
    line_polys = _mask_to_polygons(dark, scale)
    if line_polys:
        stamp = _polygons_to_mesh(line_polys, line_depth_mm + 0.4)
        if stamp is not None:
            # 상단면(z=thickness)에서 line_depth 만큼 파이도록 위치
            stamp.apply_translation([0, 0, thickness_mm - line_depth_mm])
            for engine in ("manifold", None):
                try:
                    kw = {"engine": engine} if engine else {}
                    diff = trimesh.boolean.difference([base, stamp], **kw)
                    if diff is not None and not diff.is_empty:
                        out_mesh = diff
                        break
                except Exception:  # noqa: BLE001
                    continue

    out_mesh.export(out_stl)
    return {"ok": True, "method": "flat_panel"}


def _kmeans(pixels, k: int, iters: int = 12):
    """numpy 간단 k-means. pixels: Nx3 float. 반환 (centers kx3, labels N)."""
    import numpy as np

    n = len(pixels)
    if n == 0:
        return np.zeros((0, 3)), np.array([])
    k = min(k, n)
    # 초기 중심: 빈도 높은 색 위주(고르게 샘플)
    rng = np.random.default_rng(42)
    centers = pixels[rng.choice(n, k, replace=False)].astype(float)
    labels = np.zeros(n, dtype=int)
    for _ in range(iters):
        d = ((pixels[:, None, :] - centers[None, :, :]) ** 2).sum(2)
        labels = d.argmin(1)
        new = np.array([pixels[labels == i].mean(0) if (labels == i).any()
                        else centers[i] for i in range(k)])
        if np.allclose(new, centers, atol=0.5):
            centers = new
            break
        centers = new
    return centers, labels


def build_multicolor(
    image_path: Path, ddir: Path, stem: str, *,
    size_mm: float = 50.0,
    thickness_mm: float = 3.5,
    n_colors: int = 4,
    feature: dict | None = None,
    inlay_mm: float = 0.8,
) -> list[str]:
    """단단한 베이스 판(전체 실루엣) + 그 위에 깨끗한 색 영역을 얇게 올린
    '단일' 컬러 오브젝트 생성. 흩어지지 않고 견고하며 출력 가능.

    - 컬러 3MF/GLB/OBJ: 베이스+인레이를 하나로 묶은 컬러 오브젝트
    - palette.json: 추천 색
    feature: {"kind":"hole"} | {"kind":"cavity","d":,"h":} → 최종 형상에 적용
    """
    import json

    import cv2
    import numpy as np
    import trimesh
    from PIL import Image

    img = Image.open(image_path).convert("RGBA")
    arr = np.array(img)
    alpha = arr[:, :, 3]
    gray = np.array(img.convert("L"))
    sil = (gray < 245) if int(alpha.min()) == 255 else (alpha > 128)
    if not sil.any():
        return []
    # 잡티 줄이려 약한 블러 후 색 분석
    rgb = cv2.medianBlur(arr[:, :, :3], 5)

    H, W = sil.shape
    scale = size_mm / max(H, W)
    sil_area = int(sil.sum())
    min_area_px = max(60, int(sil_area * 0.01))  # 1% 미만 색조각 제거

    # 전경 대표색 (빈도순 정렬: 가장 많은 색 = 베이스)
    # 거친 색 히스토그램: 전경 색을 ~40 단위로 양자화 후 빈도 상위 distinct N개.
    # k-means가 큰 영역에 쏠려 작은 색을 놓치는 문제 회피 (색면 일러스트에 정확).
    fg = rgb[sil].astype(int)
    q = np.clip((fg // 40) * 40 + 20, 0, 255)
    keys, cnts = np.unique(q.reshape(-1, 3), axis=0, return_counts=True)
    bo = np.argsort(-cnts)
    keep: list = []
    for i in bo:
        c = keys[i].astype(float)
        if all(np.sqrt(((c - k) ** 2).sum()) > 45 for k in keep):
            keep.append(c)
        if len(keep) >= n_colors:
            break
    if not keep:
        return []
    palette = np.array(keep)

    flat_rgb = rgb.reshape(-1, 3).astype(float)
    lab = np.argmin(((flat_rgb[:, None, :] - palette[None, :, :]) ** 2).sum(2),
                    axis=1).reshape(H, W)
    counts = [int(((lab == i) & sil).sum()) for i in range(len(palette))]
    order = sorted(range(len(palette)), key=lambda i: -counts[i])  # 베이스=최다

    def clean(mask):
        m = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        nlab, lbl, stats, _ = cv2.connectedComponentsWithStats(m, 8)
        out = np.zeros_like(m)
        for k in range(1, nlab):
            if stats[k, cv2.CC_STAT_AREA] >= min_area_px:
                out[lbl == k] = 255
        return out

    # 베이스: 전체 실루엣(내부 구멍 채워 솔리드), 색 = 최다색
    base_polys = _mask_to_polygons(_fill_holes((sil.astype("uint8")) * 255), scale)
    if not base_polys:
        return []
    base = _polygons_to_mesh(base_polys, thickness_mm)
    if base is None:
        return []
    base_color = tuple(int(x) for x in palette[order[0]])

    bmin, bmax = base.bounds
    palette_hex = ["#%02x%02x%02x" % base_color]
    parts = [(base, base_color)]

    # 인레이: 나머지 색을 베이스 윗면에 얇게 (깨끗한 마스크만)
    for idx in order[1:]:
        mask = ((lab == idx) & sil).astype("uint8") * 255
        mask = clean(mask)
        if int(mask.max()) == 0:
            continue
        polys = _mask_to_polygons(mask, scale)
        if not polys:
            continue
        inlay = _polygons_to_mesh(polys, inlay_mm)
        if inlay is None:
            continue
        inlay.apply_translation([0, 0, thickness_mm - 0.01])  # 윗면에 올림
        col = tuple(int(x) for x in palette[idx])
        parts.append((inlay, col))
        palette_hex.append("#%02x%02x%02x" % col)

    # feature 적용: 키링은 베이스에 고리 탭 '추가'(캐릭터 온전), 공동은 차감
    cx = (bmin[0] + bmax[0]) / 2
    if feature and feature.get("kind") == "hole":
        from bambu_auto.services.mesh.addons import attach_keyring

        out, _ = attach_keyring(parts[0][0], hole_d=3.0, wall=2.0)
        if out is not None:
            parts[0] = (out, parts[0][1])
    elif feature and feature.get("kind") == "cavity":
        d = float(feature.get("d", 5)) + 0.4
        h = float(feature.get("h", 2)) + 0.2
        cyl = trimesh.creation.cylinder(radius=d / 2, height=h)
        cyl.apply_translation([cx, (bmin[1] + bmax[1]) / 2,
                               bmin[2] + h / 2 - 0.05])
        for eng in ("manifold", None):
            try:
                kw = {"engine": eng} if eng else {}
                cut = trimesh.boolean.difference([parts[0][0], cyl], **kw)
                if cut is not None and not cut.is_empty:
                    parts[0] = (cut, parts[0][1])
                    break
            except Exception:  # noqa: BLE001
                continue

    # 색을 입혀 하나의 오브젝트로 합침 (미리보기 GLB/OBJ — 흩어짐 방지)
    colored = []
    for mesh, col in parts:
        mesh.visual = trimesh.visual.ColorVisuals(
            face_colors=np.tile([*col, 255], (len(mesh.faces), 1)))
        colored.append(mesh)
    merged = trimesh.util.concatenate(colored)
    merged.export(ddir / f"{stem}.glb")
    merged.export(ddir / f"{stem}.obj")
    try:
        merged.export(ddir / f"{stem}.color.3mf")
    except Exception:  # noqa: BLE001
        pass

    # Bambu/Orca 호환 멀티컬러 3MF: 파트별 익스트루더 배정(실제 다색 출력)
    try:
        from bambu_auto.services.mesh.bambu3mf import write_bambu_multicolor_3mf

        write_bambu_multicolor_3mf([m for m, _ in parts],
                                   ddir / f"{stem}.bambu.3mf")
    except Exception:  # noqa: BLE001
        pass

    # palette.json: 익스트루더(필라멘트) 번호 → 색 매핑 (1번=베이스)
    (ddir / f"{stem}.palette.json").write_text(json.dumps({
        "colors": palette_hex,
        "filament_map": [{"extruder": i + 1, "hex": h}
                         for i, h in enumerate(palette_hex)],
    }))
    return palette_hex
