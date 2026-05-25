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
