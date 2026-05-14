"""
요기보 B2B 영업용 타겟 리스트 수집 스크립트
----------------------------------------------------
수집 대상:
  1) 전국 초·중·고등학교 (학교알리미 공공데이터)
  2) 공공도서관 (문화체육관광부 도서관 정보나루 API)
  3) 지방자치단체/관공서 (공공데이터포털 행정기관 코드)

산출물: data/targets_{school|library|gov}.csv
컬럼:   name, type, region, address, phone, homepage, contact_dept,
        contact_email, est_budget_tier, notes

사용 예시:
  python collect_targets.py --type school --region 서울특별시
  python collect_targets.py --type library --region 경기도
  python collect_targets.py --type gov     --region 부산광역시

환경변수:
  DATA_GO_KR_KEY   공공데이터포털 인증키 (https://www.data.go.kr)
  LIBSEOUL_KEY     도서관정보나루 인증키 (https://www.data4library.kr)
  SCHOOLINFO_KEY   학교알리미 / 나이스 교육정보 OpenAPI 인증키
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, Iterator

import requests

OUT_DIR = Path(__file__).resolve().parent.parent / "data"
OUT_DIR.mkdir(exist_ok=True)

REQUEST_TIMEOUT = 15
SLEEP_BETWEEN_CALLS = 0.4  # API rate limit 보호


@dataclass
class Target:
    name: str
    type: str            # school / library / gov
    sub_type: str        # 초/중/고/공공도서관/시청/구청/주민센터 등
    region: str
    address: str
    phone: str
    homepage: str
    contact_dept: str    # 행정실 / 사서실 / 총무과 등
    contact_email: str
    est_budget_tier: str # S(>3,000만) / A(1,000~3,000만) / B(<1,000만)
    notes: str


# ─────────────────────────────────────────────
# 1. 학교 (NEIS 교육정보 OpenAPI - schoolInfo)
#    https://open.neis.go.kr
# ─────────────────────────────────────────────
NEIS_SCHOOL_URL = "https://open.neis.go.kr/hub/schoolInfo"
SIDO_CODE = {
    "서울특별시": "B10", "부산광역시": "C10", "대구광역시": "D10",
    "인천광역시": "E10", "광주광역시": "F10", "대전광역시": "G10",
    "울산광역시": "H10", "세종특별자치시": "I10",
    "경기도": "J10", "강원특별자치도": "K10", "충청북도": "M10",
    "충청남도": "N10", "전북특별자치도": "P10", "전라남도": "Q10",
    "경상북도": "R10", "경상남도": "S10", "제주특별자치도": "T10",
}


def fetch_schools(region: str) -> Iterator[Target]:
    key = os.environ.get("SCHOOLINFO_KEY")
    if not key:
        sys.exit("SCHOOLINFO_KEY 환경변수가 필요합니다. https://open.neis.go.kr 에서 발급")
    sido = SIDO_CODE.get(region)
    if not sido:
        sys.exit(f"알 수 없는 시도명: {region}")

    page = 1
    while True:
        params = {
            "KEY": key,
            "Type": "json",
            "pIndex": page,
            "pSize": 1000,
            "ATPT_OFCDC_SC_CODE": sido,
        }
        resp = requests.get(NEIS_SCHOOL_URL, params=params, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        rows = data.get("schoolInfo", [{}, {}])[1].get("row", [])
        if not rows:
            break
        for r in rows:
            sub = r.get("SCHUL_KND_SC_NM", "")  # 초등학교/중학교/고등학교
            # 그린스마트 미래학교/공간혁신 후보 학교는 별도 플래그용 메모
            notes = []
            if "혁신" in r.get("FOND_SC_NM", ""):
                notes.append("혁신학교")
            if r.get("HS_GNRL_BUSNS_SC_NM"):
                notes.append(r["HS_GNRL_BUSNS_SC_NM"])
            yield Target(
                name=r.get("SCHUL_NM", ""),
                type="school",
                sub_type=sub,
                region=r.get("LCTN_SC_NM", region),
                address=r.get("ORG_RDNMA", ""),
                phone=r.get("ORG_TELNO", ""),
                homepage=r.get("HMPG_ADRES", ""),
                contact_dept="행정실",
                contact_email="",  # NEIS 미제공 → 홈페이지에서 별도 수집 필요
                est_budget_tier=guess_school_tier(sub),
                notes=",".join(notes),
            )
        page += 1
        time.sleep(SLEEP_BETWEEN_CALLS)


def guess_school_tier(sub_type: str) -> str:
    # 학생 1인당 가구예산은 고교 > 중 > 초 순으로 자유도가 높음
    if "고등" in sub_type:
        return "A"
    if "중학" in sub_type:
        return "B"
    return "B"


# ─────────────────────────────────────────────
# 2. 공공도서관 (도서관정보나루)
#    https://www.data4library.kr
# ─────────────────────────────────────────────
LIB_URL = "http://data4library.kr/api/libSrch"


def fetch_libraries(region: str) -> Iterator[Target]:
    key = os.environ.get("LIBSEOUL_KEY")
    if not key:
        sys.exit("LIBSEOUL_KEY 환경변수가 필요합니다. https://www.data4library.kr 에서 발급")

    params = {"authKey": key, "region": region, "pageSize": 500, "format": "json"}
    resp = requests.get(LIB_URL, params=params, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    libs = data.get("response", {}).get("libs", [])
    for item in libs:
        lib = item.get("lib", {})
        yield Target(
            name=lib.get("libName", ""),
            type="library",
            sub_type=lib.get("libType", "공공도서관"),
            region=region,
            address=lib.get("address", ""),
            phone=lib.get("tel", ""),
            homepage=lib.get("homepage", ""),
            contact_dept="사서실/운영팀",
            contact_email=lib.get("email", ""),
            est_budget_tier="A",  # 어린이실/청소년실 가구 예산 정기 편성
            notes="어린이실/청소년실 휴게가구 제안 적합",
        )


# ─────────────────────────────────────────────
# 3. 관공서 (공공데이터포털 - 행정기관 코드)
# ─────────────────────────────────────────────
GOV_URL = "https://apis.data.go.kr/1741000/StanReginCd/getStanReginCdList"


def fetch_gov_offices(region: str) -> Iterator[Target]:
    key = os.environ.get("DATA_GO_KR_KEY")
    if not key:
        sys.exit("DATA_GO_KR_KEY 환경변수가 필요합니다.")

    params = {
        "serviceKey": key, "type": "json",
        "pageNo": 1, "numOfRows": 1000,
        "locatadd_nm": region,
    }
    resp = requests.get(GOV_URL, params=params, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    rows = (
        data.get("StanReginCd", [{}, {}])[1].get("row", [])
        if isinstance(data.get("StanReginCd"), list)
        else []
    )
    for r in rows:
        name = r.get("locatadd_nm", "")
        if not any(k in name for k in ("시청", "구청", "군청", "주민센터", "행정복지센터")):
            continue
        yield Target(
            name=name,
            type="gov",
            sub_type=classify_gov(name),
            region=region,
            address=r.get("locatadd_nm", ""),
            phone="",
            homepage="",
            contact_dept="총무과 / 복지문화과",
            contact_email="",
            est_budget_tier=guess_gov_tier(name),
            notes="민원실 대기공간, 청소년상담복지센터, 도서관 부속실",
        )


def classify_gov(name: str) -> str:
    if "시청" in name:
        return "시청"
    if "구청" in name:
        return "구청"
    if "군청" in name:
        return "군청"
    if "행정복지센터" in name or "주민센터" in name:
        return "행정복지센터"
    return "기타"


def guess_gov_tier(name: str) -> str:
    if "시청" in name or "구청" in name:
        return "S"
    if "군청" in name:
        return "A"
    return "B"


# ─────────────────────────────────────────────
# Writer
# ─────────────────────────────────────────────
def write_csv(rows: Iterable[Target], target_type: str, region: str) -> Path:
    safe_region = region.replace(" ", "_")
    out = OUT_DIR / f"targets_{target_type}_{safe_region}.csv"
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(Target.__annotations__.keys()))
        writer.writeheader()
        count = 0
        for r in rows:
            writer.writerow(asdict(r))
            count += 1
    print(f"[OK] {out}  ({count} rows)")
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--type", choices=["school", "library", "gov"], required=True)
    p.add_argument("--region", required=True, help="예: 서울특별시, 경기도")
    args = p.parse_args()

    if args.type == "school":
        rows = fetch_schools(args.region)
    elif args.type == "library":
        rows = fetch_libraries(args.region)
    else:
        rows = fetch_gov_offices(args.region)

    write_csv(rows, args.type, args.region)


if __name__ == "__main__":
    main()
