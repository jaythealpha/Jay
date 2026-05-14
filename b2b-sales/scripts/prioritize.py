"""
수집된 타겟 CSV들에서 1차 파일럿(서울+경기 합계 200건) 추출.

세그먼트 정의:
  - S1: 서울 고등학교 (혁신학교/자공고/국제고/마이스터고 우선)        → 40
  - S2: 경기 그린스마트 미래학교 / 혁신학교                          → 40
  - S3: 서울 대형 공공도서관 (구립 본관·시립)                        → 30
  - S4: 경기 신축 공공도서관 (운영기간 짧은 곳 우선 — 데이터 부족 시 전체에서 무작위) → 30
  - S5: 서울/경기 시·구청                                            → 30
  - S6: 서울/경기 청소년상담복지센터·청년플랫폼                       → 30

출력:
  data/pilot_seoul_gyeonggi_200.csv
"""

from __future__ import annotations

import csv
import random
from pathlib import Path
from typing import Iterable

random.seed(42)

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = DATA / "pilot_seoul_gyeonggi_200.csv"


def load(name: str) -> list[dict]:
    path = DATA / name
    if not path.exists():
        print(f"[warn] {name} 없음 — 건너뜀")
        return []
    with path.open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def has_keyword(row: dict, keywords: Iterable[str], fields=("sub_type", "notes", "name")) -> bool:
    text = " ".join(row.get(k, "") for k in fields)
    return any(k in text for k in keywords)


def pick(rows: list[dict], n: int, label: str) -> list[dict]:
    if not rows:
        return []
    picked = rows[:n] if len(rows) >= n else rows
    for r in picked:
        r["segment"] = label
    print(f"  · {label}: {len(picked)}건 추출 (후보 {len(rows)})")
    return picked


def main() -> None:
    seoul_school = load("targets_school_서울특별시.csv")
    gyeonggi_school = load("targets_school_경기도.csv")
    seoul_lib = load("targets_library_서울특별시.csv")
    gyeonggi_lib = load("targets_library_경기도.csv")
    seoul_gov = load("targets_gov_서울특별시.csv")
    gyeonggi_gov = load("targets_gov_경기도.csv")

    print("\n=== 1차 파일럿(서울+경기, 200건) 추출 ===\n")

    # S1: 서울 고등학교 — 혁신·자공·국제·마이스터 우선
    s1_pool = [r for r in seoul_school if "고등" in r.get("sub_type", "")]
    s1_pool.sort(key=lambda r: 0 if has_keyword(r, ["혁신", "자율", "국제", "마이스터"]) else 1)
    s1 = pick(s1_pool, 40, "S1_서울고교")

    # S2: 경기 혁신학교/그린스마트
    s2_pool = [r for r in gyeonggi_school if has_keyword(r, ["혁신", "그린스마트", "공간혁신"])]
    if len(s2_pool) < 40:
        rest = [r for r in gyeonggi_school if "고등" in r.get("sub_type", "")]
        random.shuffle(rest)
        s2_pool.extend(rest)
    s2 = pick(s2_pool, 40, "S2_경기혁신·그린스마트")

    # S3: 서울 대형 공공도서관
    s3_pool = [r for r in seoul_lib if has_keyword(r, ["시립", "구립", "중앙"], fields=("name", "sub_type"))]
    if len(s3_pool) < 30:
        s3_pool.extend(seoul_lib)
    s3 = pick(s3_pool, 30, "S3_서울대형도서관")

    # S4: 경기 공공도서관 — 데이터 부족 시 전체에서 무작위
    random.shuffle(gyeonggi_lib)
    s4 = pick(gyeonggi_lib, 30, "S4_경기도서관")

    # S5: 서울/경기 시·구청
    gov_office = [r for r in seoul_gov + gyeonggi_gov if has_keyword(r, ["시청", "구청"], fields=("name", "sub_type"))]
    random.shuffle(gov_office)
    s5 = pick(gov_office, 30, "S5_서울경기시구청")

    # S6: 청소년상담·청년플랫폼 — 관공서 데이터에는 적기 어려움
    # 일단 행정복지센터/주민센터 중 인구 많은 구의 본청 위주로 임시 채택
    youth = [r for r in seoul_gov + gyeonggi_gov if has_keyword(r, ["행정복지센터", "주민센터"], fields=("name", "sub_type"))]
    random.shuffle(youth)
    s6 = pick(youth, 30, "S6_청년·청소년공간(잠정)")

    all_picked = s1 + s2 + s3 + s4 + s5 + s6
    print(f"\n총 {len(all_picked)}건 선정 (목표 200)")

    if not all_picked:
        print("[error] 수집 데이터가 비어 있습니다. collect_targets.py 부터 실행해 주세요.")
        return

    fieldnames = list(all_picked[0].keys())
    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(all_picked)
    print(f"[OK] 저장 → {OUT}")

    print("\n다음 단계:")
    print("  1) python scripts/enrich_contacts.py --input data/pilot_seoul_gyeonggi_200.csv")
    print("  2) 보강된 CSV를 tracking/pipeline_template.csv 와 합쳐 Google Sheets로 임포트")
    print("  3) 세그먼트(S1~S6)별로 cold_email_templates.md A/B/C 매칭하여 발송")


if __name__ == "__main__":
    main()
