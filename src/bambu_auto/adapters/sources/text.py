from __future__ import annotations

from pathlib import Path

from bambu_auto.adapters.sources.base import PreparedSource, SourceAdapter, hash_text


class TextSourceAdapter(SourceAdapter):
    """텍스트 프롬프트 소스. 이미지 없이 문장만으로 3D 생성.

    예: "요기보 캐릭터가 하트를 든 키링, 단순한 형태, 두꺼운 벽".
    """

    def __init__(self, prompt: str) -> None:
        self.prompt = prompt.strip()
        if not self.prompt:
            raise ValueError("프롬프트가 비어있음")

    def prepare(self, work_dir: Path) -> PreparedSource:
        work_dir.mkdir(parents=True, exist_ok=True)
        return PreparedSource(
            kind="text",
            input_hash=hash_text(self.prompt),
            prompt=self.prompt,
        )
