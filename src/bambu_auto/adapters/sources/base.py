from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass
class PreparedSource:
    """생성 단계로 넘길 준비가 끝난 입력.

    - kind: 'image' | 'multi_image' | 'text' | 'cad'
    - image_paths: 로컬에 준비된 이미지 경로들 (image/multi_image 일 때)
    - prompt: 텍스트 프롬프트 (text/cad 일 때)
    - cad_params: 자연어 외 명시 치수·옵션 (cad 일 때, 예 {"width_mm": 18})
    - input_hash: 캐시 dedup 키 (동일 입력 재처리 방지)
    """

    kind: str
    input_hash: str
    image_paths: list[Path] | None = None
    prompt: str | None = None
    cad_params: dict[str, float | int | str] | None = None


class SourceAdapter(Protocol):
    """모든 소스 어댑터 공통 인터페이스."""

    def prepare(self, work_dir: Path) -> PreparedSource:
        """원본 소스를 Meshy 호출 가능한 형태로 준비. work_dir에 산출물 저장."""
        ...


def hash_bytes(*chunks: bytes) -> str:
    h = hashlib.sha256()
    for c in chunks:
        h.update(c)
    return h.hexdigest()[:16]


def hash_text(text: str) -> str:
    return hash_bytes(text.strip().encode("utf-8"))
