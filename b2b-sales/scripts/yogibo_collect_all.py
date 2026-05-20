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

# 도서관정보나루 region 코드 (data4library.kr 은 시도명이 아닌 숫자 코드를 받음)
LIB_REGION = {
    "서울특별시": "11",
    "경기도": "31",
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
    region_code = LIB_REGION.get(region)
    if not region_code:
        print(f"  [error] 도서관 {region}: LIB_REGION 매핑 누락")
        return out
    try:
        r = requests.get(
            "http://data4library.kr/api/libSrch",
            params={"authKey": key, "region": region_code, "pageSize": 1000, "format": "json"},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"  [error] 도서관 {region}: {e}")
        return out

    resp = data.get("response", {})
    if "error" in resp:
        print(f"  [error] 도서관 {region}: {resp['error']}")
        return out

    for item in resp.get("libs", []):
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
# 3. 시·구·군청 (하드코딩 리스트)
# data.go.kr StanReginCd 는 기관 목록이 아닌 행정구역 코드만 반환하므로
# 고정 자치단체 목록을 직접 사용합니다.
# ─────────────────────────────────────────────
SEOUL_GOV = [
    ("서울특별시청", "시청", "https://www.seoul.go.kr"),
    ("종로구청", "구청", "https://www.jongno.go.kr"),
    ("중구청", "구청", "https://www.junggu.seoul.kr"),
    ("용산구청", "구청", "https://www.yongsan.go.kr"),
    ("성동구청", "구청", "https://www.sd.go.kr"),
    ("광진구청", "구청", "https://www.gwangjin.go.kr"),
    ("동대문구청", "구청", "https://www.ddm.go.kr"),
    ("중랑구청", "구청", "https://www.jungnang.go.kr"),
    ("성북구청", "구청", "https://www.sb.go.kr"),
    ("강북구청", "구청", "https://www.gangbuk.go.kr"),
    ("도봉구청", "구청", "https://www.dobong.go.kr"),
    ("노원구청", "구청", "https://www.nowon.kr"),
    ("은평구청", "구청", "https://www.ep.go.kr"),
    ("서대문구청", "구청", "https://www.sdm.go.kr"),
    ("마포구청", "구청", "https://www.mapo.go.kr"),
    ("양천구청", "구청", "https://www.yangcheon.go.kr"),
    ("강서구청", "구청", "https://www.gangseo.seoul.kr"),
    ("구로구청", "구청", "https://www.guro.go.kr"),
    ("금천구청", "구청", "https://www.geumcheon.go.kr"),
    ("영등포구청", "구청", "https://www.ydp.go.kr"),
    ("동작구청", "구청", "https://www.dongjak.go.kr"),
    ("관악구청", "구청", "https://www.gwanak.go.kr"),
    ("서초구청", "구청", "https://www.seocho.go.kr"),
    ("강남구청", "구청", "https://www.gangnam.go.kr"),
    ("송파구청", "구청", "https://www.songpa.go.kr"),
    ("강동구청", "구청", "https://www.gangdong.go.kr"),
]

GYEONGGI_GOV = [
    ("경기도청", "도청", "https://www.gg.go.kr"),
    ("수원시청", "시청", "https://www.suwon.go.kr"),
    ("고양시청", "시청", "https://www.goyang.go.kr"),
    ("용인시청", "시청", "https://www.yongin.go.kr"),
    ("성남시청", "시청", "https://www.seongnam.go.kr"),
    ("부천시청", "시청", "https://www.bucheon.go.kr"),
    ("화성시청", "시청", "https://www.hscity.go.kr"),
    ("안산시청", "시청", "https://www.iansan.net"),
    ("남양주시청", "시청", "https://www.nyj.go.kr"),
    ("안양시청", "시청", "https://www.anyang.go.kr"),
    ("평택시청", "시청", "https://www.pyeongtaek.go.kr"),
    ("시흥시청", "시청", "https://www.siheung.go.kr"),
    ("파주시청", "시청", "https://www.paju.go.kr"),
    ("의정부시청", "시청", "https://www.ui4u.go.kr"),
    ("김포시청", "시청", "https://www.gimpo.go.kr"),
    ("광주시청", "시청", "https://www.gjcity.go.kr"),
    ("광명시청", "시청", "https://www.gm.go.kr"),
    ("군포시청", "시청", "https://www.gunpo.go.kr"),
    ("하남시청", "시청", "https://www.hanam.go.kr"),
    ("오산시청", "시청", "https://www.osan.go.kr"),
    ("양주시청", "시청", "https://www.yangju.go.kr"),
    ("이천시청", "시청", "https://www.icheon.go.kr"),
    ("구리시청", "시청", "https://www.guri.go.kr"),
    ("안성시청", "시청", "https://www.anseong.go.kr"),
    ("포천시청", "시청", "https://www.pocheon.go.kr"),
    ("의왕시청", "시청", "https://www.uiwang.go.kr"),
    ("여주시청", "시청", "https://www.yeoju.go.kr"),
    ("동두천시청", "시청", "https://www.ddc.go.kr"),
    ("과천시청", "시청", "https://www.gccity.go.kr"),
    ("양평군청", "군청", "https://www.yp21.go.kr"),
    ("가평군청", "군청", "https://www.gp.go.kr"),
    ("연천군청", "군청", "https://www.yeoncheon.go.kr"),
]


def fetch_gov(region: str) -> list[Target]:
    src = SEOUL_GOV if region == "서울특별시" else GYEONGGI_GOV if region == "경기도" else []
    out: list[Target] = []
    for name, sub, hp in src:
        out.append(Target(
            name=name,
            type="gov",
            sub_type=sub,
            region=region,
            address="",
            phone="",
            homepage=hp,
            contact_dept="총무과 / 복지문화과",
            contact_email="",
            est_budget_tier="S",
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

    # S5: 시·구·군·도청
    s5 = [r for r in seoul_gov + gyeonggi_gov if has_kw(r, ["시청", "구청", "군청", "도청"])]
    random.shuffle(s5)
    for r in s5[:30]:
        r.segment = "S5_시구청"
        pilot.append(r)
    print(f"  S5 시·구청:         {min(30, len(s5))}건")

    # S6: 행정복지센터/주민센터 — 별도 데이터 소스 필요 (현재 미수집)
    s6 = [r for r in seoul_gov + gyeonggi_gov if has_kw(r, ["행정복지센터", "주민센터"])]
    random.shuffle(s6)
    for r in s6[:30]:
        r.segment = "S6_청년·청소년공간(잠정)"
        pilot.append(r)
    print(f"  S6 청년·청소년공간: {min(30, len(s6))}건  (※ 별도 데이터 소스 필요)")

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
