from __future__ import annotations

from pathlib import Path

from bambu_auto.adapters.sources.base import PreparedSource, SourceAdapter, hash_bytes
from bambu_auto.adapters.sources.image import ImageSourceAdapter


class MultiImageSourceAdapter(SourceAdapter):
    """여러 장(1~4) 소스. 같은 물체의 다른 각도 → Meshy multi-image.

    각 입력을 ImageSourceAdapter로 개별 준비(다운로드/배경제거) 후 묶음.
    단일 이미지 대비 뒷면·측면 정확도가 크게 향상.
    """

    def __init__(self, sources: list[str], remove_bg: bool = False) -> None:
        if not 1 <= len(sources) <= 4:
            raise ValueError(f"multi-image는 1~4장 필요 (받음: {len(sources)})")
        self.sources = sources
        self.remove_bg = remove_bg

    def prepare(self, work_dir: Path) -> PreparedSource:
        work_dir.mkdir(parents=True, exist_ok=True)
        paths: list[Path] = []
        for i, src in enumerate(self.sources):
            sub = ImageSourceAdapter(src, remove_bg=self.remove_bg)
            prepared = sub.prepare(work_dir / f"img{i}")
            assert prepared.image_paths
            paths.append(prepared.image_paths[0])
        combined = hash_bytes(*[p.read_bytes() for p in paths])
        return PreparedSource(kind="multi_image", input_hash=combined,
                              image_paths=paths)
