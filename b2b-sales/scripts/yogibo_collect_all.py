"""
요기보 B2B — 서울+경기 타겟 수집 통합본 (단일 파일)
=========================================================
파이썬 파일 하나로 끝납니다.

[사전 준비]
1) 파이썬 패키지 설치 (한 번만):
     pip install requests

2) 환경변수 3개 확인 (Git Bash):
     echo $SCHOOLINFO_KEY
     echo $LIBSEOUL_KEY
     echo $DATA_GO_KR_KEY

[실행]
     python yogibo_collect_all.py

[결과물]
   ./targets_school_서울특별시.csv
   ./targets_school_경기도.csv
   ./targets_library_서울특별시.csv
   ./targets_library_경기도.csv
   ./targets_gov_서울특별시.csv
   ./targets_gov_경기도.csv
   ./pilot_seoul_gyeonggi_200.csv   ← 1차 영업 대상 200건
"""

from __future__ import annotations

import csv
import os
import random
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path

import requests

random.seed(42)
TIMEOUT = 15
SLEEP = 0.4
OUT_DIR = Path(".")

SIDO = {
    "서울특별시": "B10",
    "경기도": "J10",
}


# ─────────────────────────────────────────────
@dataclass
class Target:
    name: str
    type: str
    sub_type: str
    region: str
    address: str
    phone: str
    homepage: str
    contact_dept: str
    contact_email: str
    est_budget_tier: str
    notes: str
    segment: str = ""


# ─────────────────────────────────────────────
def need(env: str) -> str:
    v = os.environ.get(env, "").strip()
    if not v:
        sys.exit(f"[중단] 환경변수 {env} 가 비어 있습니다. ~/.bashrc 확인 후 'source ~/.bashrc' 후 다시 실행하세요.")
    return v


# ─────────────────────────────────────────────
# 1. NEIS 학교
# ─────────────────────────────────────────────
def fetch_schools(region: str) -> list[Target]:
    key = need("SCHOOLINFO_KEY")
    out: list[Target] = []
    page = 1
    while True:
        try:
            r = requests.get(
                "https://open.neis.go.kr/hub/schoolInfo",
                params={
                    "KEY": key, "Type": "json",
                    "pIndex": page, "pSize": 1000,
                    "ATPT_OFCDC_SC_CODE": SIDO[region],
                },
                timeout=TIMEOUT,
            )
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            print(f"  [error] NEIS page {page}: {e}")
            break

        if "schoolInfo" not in data:
            # 에러 응답 (RESULT.CODE)
            print(f"  [info] {region} 학교 — 응답 종료 ({data.get('RESULT', {}).get('MESSAGE', '')})")
            break

        rows = data["schoolInfo"][1].get("row", [])
        if not rows:
            break

        for r_ in rows:
            sub = r_.get("SCHUL_KND_SC_NM", "")
            out.append(Target(
                name=r_.get("SCHUL_NM", ""),
                type="school",
                sub_type=sub,
                region=r_.get("LCTN_SC_NM", region),
                address=r_.get("ORG_RDNMA", ""),
                phone=r_.get("ORG_TELNO", ""),
                homepage=r_.get("HMPG_ADRES", ""),
                contact_dept="행정실",
                contact_email="",
                est_budget_tier="A" if "고등" in sub else "B",
                notes=r_.get("FOND_SC_NM", ""),
            ))
        page += 1
        time.sleep(SLEEP)
    return out


# ─────────────────────────────────────────────
# 2. 도서관정보나루
# ─────────────────────────────────────────────
def fetch_libraries(region: str) -> list[Target]:
    key = need("LIBSEOUL_KEY")
    out: list[Target] = []
    try:
        r = requests.get(
            "http://data4library.kr/api/libSrch",
            params={"authKey": key, "region": region, "pageSize": 1000, "format": "json"},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"  [error] 도서관 {region}: {e}")
        return out

    for item in data.get("response", {}).get("libs", []):
        lib = item.get("lib", {})
        out.append(Target(
            name=lib.get("libName", ""),
            type="library",
            sub_type=lib.get("libType", "공공도서관"),
            region=region,
            address=lib.get("address", ""),
            phone=lib.get("tel", ""),
            homepage=lib.get("homepage", ""),
            contact_dept="사서실/운영팀",
            contact_email=lib.get("email", ""),
            est_budget_tier="A",
            notes="어린이실/청소년실 휴게가구 제안",
        ))
    return out


# ─────────────────────────────────────────────
# 3. 공공데이터포털 — 행정기관 코드
# ─────────────────────────────────────────────
def fetch_gov(region: str) -> list[Target]:
    key = need("DATA_GO_KR_KEY")
    out: list[Target] = []
    try:
        r = requests.get(
            "https://apis.data.go.kr/1741000/StanReginCd/getStanReginCdList",
            params={
                "serviceKey": key, "type": "json",
                "pageNo": 1, "numOfRows": 1000,
                "locatadd_nm": region,
            },
            timeout=TIMEOUT,
        )
        if "OpenAPI_ServiceResponse" in r.text:
            print(f"  [error] 공공데이터포털 인증 실패 — DATA_GO_KR_KEY 확인 필요")
            return out
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"  [error] 관공서 {region}: {e}")
        return out

    payload = data.get("StanReginCd")
    if not isinstance(payload, list) or len(payload) < 2:
        return out

    for r_ in payload[1].get("row", []):
        name = r_.get("locatadd_nm", "")
        if not any(k in name for k in ("시청", "구청", "군청", "주민센터", "행정복지센터")):
            continue
        out.append(Target(
            name=name,
            type="gov",
            sub_type=("시청" if "시청" in name else "구청" if "구청" in name else "기타"),
            region=region,
            address=name,
            phone="",
            homepage="",
            contact_dept="총무과 / 복지문화과",
            contact_email="",
            est_budget_tier="S" if ("시청" in name or "구청" in name) else "B",
            notes="민원실/청년공간/직원휴게",
        ))
    return out


