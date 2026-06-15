"""CAD 스펙 소스 어댑터.

자연어 설명 + (선택) 명시 치수 dict → Claude가 build123d 코드를 생성하기 좋게
정규화된 단일 프롬프트로 묶음.

예:
    CadSpecAdapter(
        prompt="MX 호환 1u 키캡, 위에 'A' 음각",
        params={"cap_mm": 18, "height_mm": 8, "letter": "A"},
    )
"""

from __future__ import annotations

from pathlib import Path

from bambu_auto.adapters.sources.base import (
    PreparedSource,
    SourceAdapter,
    hash_text,
)


class CadSpecAdapter(SourceAdapter):
    """자연어 + 치수 → CAD 트랙용 PreparedSource(kind='cad').

    Meshy를 우회하고 Claude+build123d로 결정적 watertight STL 생성에 사용.
    """

    def __init__(
        self,
        prompt: str,
        params: dict[str, float | int | str] | None = None,
    ) -> None:
        self.prompt = prompt.strip()
        if not self.prompt:
            raise ValueError("CAD 스펙(자연어)이 비어있음")
        self.params = dict(params or {})

    def prepare(self, work_dir: Path) -> PreparedSource:
        work_dir.mkdir(parents=True, exist_ok=True)
        full = self._compose_prompt()
        return PreparedSource(
            kind="cad",
            input_hash=hash_text(full),
            prompt=full,
            cad_params=self.params or None,
        )

    def _compose_prompt(self) -> str:
        if not self.params:
            return self.prompt
        lines = [self.prompt, "", "Explicit dimensions (use exactly):"]
        for k, v in self.params.items():
            lines.append(f"- {k} = {v}")
        return "\n".join(lines)
