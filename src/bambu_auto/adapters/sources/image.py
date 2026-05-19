from __future__ import annotations

import shutil
from pathlib import Path

import httpx

from bambu_auto.adapters.sources.base import PreparedSource, SourceAdapter, hash_bytes

VALID_EXT = {".jpg", ".jpeg", ".png", ".webp"}


class ImageSourceAdapter(SourceAdapter):
    """단일 이미지 소스. 로컬 경로 또는 URL 지원.

    배경 제거(rembg)는 선택. preprocess extra 미설치 시 원본 그대로 사용.
    """

    def __init__(self, source: str, remove_bg: bool = True) -> None:
        self.source = source
        self.remove_bg = remove_bg

    def _fetch(self, work_dir: Path) -> Path:
        if self.source.startswith(("http://", "https://")):
            r = httpx.get(self.source, timeout=60, follow_redirects=True)
            r.raise_for_status()
            ctype = r.headers.get("content-type", "").split(";")[0].strip().lower()
            if not ctype.startswith("image/"):
                raise ValueError(
                    f"URL이 이미지가 아닙니다 (content-type={ctype or 'unknown'}). "
                    f"상품 '페이지' URL이 아니라 이미지 파일 URL(.jpg/.png)을 주세요. "
                    f"상품 페이지에서 이미지를 자동 추출하려면 web_url 소스(Phase 3)가 필요합니다."
                )
            ext_map = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
            ext = ext_map.get(ctype) or Path(self.source.split("?")[0]).suffix.lower()
            if ext not in VALID_EXT:
                ext = ".jpg"
            dst = work_dir / f"input{ext}"
            dst.write_bytes(r.content)
            return dst

        src = Path(self.source).expanduser()
        if not src.exists():
            raise FileNotFoundError(f"Image not found: {src}")
        if src.suffix.lower() not in VALID_EXT:
            raise ValueError(f"Unsupported image type {src.suffix}; use {sorted(VALID_EXT)}")
        dst = work_dir / f"input{src.suffix.lower()}"
        shutil.copy2(src, dst)
        return dst

    def _strip_background(self, img_path: Path) -> Path:
        """배경·인물 제거. rembg가 사진의 주요 물체만 남김.
        (사람이 화면을 지배하면 사람이 남을 수 있음 — 상품 중심 사진 권장)"""
        try:
            from rembg import remove  # type: ignore
        except ImportError as e:
            raise RuntimeError(
                "배경 제거에는 rembg 필요. `uv sync` 재실행 (핵심 의존성)."
            ) from e
        out = img_path.with_name("input_nobg.png")
        out.write_bytes(remove(img_path.read_bytes()))
        return out

    def prepare(self, work_dir: Path) -> PreparedSource:
        work_dir.mkdir(parents=True, exist_ok=True)
        img = self._fetch(work_dir)
        if self.remove_bg:
            img = self._strip_background(img)
        return PreparedSource(
            kind="image",
            input_hash=hash_bytes(img.read_bytes()),
            image_paths=[img],
        )