# ─────────────────────────────────────────────
# 저장
# ─────────────────────────────────────────────
def save(rows: list[Target], filename: str) -> None:
    path = OUT_DIR / filename
    if not rows:
        print(f"  [warn] {filename} — 0건, 저장 생략")
        return
    fields = list(Target.__annotations__.keys())
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(asdict(r))
    print(f"  ✅ {path}  ({len(rows)}건)")


# ─────────────────────────────────────────────
# 파일럿 200건 추출
# ─────────────────────────────────────────────
def has_kw(r: Target, kws) -> bool:
    text = f"{r.name} {r.sub_type} {r.notes}"
    return any(k in text for k in kws)


def build_pilot(
    seoul_school, gyeonggi_school,
    seoul_lib, gyeonggi_lib,
    seoul_gov, gyeonggi_gov,
) -> list[Target]:
    print("\n--- 파일럿 200건 추출 ---")
    pilot: list[Target] = []

    # S1: 서울 고등학교
    s1 = [r for r in seoul_school if "고등" in r.sub_type]
    s1.sort(key=lambda r: 0 if has_kw(r, ["혁신", "자율", "국제", "마이스터"]) else 1)
    for r in s1[:40]:
        r.segment = "S1_서울고교"
        pilot.append(r)
    print(f"  S1 서울고교:        {min(40, len(s1))}건")

    # S2: 경기 혁신/그린스마트
    s2 = [r for r in gyeonggi_school if has_kw(r, ["혁신", "그린스마트", "공간혁신"])]
    if len(s2) < 40:
        rest = [r for r in gyeonggi_school if "고등" in r.sub_type and r not in s2]
        random.shuffle(rest)
        s2.extend(rest)
    for r in s2[:40]:
        r.segment = "S2_경기혁신·그린스마트"
        pilot.append(r)
    print(f"  S2 경기혁신·그린스마트: {min(40, len(s2))}건")

    # S3: 서울 대형 공공도서관
    s3 = [r for r in seoul_lib if has_kw(r, ["시립", "구립", "중앙"])]
    if len(s3) < 30:
        s3.extend([r for r in seoul_lib if r not in s3])
    for r in s3[:30]:
        r.segment = "S3_서울대형도서관"
        pilot.append(r)
    print(f"  S3 서울도서관:       {min(30, len(s3))}건")

    # S4: 경기 공공도서관 무작위
    s4 = list(gyeonggi_lib)
    random.shuffle(s4)
    for r in s4[:30]:
        r.segment = "S4_경기도서관"
        pilot.append(r)
    print(f"  S4 경기도서관:       {min(30, len(s4))}건")

    # S5: 시·구청
    s5 = [r for r in seoul_gov + gyeonggi_gov if has_kw(r, ["시청", "구청"])]
    random.shuffle(s5)
    for r in s5[:30]:
        r.segment = "S5_시구청"
        pilot.append(r)
    print(f"  S5 시·구청:         {min(30, len(s5))}건")

    # S6: 행정복지센터/주민센터 (청년·청소년 공간 잠정)
    s6 = [r for r in seoul_gov + gyeonggi_gov if has_kw(r, ["행정복지센터", "주민센터"])]
    random.shuffle(s6)
    for r in s6[:30]:
        r.segment = "S6_청년·청소년공간(잠정)"
        pilot.append(r)
    print(f"  S6 청년·청소년공간: {min(30, len(s6))}건")

    return pilot


# ─────────────────────────────────────────────
def main() -> None:
    print("\n========== 요기보 B2B 타겟 수집 (서울+경기) ==========\n")

    print("[1/3] 서울 학교 수집...")
    seoul_school = fetch_schools("서울특별시")
    save(seoul_school, "targets_school_서울특별시.csv")

    print("[2/3] 경기 학교 수집...")
    gyeonggi_school = fetch_schools("경기도")
    save(gyeonggi_school, "targets_school_경기도.csv")

    print("[3/3] 도서관 + 관공서 수집...")
    seoul_lib = fetch_libraries("서울특별시"); save(seoul_lib, "targets_library_서울특별시.csv")
    gyeonggi_lib = fetch_libraries("경기도");      save(gyeonggi_lib, "targets_library_경기도.csv")
    seoul_gov = fetch_gov("서울특별시");          save(seoul_gov,  "targets_gov_서울특별시.csv")
    gyeonggi_gov = fetch_gov("경기도");              save(gyeonggi_gov, "targets_gov_경기도.csv")

    pilot = build_pilot(seoul_school, gyeonggi_school, seoul_lib, gyeonggi_lib, seoul_gov, gyeonggi_gov)
    save(pilot, "pilot_seoul_gyeonggi_200.csv")

    print("\n========== 완료 ==========")
    print("다음 단계:")
    print("  1) pilot_seoul_gyeonggi_200.csv 를 Excel/Google Sheets로 열어서 확인")
    print("  2) 비어 있는 contact_email 컬럼을 채워야 발송 가능")
    print("     (홈페이지 방문해 행정실/사서실 이메일 수동 수집 또는 추가 스크립트)")


if __name__ == "__main__":
    main()
