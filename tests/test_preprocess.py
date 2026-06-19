"""이미지 전처리(normalize · vision_assess) 단위 + 파이프라인 통합 검증."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PIL import Image

from bambu_auto.services.preprocess.normalize import normalize_image
from bambu_auto.services.preprocess import vision_assess


# ───────── normalize ─────────

def _save(img: Image.Image, p: Path) -> Path:
    img.save(p)
    return p


def test_normalize_pads_to_square_and_target_size(tmp_path: Path) -> None:
    src = _save(Image.new("RGB", (300, 100), (200, 50, 50)), tmp_path / "i.png")
    r = normalize_image(src, tmp_path / "o.png", target_size=512)
    out = Image.open(r.path)
    assert out.size == (512, 512)
    assert r.size_in == (300, 100)
    assert r.size_out == (512, 512)


def test_normalize_alpha_bbox_crop(tmp_path: Path) -> None:
    canvas = Image.new("RGBA", (300, 300), (0, 0, 0, 0))
    canvas.paste(Image.new("RGBA", (60, 60), (0, 200, 0, 255)), (100, 120))
    src = _save(canvas, tmp_path / "i.png")
    r = normalize_image(src, tmp_path / "o.png", target_size=256)
    assert r.has_alpha
    assert r.cropped
    out = Image.open(r.path)
    assert out.size == (256, 256)
    assert out.mode == "RGBA"


def test_normalize_upscale_flagged(tmp_path: Path) -> None:
    src = _save(Image.new("RGB", (80, 80), (128, 128, 128)), tmp_path / "i.png")
    r = normalize_image(src, tmp_path / "o.png", target_size=1024)
    assert r.upscaled
    assert any("upscale" in n for n in r.notes)


def test_normalize_binary_alpha_threshold(tmp_path: Path) -> None:
    # Gradient alpha: 0..255 across X
    canvas = Image.new("RGBA", (256, 256), (255, 0, 0, 0))
    for x in range(256):
        for y in range(256):
            canvas.putpixel((x, y), (255, 0, 0, x))
    src = _save(canvas, tmp_path / "i.png")
    r = normalize_image(
        src, tmp_path / "o.png", target_size=128, binary_alpha=True,
        alpha_threshold=128,
    )
    out = Image.open(r.path)
    alphas = set(out.split()[-1].getdata())
    assert alphas <= {0, 255}, f"부분 투명 잔존: {sorted(alphas)[:10]}"


def test_normalize_autocontrast_brightens_dim_image(tmp_path: Path) -> None:
    # Very dim narrow-range image
    img = Image.new("RGB", (200, 200), (20, 20, 20))
    src = _save(img, tmp_path / "dim.png")
    r = normalize_image(src, tmp_path / "out.png", target_size=200, autocontrast=True)
    out = Image.open(r.path).convert("RGB")
    # autocontrast가 cutoff=1로 호출되므로 평균 픽셀 값이 의미있게 변함
    avg = sum(sum(p) / 3 for p in out.getdata()) / (200 * 200)
    assert avg != 20  # 변화 확인 (구체적 값은 PIL 버전에 따라 다름)


# ───────── vision_assess ─────────

def _mock_anthropic(json_obj: dict | str):
    """messages.create가 JSON을 텍스트 블록으로 반환하도록 mock 구성."""
    if isinstance(json_obj, dict):
        text = json.dumps(json_obj)
    else:
        text = json_obj
    client = MagicMock()
    msg = MagicMock()
    block = MagicMock()
    block.type = "text"
    block.text = text
    msg.content = [block]
    client.messages.create.return_value = msg
    fake = MagicMock()
    fake.Anthropic.return_value = client
    return fake


def test_assess_parses_clean_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    img = tmp_path / "p.png"
    Image.new("RGB", (32, 32), (200, 200, 200)).save(img)
    fake = _mock_anthropic({
        "score": 8.4, "category": "character",
        "issues": [], "enhanced_prompt": "front-facing chibi figure",
    })
    monkeypatch.setitem(__import__("sys").modules, "anthropic", fake)
    a = vision_assess.assess_image(img, api_key="sk-x")
    assert a.ok
    assert a.score == pytest.approx(8.4)
    assert a.category == "character"
    assert a.recommend == "proceed"
    assert a.error is None


def test_assess_warn_when_below_threshold(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    img = tmp_path / "p.png"
    Image.new("RGB", (32, 32), (100, 100, 100)).save(img)
    fake = _mock_anthropic({
        "score": 4.5, "category": "product",
        "issues": ["cluttered background"], "enhanced_prompt": "single product",
    })
    monkeypatch.setitem(__import__("sys").modules, "anthropic", fake)
    a = vision_assess.assess_image(img, api_key="sk-x")
    assert a.recommend == "warn"
    assert "cluttered background" in a.issues
    assert a.ok  # warn은 진행 가능


def test_assess_block_when_severely_low(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    img = tmp_path / "p.png"
    Image.new("RGB", (32, 32), (50, 50, 50)).save(img)
    fake = _mock_anthropic({
        "score": 1.0, "category": "unknown",
        "issues": ["text only"], "enhanced_prompt": "",
    })
    monkeypatch.setitem(__import__("sys").modules, "anthropic", fake)
    a = vision_assess.assess_image(img, api_key="sk-x", block_below=3)
    assert a.recommend == "block"
    assert not a.ok


def test_assess_extracts_json_from_prose(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    img = tmp_path / "p.png"
    Image.new("RGB", (32, 32), (200, 200, 200)).save(img)
    # 모델이 잡설을 섞었을 때도 첫 JSON 객체 추출
    fake = _mock_anthropic(
        'Sure, here is the JSON:\n{"score":7,"category":"toy",'
        '"issues":[],"enhanced_prompt":"a toy car"}\nDone.',
    )
    monkeypatch.setitem(__import__("sys").modules, "anthropic", fake)
    a = vision_assess.assess_image(img, api_key="sk-x")
    assert a.ok and a.score == 7 and a.category == "toy"


def test_assess_missing_api_key_returns_error(tmp_path: Path) -> None:
    img = tmp_path / "p.png"
    Image.new("RGB", (32, 32), (200, 200, 200)).save(img)
    a = vision_assess.assess_image(img, api_key="")
    assert a.error is not None
    assert a.recommend == "warn"


def test_assess_missing_file_returns_error(tmp_path: Path) -> None:
    a = vision_assess.assess_image(tmp_path / "nope.png", api_key="sk-x")
    assert a.error is not None
    assert a.recommend == "block"
