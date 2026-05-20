"""모델 바닥면(빌드 플레이트 접촉면)에 텍스트/아이콘 디보스(deboss).

전략: 텍스트/심볼을 고해상도 binary mask로 렌더 → OpenCV로 contour
(외곽선+구멍 계층) 추출 → shapely polygon → trimesh로 박판 extrusion
→ 모델 바닥에 boolean subtract.

디보스(파임)가 FDM에서 가장 깔끔: 첫 레이어가 평탄·정확, 오버행 없음.
"""

from __future__ import annotations

from pathlib import Path

# NFC 태그가 트리거 가능한 액션을 표상하는 단문자/단어 (모노크롬 가용)
ICON_LABELS: dict[str, str] = {
    "wifi": "Wi-Fi",
    "nfc": "NFC",
    "phone": "☎",
    "mobile": "📱",
    "email": "✉",
    "bluetooth": "Bluetooth",
}


def _find_font(size: int):
    from PIL import ImageFont

    cands = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",  # macOS
        "/System/Library/Fonts/Helvetica.ttc",                 # macOS
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",          # macOS Korean
        "/System/Library/Fonts/Apple Symbols.ttf",             # macOS symbols
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
    ]
    for fp in cands:
        if Path(fp).exists():
            try:
                return ImageFont.truetype(fp, size)
            except Exception:  # noqa: BLE001
                continue
    return ImageFont.load_default()


def _render_mask(text: str, px_height: int = 240, padding: int = 12):
    """텍스트를 흰글자/검은배경 binary mask로 렌더 (numpy uint8)."""
    import numpy as np
    from PIL import Image, ImageDraw

    font = _find_font(px_height)
    probe = Image.new("L", (10, 10))
    bb = ImageDraw.Draw(probe).textbbox((0, 0), text, font=font)
    w = max(1, bb[2] - bb[0]) + 2 * padding
    h = max(1, bb[3] - bb[1]) + 2 * padding
    img = Image.new("L", (w, h), 0)
    ImageDraw.Draw(img).text((padding - bb[0], padding - bb[1]),
                             text, fill=255, font=font)
    return np.array(img)


def _mask_to_polygons(mask, scale_mm_per_px: float) -> list:
    """OpenCV로 contour 계층 추출 → shapely Polygon 리스트(holes 포함)."""
    import cv2
    from shapely.geometry import Polygon

    contours, hierarchy = cv2.findContours(
        (mask > 127).astype("uint8") * 255,
        cv2.RETR_CCOMP, cv2.CHAIN_APPROX_TC89_KCOS)
    if not contours:
        return []
    polys: list = []
    h_arr = hierarchy[0] if hierarchy is not None else []
    height_px = mask.shape[0]

    def to_xy(cnt):
        # OpenCV: y는 아래로 증가. mm 변환 + y 뒤집기(모델 좌표계).
        return [(float(p[0][0]) * scale_mm_per_px,
                 float(height_px - p[0][1]) * scale_mm_per_px) for p in cnt]

    # CCOMP: 외곽(부모 -1) + 구멍(부모 != -1) 2단 계층
    for i, cnt in enumerate(contours):
        if len(cnt) < 3:
            continue
        parent = h_arr[i][3] if i < len(h_arr) else -1
        if parent != -1:
            continue  # 구멍은 부모와 함께 처리
        outer = to_xy(cnt)
        # 이 외곽의 구멍들
        holes = [to_xy(contours[j]) for j, hv in enumerate(h_arr)
                 if hv[3] == i and len(contours[j]) >= 3]
        try:
            poly = Polygon(outer, holes=holes)
            if poly.is_valid and poly.area > 0.1:
                polys.append(poly)
        except Exception:  # noqa: BLE001
            continue
    return polys


def _polygons_to_mesh(polys: list, depth_mm: float):
    """polygons → 두께 depth_mm 압출 → 합쳐서 trimesh.Trimesh."""
    import trimesh

    parts = []
    for p in polys:
        try:
            m = trimesh.creation.extrude_polygon(p, depth_mm)
            if m is not None and not m.is_empty:
                parts.append(m)
        except Exception:  # noqa: BLE001
            continue
    if not parts:
        return None
    return trimesh.util.concatenate(parts)


def add_bottom_branding(
    stl_in: Path, stl_out: Path, *,
    content: str,
    size_mm: float = 25.0,
    depth_mm: float = 0.6,
) -> dict:
    """모델 바닥면에 텍스트/심볼을 디보스. 성공 시 {ok,method}.

    - content: 텍스트(자유) 또는 ICON_LABELS의 키 ('wifi' 등)
    - size_mm: 디보스 폭(최대 치수)
    - depth_mm: 파임 깊이 (0.4~1.0mm 권장)
    """
    import numpy as np
    import trimesh

    text = ICON_LABELS.get(content, content)
    mask = _render_mask(text)
    if mask.max() == 0:
        return {"ok": False, "method": "empty_mask"}

    # mask를 size_mm 폭에 맞도록 스케일
    w_px, h_px = mask.shape[1], mask.shape[0]
    longer = max(w_px, h_px)
    scale = size_mm / longer
    polys = _mask_to_polygons(mask, scale)
    if not polys:
        return {"ok": False, "method": "no_polygons"}

    # 디보스용 stamp: depth보다 살짝 두껍게 만들어 확실히 자르도록
    stamp = _polygons_to_mesh(polys, depth_mm + 0.4)
    if stamp is None:
        return {"ok": False, "method": "extrude_failed"}

    mesh = trimesh.load(stl_in, force="mesh")
    bmin, bmax = mesh.bounds
    cx = (bmin[0] + bmax[0]) / 2
    cy = (bmin[1] + bmax[1]) / 2

    # stamp는 z=[0, depth+0.4]. 바닥면이 z=bmin[2]에 닿도록 위치
    # stamp 중심도 모델 중심 (cx, cy)에 맞춤
    sb_min, sb_max = stamp.bounds
    sx = (sb_min[0] + sb_max[0]) / 2
    sy = (sb_min[1] + sb_max[1]) / 2
    stamp.apply_translation([cx - sx, cy - sy,
                              bmin[2] - 0.2])  # 0.2mm 내려 확실한 cut

    # boolean difference (디보스)
    for engine in ("manifold", None):
        try:
            kw = {"engine": engine} if engine else {}
            out = trimesh.boolean.difference([mesh, stamp], **kw)
            if out is not None and not out.is_empty:
                out.export(stl_out)
                return {"ok": True, "method": f"deboss/{engine or 'default'}"}
        except Exception:  # noqa: BLE001
            continue
    return {"ok": False, "method": "boolean_failed"}
