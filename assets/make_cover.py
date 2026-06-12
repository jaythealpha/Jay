#!/usr/bin/env python3
"""itch.io 커버 이미지 생성기 — 630x500 픽셀 아트 커버.

게임(v2.html)의 픽셀맵 스프라이트를 그대로 가져와 그리고,
GNU Unifont(비트맵 스타일)로 한글 타이틀을 얹는다.
사용: python3 assets/make_cover.py  →  assets/cover.png
"""
from PIL import Image, ImageDraw, ImageFont

W, H = 630, 500
UNIFONT = "/usr/share/fonts/opentype/unifont/unifont.otf"

PAL = {
    "K": "#20223a", "S": "#f2c9a0", "B": "#3d5a99", "D": "#2d4377",
    "W": "#f5f5f5", "T": "#e94560", "E": "#6b4f3a", "F": "#54392a",
    "G": "#101020", "Y": "#ffd166", "C": "#7a4a2b", "M": "#c0c8e0",
    "U": "#4cc9f0", "N": "#3ee06f",
}

RUN1 = [
    "................",
    ".....KKKKKK.....",
    "....KKKKKKKK....",
    "....KSSSSSSK....",
    "....KSKSSKSK....",
    "....KSSSSSSK....",
    ".....SSSSSS.....",
    "....BBBWWBBB....",
    "...BBBWTTWBBB...",
    "...BSBWTTWBSB...",
    "...BBBWWWWBBB...",
    "....BBBBBBBB....",
    "....DDD..DDD....",
    "...DDD....DDD...",
    "..KKK......KKK..",
    "................",
]
BOSS = [
    "................",
    ".....KKKKKK.....",
    "....KKKKKKKK....",
    "....KSSSSSSK....",
    "....KGGSSGGK....",
    "....KSSSSSSK....",
    "....KSKKKKSK....",
    ".....SSSSSS.....",
    "....EEEEEEEE....",
    "...EEEWWWWEEE...",
    "..EEEWWTTWWEEE..",
    "..EEEWWTTWWEEE..",
    "..EEEWWWWWWEEE..",
    "..EE.WWWWWW.EE..",
    "..SS.FFFFFF.SS..",
    ".....FFFFFF.....",
    ".....FF..FF.....",
    ".....FF..FF.....",
    "....KKK..KKK....",
    "................",
]
COFFEE = [
    "..MMMM..",
    ".MCCCCM.",
    ".WWWWWW.",
    ".WWWWWWM",
    ".WWWWWWM",
    "..WWWW..",
    "..KKKK..",
]
KAKAO = [
    ".YYYYYYYYYYY.",
    "YYYYYYYYYYYYY",
    "YYKYYKYYKYYYY",
    "YYYYYYYYYYYYY",
    ".YYYYYYYYYYY.",
    "...YY........",
    "..YY.........",
]


def blit(draw, rows, x0, y0, scale):
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            col = PAL.get(ch)
            if col:
                draw.rectangle(
                    [x0 + x * scale, y0 + y * scale,
                     x0 + (x + 1) * scale - 1, y0 + (y + 1) * scale - 1],
                    fill=col)


def pixel_text(img, text, cx, y, size, color, scale=3):
    """Unifont로 작게 렌더한 뒤 정수 배율로 확대해 또렷한 픽셀 글자를 만든다."""
    font = ImageFont.truetype(UNIFONT, size)
    tmp = Image.new("RGBA", (W, size * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(tmp)
    d.text((0, 0), text, font=font, fill=color)
    box = tmp.getbbox()
    if not box:
        return
    glyph = tmp.crop(box)
    glyph = glyph.resize((glyph.width * scale, glyph.height * scale), Image.NEAREST)
    img.paste(glyph, (cx - glyph.width // 2, y), glyph)


def main():
    img = Image.new("RGB", (W, H), "#12141d")
    d = ImageDraw.Draw(img)

    # 벽 + 창문(야경)
    d.rectangle([0, 0, W, 384], fill="#1a1d2e")
    for wx in range(20, W, 200):
        d.rectangle([wx, 40, wx + 150, 150], fill="#10121f")
        d.rectangle([wx + 8, 48, wx + 142, 142], fill="#0a1530")
        for i in range(14):
            sx = wx + 16 + (i * 37) % 115
            sy = 60 + (i * 23) % 70
            if i % 3:
                d.rectangle([sx, sy, sx + 5, sy + 5], fill="#ffd166")
        d.rectangle([wx + 71, 48, wx + 79, 142], fill="#2a2f4a")

    # 바닥
    d.rectangle([0, 384, W, H], fill="#242842")
    for fx in range(0, W, 60):
        d.rectangle([fx, 384, fx + 30, H], fill="#1d2138")
    d.rectangle([0, 384, W, 388], fill="#343a55")

    # 스프라이트: 부장님(추격) ← 김대리(질주) ← 커피/카톡
    blit(d, BOSS, 60, 384 - 20 * 9, 9)
    blit(d, RUN1, 280, 384 - 16 * 11, 11)
    blit(d, COFFEE, 500, 240, 7)
    blit(d, KAKAO, 480, 130, 6)
    # 스피드 라인
    for ly in (250, 290, 330):
        d.rectangle([180, ly, 270, ly + 4], fill="#343a55")

    # 타이틀
    pixel_text(img, "직장인 러너", W // 2, 40, 32, "#ffd166", scale=3)
    pixel_text(img, "─ 출근 대작전 ─", W // 2, 160, 16, "#4cc9f0", scale=3)
    pixel_text(img, "OFFICE RUNNER · 16-BIT SURVIVAL", W // 2, 440, 16, "#c0c8e0", scale=2)

    img.save("assets/cover.png")
    # itch.io 최소 커버(315x250)용 축소판
    img.resize((315, 250), Image.NEAREST).save("assets/cover_small.png")
    print("saved: assets/cover.png (630x500), assets/cover_small.png (315x250)")


if __name__ == "__main__":
    main()
