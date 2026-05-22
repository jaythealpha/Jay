#!/usr/bin/env python3
"""
이미지 위에 한국어 후킹 카피를 합성한다.
인스타 티저는 '1초 안에 읽히는 한 줄'이 핵심이므로,
상단에 가독성 높은 큰 텍스트 + 가독 그라데이션을 깐다.

Pillow 필요. 한글 폰트 경로는 환경변수 KOREAN_FONT 로 지정 가능.
"""
import os

# 흔한 한글 폰트 후보(환경에 맞게 추가)
_FONT_CANDIDATES = [
    os.environ.get("KOREAN_FONT", ""),
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "C:/Windows/Fonts/malgunbd.ttf",
]


def _find_font(size):
    from PIL import ImageFont
    for path in _FONT_CANDIDATES:
        if path and os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:  # noqa: BLE001
                continue
    return ImageFont.load_default()


def _wrap(text, max_chars):
    words, lines, cur = text.split(" "), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > max_chars and cur:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines


def apply(image_path, text, position="top"):
    from PIL import Image, ImageDraw
    img = Image.open(image_path).convert("RGBA")
    W, H = img.size
    draw = ImageDraw.Draw(img)

    font_size = max(36, W // 16)
    font = _find_font(font_size)
    lines = _wrap(text, max_chars=max(10, W // (font_size // 2)))

    line_h = int(font_size * 1.25)
    block_h = line_h * len(lines) + int(font_size * 0.8)

    # 가독성 그라데이션 바
    grad = Image.new("RGBA", (W, block_h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    for y in range(block_h):
        a = int(150 * (1 - y / block_h)) if position == "top" else int(150 * (y / block_h))
        gd.line([(0, y), (W, y)], fill=(0, 0, 0, a))
    y0 = 0 if position == "top" else H - block_h
    img.alpha_composite(grad, (0, y0))

    ty = y0 + int(font_size * 0.4)
    for ln in lines:
        bbox = draw.textbbox((0, 0), ln, font=font)
        tw = bbox[2] - bbox[0]
        tx = (W - tw) // 2
        # 외곽선
        for dx, dy in [(-2, 0), (2, 0), (0, -2), (0, 2)]:
            draw.text((tx + dx, ty + dy), ln, font=font, fill=(0, 0, 0, 200))
        draw.text((tx, ty), ln, font=font, fill=(255, 255, 255, 255))
        ty += line_h

    img.convert("RGB").save(image_path)
    return image_path


if __name__ == "__main__":
    import sys
    apply(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "테스트 후킹 카피")
