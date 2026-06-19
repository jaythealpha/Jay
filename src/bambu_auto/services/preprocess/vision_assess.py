"""Claude Vision으로 이미지가 3D 생성에 얼마나 적합한지 평가.

판단 항목 (JSON 반환):
  - score: 0~10 (10=완벽한 단일 객체 정면, 0=다중 객체·심하게 가려짐)
  - category: character | product | toy | tool | flat_art | unknown
  - issues: 잘못된 점 (다중 객체, 측면뷰, 잘림 등)
  - enhanced_prompt: Meshy 텍스트 강화 또는 retexture/text-to-3d 백업 경로용
  - recommend: proceed | warn | block (점수와 임계치로 결정)

비용: 작업당 ~$0.005~0.01 (sonnet 기준, 이미지 1장).
모델은 호출자 지정 가능; 기본은 비용/품질 균형의 sonnet.
"""

from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass, field
from pathlib import Path


SYSTEM_PROMPT = (
    "You evaluate input images for AI 3D model generation (Meshy / FDM 3D print). "
    "Score how suitable the image is and give a generation-ready prompt.\n\n"
    "Reply with EXACTLY one JSON object, no prose, no code fence. Schema:\n"
    "{\n"
    '  "score": <number 0-10>,\n'
    '  "category": "character"|"product"|"toy"|"tool"|"flat_art"|"unknown",\n'
    '  "issues": [<short strings>],\n'
    '  "enhanced_prompt": "<concise English prompt describing the subject for '
    '3D generation; mention pose, silhouette, simple solid body>"\n'
    "}\n\n"
    "Scoring rubric:\n"
    "- 9-10: single subject, front-facing, clean isolated background, no occlusion, "
    "good contrast.\n"
    "- 7-8: mostly suitable but small issues (slight angle, minor occlusion).\n"
    "- 5-6: usable but with notable issues (cluttered bg, side view, partial cut).\n"
    "- 3-4: marginal — multiple subjects, heavy occlusion, blur, or extreme angle.\n"
    "- 0-2: unsuitable — text only, abstract, indistinguishable subject."
)


@dataclass
class Assessment:
    score: float
    category: str
    issues: list[str]
    enhanced_prompt: str
    recommend: str  # 'proceed' | 'warn' | 'block'
    model: str = ""
    raw: str = ""
    error: str | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.error is None and self.recommend != "block"


# Claude vision supported MIME types (image only).
_MIME = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


def _read_image(path: Path) -> tuple[str, str]:
    """Return (media_type, base64-encoded data)."""
    mime = _MIME.get(path.suffix.lower(), "image/png")
    return mime, base64.b64encode(path.read_bytes()).decode("ascii")


def _extract_json(raw: str) -> dict:
    """Claude가 코드펜스나 잡설을 섞었을 때를 대비해 JSON 객체만 추출."""
    raw = raw.strip()
    # try direct
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # find first {...} block
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        raise ValueError("응답에서 JSON을 찾을 수 없음")
    return json.loads(m.group(0))


def _recommend(score: float, warn: float, block: float) -> str:
    if score < block:
        return "block"
    if score < warn:
        return "warn"
    return "proceed"


def assess_image(
    image_path: Path,
    api_key: str,
    *,
    model: str = "claude-sonnet-4-6",
    warn_below: float = 6.0,
    block_below: float = 3.0,
    max_tokens: int = 600,
) -> Assessment:
    """이미지 1장을 Claude vision으로 평가. 성공·실패 모두 Assessment 반환.

    실패 시 ok=False · error 채움 → 호출자가 결정(차단/경고 후 진행).
    """
    image_path = Path(image_path)
    if not image_path.exists():
        return Assessment(
            score=0, category="unknown", issues=["file-not-found"],
            enhanced_prompt="", recommend="block", model=model,
            error=f"file not found: {image_path}",
        )

    try:
        import anthropic
    except ImportError as e:
        return Assessment(
            score=0, category="unknown", issues=["anthropic-missing"],
            enhanced_prompt="", recommend="warn", model=model,
            error=f"anthropic SDK 미설치: {e}",
        )

    if not api_key:
        return Assessment(
            score=0, category="unknown", issues=["no-api-key"],
            enhanced_prompt="", recommend="warn", model=model,
            error="ANTHROPIC_API_KEY 누락",
        )

    media_type, b64 = _read_image(image_path)
    client = anthropic.Anthropic(api_key=api_key)
    try:
        msg = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=[{
                "type": "text", "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {
                        "type": "base64",
                        "media_type": media_type, "data": b64,
                    }},
                    {"type": "text", "text":
                     "Evaluate this image. Reply with the JSON object only."},
                ],
            }],
        )
    except Exception as e:  # noqa: BLE001
        return Assessment(
            score=0, category="unknown", issues=[f"api-error:{type(e).__name__}"],
            enhanced_prompt="", recommend="warn", model=model, error=str(e),
        )

    raw = "\n".join(
        b.text for b in msg.content if getattr(b, "type", "") == "text"
    )
    try:
        data = _extract_json(raw)
    except (ValueError, json.JSONDecodeError) as e:
        return Assessment(
            score=0, category="unknown", issues=["parse-error"],
            enhanced_prompt="", recommend="warn", model=model,
            raw=raw[:400], error=f"JSON 파싱 실패: {e}",
        )

    score = float(data.get("score") or 0)
    score = max(0.0, min(10.0, score))
    category = str(data.get("category") or "unknown")
    issues_raw = data.get("issues") or []
    issues = [str(x) for x in issues_raw] if isinstance(issues_raw, list) else []
    enhanced = str(data.get("enhanced_prompt") or "")

    return Assessment(
        score=score,
        category=category,
        issues=issues,
        enhanced_prompt=enhanced,
        recommend=_recommend(score, warn_below, block_below),
        model=model,
        raw=raw[:400],
    )
