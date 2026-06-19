"""결정적 이미지 정규화 (3D 생성기 입력 준비).

원본 이미지를 그대로 Meshy에 던지면 사진/스크린샷/저해상도/측면뷰가 들어왔을 때
"추측"으로 채워 넣어 결과가 깨짐. 이 단계는 Meshy Creative Lab의
'Image Enhancement' 권장사항과 동일한 조건을 보장:
- 단일 객체 중심 정렬
- 정사각 캔버스 + 여백
- 1040+ 해상도 (Meshy 권장)
- 깨끗한 대비

비용 0 · 항상 결정적 · 외부 의존 없음(rembg는 image adapter에서 이미 처리).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class NormalizeResult:
    path: Path                  # 출력 파일
    size_in: tuple[int, int]    # 입력 크기 (w, h)
    size_out: tuple[int, int]   # 출력 크기 (w, h)
    has_alpha: bool             # 입력에 alpha 채널 존재
    cropped: bool               # alpha bbox로 crop 실행 여부
    upscaled: bool              # target_size까지 확대 여부
    notes: list[str] = field(default_factory=list)


def normalize_image(
    src: Path,
    dest: Path,
    *,
    target_size: int = 1024,
    pad_ratio: float = 0.08,
    autocontrast: bool = True,
    binary_alpha: bool = False,
    alpha_threshold: int = 128,
) -> NormalizeResult:
    """src 이미지를 3D 생성기에 적합한 정사각 PNG로 정규화해 dest에 저장.

    target_size: 출력 한 변의 픽셀 수 (Meshy 권장 1040px↑).
    pad_ratio: 객체 경계 주위 여백 비율 (0.08 = 캔버스 변의 8%).
    autocontrast: 자동 대비/밝기 정규화 (RGB 채널만, alpha 보존).
    binary_alpha: True면 부분 투명을 0/255로 이분화 (메쉬 경계 안정성↑).
    alpha_threshold: binary_alpha 사용 시 임계값.
    """
    try:
        from PIL import Image, ImageOps
    except ImportError as e:
        raise RuntimeError("Pillow 필요 — `uv sync` 실행") from e

    src = Path(src)
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)

    notes: list[str] = []
    img = Image.open(src)
    size_in = img.size
    has_alpha = img.mode in ("RGBA", "LA") or "A" in img.getbands()

    # 1) RGBA로 통일 — 이후 합성·crop·resize 일관 처리
    if img.mode != "RGBA":
        img = img.convert("RGBA")

    # 2) alpha 기반 bbox crop: 배경 제거된 입력이라면 객체 외곽만 남김
    cropped = False
    if has_alpha:
        # 살짝 alpha 마스크를 inflate해서 thin edge가 잘려나가지 않게
        alpha = img.split()[-1]
        bbox = alpha.getbbox()
        if bbox and (
            bbox[2] - bbox[0] < img.size[0] or bbox[3] - bbox[1] < img.size[1]
        ):
            img = img.crop(bbox)
            cropped = True
            notes.append("alpha-bbox-crop")

    # 3) 정사각 캔버스 + 패딩
    w, h = img.size
    side = max(w, h)
    pad = int(side * pad_ratio)
    canvas_side = side + 2 * pad
    bg = (0, 0, 0, 0) if has_alpha else (255, 255, 255, 255)
    canvas = Image.new("RGBA", (canvas_side, canvas_side), bg)
    ox = (canvas_side - w) // 2
    oy = (canvas_side - h) // 2
    canvas.paste(img, (ox, oy), img if has_alpha else None)
    img = canvas

    # 4) 표준 해상도로 스케일 (Meshy 권장 1040+)
    upscaled = False
    if img.size[0] != target_size:
        if img.size[0] < target_size:
            upscaled = True
            notes.append(f"upscale {img.size[0]}→{target_size}")
        img = img.resize((target_size, target_size), Image.LANCZOS)

    # 5) autocontrast — alpha 보존하면서 RGB만 채널별 stretch
    if autocontrast:
        if has_alpha:
            r, g, b, a = img.split()
            rgb = Image.merge("RGB", (r, g, b))
            rgb = ImageOps.autocontrast(rgb, cutoff=1)
            r, g, b = rgb.split()
            img = Image.merge("RGBA", (r, g, b, a))
        else:
            img = ImageOps.autocontrast(img.convert("RGB"), cutoff=1).convert("RGBA")
        notes.append("autocontrast")

    # 6) alpha 이분화 (옵션) — 메쉬 generation이 부분 투명을 잘못 해석하는 경우 방지
    if binary_alpha and has_alpha:
        r, g, b, a = img.split()
        a = a.point(lambda v, t=alpha_threshold: 255 if v >= t else 0)
        img = Image.merge("RGBA", (r, g, b, a))
        notes.append("binary-alpha")

    # 7) 저장 — 항상 PNG (alpha 보존)
    img.save(dest, "PNG", optimize=True)
    return NormalizeResult(
        path=dest,
        size_in=size_in,
        size_out=img.size,
        has_alpha=has_alpha,
        cropped=cropped,
        upscaled=upscaled,
        notes=notes,
    )
