#!/usr/bin/env python3
"""
요기보 인스타 티징 — 1,000개 이미지 프롬프트 매니페스트 생성기

조합 축(제품 × 후킹 × 장면 × 페르소나 × 스타일)을 곱한 거대한 공간에서
다양성을 극대화하며 중복 없이 N개를 샘플링한다.

출력:
  prompts/manifest.jsonl   - 한 줄당 1개 프롬프트(이미지 생성 API 입력용)
  prompts/manifest.csv     - 사람이 검토/편집하기 좋은 표 형태

사용:
  python generate_prompts.py            # 기본 1000개
  python generate_prompts.py --count 1000 --seed 42
"""
import argparse
import csv
import itertools
import json
import os
import random

import data

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "prompts")


def weighted_ratio(rng):
    pool = []
    for ar in data.ASPECT_RATIOS:
        pool.extend([ar] * ar["weight"])
    return rng.choice(pool)


def build_image_prompt(product, scene, persona, style, color):
    """이미지 모델에 넣을 영문 프롬프트(상표/로고 배제)."""
    person_part = "" if persona["en"].startswith("no person") else f"{persona['en']}, "
    return (
        f"A premium oversized bean bag sofa ({product['form']}), {color} fabric color, "
        f"{person_part}{scene['en']}, {style['en']}, "
        f"Korean home aesthetic, photorealistic, high-end interior photography, "
        f"soft natural shadows, 8k, advertising quality, leave clean negative space at the top for a text overlay"
    )


def generate(count, seed):
    rng = random.Random(seed)

    # 조합 공간이 충분히 크므로(수십만), 무작위 추출 + 중복 제거로
    # 제품·후킹·장면·페르소나·스타일이 고르게 퍼지게 한다.
    space = (
        len(data.PRODUCTS) * len(data.HOOKS) * len(data.SCENES)
        * len(data.PERSONAS) * len(data.STYLES)
    )
    if count > space:
        raise ValueError(f"요청 {count}개 > 가능 조합 {space}개")

    seen = set()
    records = []
    i = 0
    guard = 0
    while len(records) < count and guard < count * 200:
        guard += 1
        product = rng.choice(data.PRODUCTS)
        hook = rng.choice(data.HOOKS)
        scene = rng.choice(data.SCENES)
        persona = rng.choice(data.PERSONAS)
        style = rng.choice(data.STYLES)

        key = (product["en"], hook["key"], scene["kr"], persona["kr"], style["kr"])
        if key in seen:
            continue
        seen.add(key)

        copy_line = rng.choice(hook["copy"])
        color = rng.choice(data.COLORS)
        ar = weighted_ratio(rng)

        i += 1
        rec = {
            "id": f"yg_{i:04d}",
            "product_kr": product["kr"],
            "product_en": product["en"],
            "hook_key": hook["key"],
            "hook_kr": hook["kr"],
            "overlay_text_kr": copy_line,
            "scene_kr": scene["kr"],
            "persona_kr": persona["kr"],
            "style_kr": style["kr"],
            "color_kr": color,
            "aspect_ratio": ar["ratio"],
            "size": ar["size"],
            "ig_format": ar["use"],
            "image_prompt": build_image_prompt(product, scene, persona, style, color),
            "negative_prompt": data.NEGATIVE_PROMPT,
            "status": "pending",
            "image_path": "",
        }
        records.append(rec)

    return records


def write_outputs(records):
    os.makedirs(OUT_DIR, exist_ok=True)
    jsonl_path = os.path.join(OUT_DIR, "manifest.jsonl")
    csv_path = os.path.join(OUT_DIR, "manifest.csv")

    with open(jsonl_path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    fields = list(records[0].keys())
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(records)

    return jsonl_path, csv_path


def summarize(records):
    from collections import Counter
    def dist(field):
        return Counter(r[field] for r in records)
    print(f"\n총 {len(records)}개 프롬프트 생성 완료\n")
    print("[제품별 분포]", dict(dist("product_kr")))
    print("[후킹 유형별 분포]", dict(dist("hook_kr")))
    print("[포맷별 분포]", dict(dist("ig_format")))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    records = generate(args.count, args.seed)
    if len(records) < args.count:
        print(f"경고: 요청 {args.count}개 중 {len(records)}개만 생성됨(조합 부족).")
    jsonl_path, csv_path = write_outputs(records)
    summarize(records)
    print(f"\n매니페스트 저장:\n  - {jsonl_path}\n  - {csv_path}")


if __name__ == "__main__":
    main()
