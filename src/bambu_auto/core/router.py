"""프린터 라우팅. settings.yaml의 routing.rules 평가.

규칙 형식 (순서대로 평가, 첫 매칭 채택):
    - if: { material: [abs, asa, petg] }       use: p2s
    - if: { max_dimension_mm: 200, material: [pla, silk] }  use: a1
    - default: p2s

max_dimension_mm 은 "이하" 조건으로 해석.
"""

from __future__ import annotations

from dataclasses import dataclass

from bambu_auto.config import RoutingConfig


@dataclass
class RouteContext:
    material: str
    max_dimension_mm: float


def select_printer(
    ctx: RouteContext,
    routing: RoutingConfig,
    forced: str | None = None,
) -> str:
    """forced 지정 시 그대로. 아니면 규칙 평가 → 프린터 이름 반환."""
    if forced:
        return forced

    default = "p2s"
    for rule in routing.rules:
        if "default" in rule:
            default = rule["default"]
            continue
        cond = rule.get("if", {})
        if _matches(cond, ctx):
            return rule["use"]
    return default


def _matches(cond: dict, ctx: RouteContext) -> bool:
    if "material" in cond:
        mats = cond["material"]
        if isinstance(mats, str):
            mats = [mats]
        if ctx.material.lower() not in [m.lower() for m in mats]:
            return False
    if "max_dimension_mm" in cond:
        if ctx.max_dimension_mm > float(cond["max_dimension_mm"]):
            return False
    return True
