"""2D 이미지 → 평면 패널 (자석/NFC/플랫 키링용). Meshy 미사용·크레딧 0.

전략: 배경 제거된 이미지의 실루엣을 두께만큼 압출(단색 평판) +
이미지의 어두운 주요 선을 상단에 음각(deboss). 자석/NFC 공동은
이후 addon 단계에서 바닥에 추가.
"""

from __future__ import annotations

from pathlib import Path

from bambu_auto.services.mesh.branding import _mask_to_polygons, _polygons_to_mesh


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
    sil_mask = (sil.astype("uint8")) * 255
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
) -> list[str]:
    """전경 색을 k-means로 분석해 색 영역별 파트를 마스크에서 직접 압출.
    색상별 STL(_c1..) + 컬러 GLB/OBJ + palette.json 생성. 팔레트 hex 반환.

    feature: {"kind":"hole"} 또는 {"kind":"cavity","d":..,"h":..} → 각 파트에 적용.
    """
    import json

    import cv2
    import numpy as np
    import trimesh
    from PIL import Image

    img = Image.open(image_path).convert("RGBA")
    arr = np.array(img)
    alpha = arr[:, :, 3]
    rgb = arr[:, :, :3]
    gray = np.array(img.convert("L"))
    sil = (gray < 245) if int(alpha.min()) == 255 else (alpha > 128)
    if not sil.any():
        return []

    H, W = sil.shape
    scale = size_mm / max(H, W)

    # 전경 픽셀만으로 대표색 추출 (배경 제외 → 탁한 팔레트 방지)
    fg = rgb[sil].astype(float)
    centers, _ = _kmeans(fg, n_colors)
    if len(centers) == 0:
        return []
    # 거의 같은 색 병합 (perceptual 거리 < 28)
    keep: list = []
    for c in centers:
        if all(np.sqrt(((c - k) ** 2).sum()) > 28 for k in keep):
            keep.append(c)
    palette = np.array(keep)

    # 전체 픽셀을 팔레트 최근접으로 라벨
    flat_rgb = rgb.reshape(-1, 3).astype(float)
    lab = np.argmin(((flat_rgb[:, None, :] - palette[None, :, :]) ** 2).sum(2),
                    axis=1).reshape(H, W)

    # 전체 실루엣 bounds (feature 위치 계산용) — 실루엣 압출로 산출
    sil_polys = _mask_to_polygons((sil.astype("uint8")) * 255, scale)
    if not sil_polys:
        return []
    base = _polygons_to_mesh(sil_polys, thickness_mm)
    if base is None:
        return []
    bmin, bmax = base.bounds

    def feat_cyl():
        if not feature:
            return None
        cx = (bmin[0] + bmax[0]) / 2
        if feature.get("kind") == "hole":
            d = 5.0
            top_y = bmax[1] - 4.0 - d / 2
            cyl = trimesh.creation.cylinder(radius=d / 2,
                                            height=thickness_mm + 2)
            cyl.apply_translation([cx, top_y, (bmin[2] + bmax[2]) / 2])
            return cyl
        if feature.get("kind") == "cavity":
            d = float(feature.get("d", 5)) + 0.4
            h = float(feature.get("h", 2)) + 0.2
            cy = (bmin[1] + bmax[1]) / 2
            cyl = trimesh.creation.cylinder(radius=d / 2, height=h)
            cyl.apply_translation([cx, cy, bmin[2] + h / 2 - 0.05])
            return cyl
        return None

    fcyl = feat_cyl()

    def sub_feat(part):
        if fcyl is None:
            return part
        for eng in ("manifold", None):
            try:
                kw = {"engine": eng} if eng else {}
                out = trimesh.boolean.difference([part, fcyl.copy()], **kw)
                if out is not None and not out.is_empty:
                    return out
            except Exception:  # noqa: BLE001
                continue
        return part

    palette_hex: list[str] = []
    combined = []
    for i, color in enumerate(palette):
        mask_i = ((lab == i) & sil).astype("uint8") * 255
        if int(mask_i.max()) == 0:
            continue
        # 노이즈 정리(작은 점 제거)
        mask_i = cv2.morphologyEx(mask_i, cv2.MORPH_OPEN,
                                  np.ones((3, 3), np.uint8))
        polys = _mask_to_polygons(mask_i, scale)
        if not polys:
            continue
        part = _polygons_to_mesh(polys, thickness_mm)
        if part is None:
            continue
        part = sub_feat(part)
        rgbc = tuple(int(x) for x in color)
        n = len(palette_hex) + 1
        part.visual = trimesh.visual.ColorVisuals(
            face_colors=np.tile([*rgbc, 255], (len(part.faces), 1)))
        part.export(ddir / f"{stem}_c{n}.stl")
        combined.append(part)
        palette_hex.append("#%02x%02x%02x" % rgbc)

    if not combined:
        return []
    scene = trimesh.util.concatenate(combined)
    scene.export(ddir / f"{stem}.glb")
    scene.export(ddir / f"{stem}.obj")
    (ddir / f"{stem}.palette.json").write_text(
        json.dumps({"colors": palette_hex}))
    return palette_hex
