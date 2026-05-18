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
            ext = Path(self.source.split("?")[0]).suffix.lower() or ".jpg"
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
        try:
            from rembg import remove  # type: ignore
        except ImportError:
            return img_path  # preprocess extra 미설치 — 원본 사용
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
