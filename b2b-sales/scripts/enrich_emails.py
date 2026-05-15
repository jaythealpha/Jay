"""
이메일 추출 (homepage 크롤링 → contact_email 자동 채우기)
===========================================================
입력 : ./pilot_seoul_gyeonggi_200.csv
출력 : ./pilot_seoul_gyeonggi_200_enriched.csv

추출 우선순위:
  1) mailto: 링크 (가장 정확)
  2) 페이지 텍스트의 이메일 패턴
부서 매칭:
  학교  → 행정실 > 총무부 > 교무실 > 교장실
  도서관 → 사서실 > 운영팀 > 관리과 > 정보봉사 > 문의
  시·구청 → 총무과 > 청년정책 > 복지문화 > 기획 > 민원
대표 페이지에서 못 찾으면 /contact, /about, /오시는길 등 보조 페이지를 한 번 더 시도.
"""

from __future__ import annotations

import csv
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

INPUT = Path("pilot_seoul_gyeonggi_200.csv")
OUTPUT = Path("pilot_seoul_gyeonggi_200_enriched.csv")

TIMEOUT = 8
SLEEP = 0.4
USER_AGENT = "Mozilla/5.0 (compatible; YogiboB2BBot/1.0)"

DEPT_KEYWORDS = {
    "school":  ["행정실", "총무부", "교무실", "교장실"],
    "library": ["사서실", "운영팀", "관리과", "정보봉사", "문의"],
    "gov":     ["총무과", "청년정책", "복지문화", "기획", "민원"],
}

SECONDARY_PATHS = [
    "/contact", "/about", "/intro",
    "/오시는길", "/이용안내", "/조직도", "/연락처",
]

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
BAD_PREFIX = ("noreply@", "no-reply@", "donotreply@", "do-not-reply@")
BAD_DOMAINS = ("example.com", "test.com", "sample.com")


def fetch(url: str, session: requests.Session) -> str | None:
    try:
        r = session.get(url, timeout=TIMEOUT, headers={"User-Agent": USER_AGENT})
        if r.status_code != 200:
            return None
        r.encoding = r.apparent_encoding or "utf-8"
        return r.text
    except Exception:
        return None


def extract_candidates(html: str) -> list[tuple[str, str, str]]:
    """(email, surrounding_text, source_label) 후보 목록"""
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[tuple[str, str, str]] = []

    # 1) mailto:
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.lower().startswith("mailto:"):
            email = href[7:].split("?")[0].strip()
            if EMAIL_RE.fullmatch(email):
                parent = a.find_parent()
                ctx = parent.get_text(" ", strip=True)[:300] if parent else ""
                candidates.append((email, ctx, "mailto"))

    # 2) 본문 텍스트
    text = soup.get_text(" ", strip=True)
    for m in EMAIL_RE.finditer(text):
        email = m.group(0)
        start = max(0, m.start() - 80)
        end = min(len(text), m.end() + 80)
        candidates.append((email, text[start:end], "text"))

    return candidates


def is_junk(email: str) -> bool:
    el = email.lower()
    if el.startswith(BAD_PREFIX):
        return True
    if any(el.endswith("@" + d) for d in BAD_DOMAINS):
        return True
    if el.endswith((".png", ".jpg", ".gif", ".svg")):  # 이미지 파일명 오탐
        return True
    return False


def pick_best(candidates: list[tuple[str, str, str]], target_type: str):
    """부서 키워드 매칭으로 가장 적합한 이메일 선정"""
    if not candidates:
        return None, "", ""

    # 중복 제거 (순서 유지)
    seen: set[str] = set()
    deduped: list[tuple[str, str, str]] = []
    for email, ctx, src in candidates:
        e = email.lower()
        if e in seen or is_junk(email):
            continue
        seen.add(e)
        deduped.append((email, ctx, src))

    if not deduped:
        return None, "", ""

    # 부서 키워드 우선
    for kw in DEPT_KEYWORDS.get(target_type, []):
        for email, ctx, src in deduped:
            if kw in ctx:
                return email, kw, src

    # 매칭 실패 — mailto 우선
    for email, ctx, src in deduped:
        if src == "mailto":
            return email, "", src
    return deduped[0][0], "", deduped[0][2]


def normalize_url(url: str) -> str | None:
    if not url:
        return None
    url = url.strip()
    if not url or url in ("-", "N/A"):
        return None
    if not url.startswith(("http://", "https://")):
        url = "http://" + url
    return url


def find_email(session: requests.Session, homepage: str, target_type: str):
    """대표 페이지 → 보조 페이지 순으로 시도"""
    html = fetch(homepage, session)
    cands = extract_candidates(html) if html else []
    chosen_url = homepage if cands else ""

    if not cands:
        parsed = urlparse(homepage)
        base = f"{parsed.scheme}://{parsed.netloc}"
        for path in SECONDARY_PATHS:
            sub_url = urljoin(base, path)
            sub_html = fetch(sub_url, session)
            time.sleep(SLEEP)
            if sub_html:
                sub_c = extract_candidates(sub_html)
                if sub_c:
                    cands = sub_c
                    chosen_url = sub_url
                    break

    email, dept, _ = pick_best(cands, target_type)
    return (email or ""), (chosen_url if email else ""), dept


def main() -> None:
    if not INPUT.exists():
        sys.exit(f"[중단] 입력 파일 없음: {INPUT}")

    with INPUT.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])

    for col in ("email_source_url", "email_dept", "manual_check", "enrich_note"):
        if col not in fieldnames:
            fieldnames.append(col)

    session = requests.Session()
    filled = missing = preserved = 0
    print(f"[enrich] {len(rows)}개 행 처리 시작\n")

    for i, row in enumerate(rows, 1):
        existing = row.get("contact_email", "").strip()
        if existing:
            row["email_source_url"] = row.get("email_source_url", "")
            row["email_dept"] = row.get("email_dept", "")
            row["manual_check"] = ""
            row["enrich_note"] = "preserved_existing"
            preserved += 1
            filled += 1
            continue

        homepage = normalize_url(row.get("homepage", ""))
        if not homepage:
            row["contact_email"] = ""
            row["email_source_url"] = ""
            row["email_dept"] = ""
            row["manual_check"] = "Y"
            row["enrich_note"] = "no_homepage"
            missing += 1
            continue

        target_type = row.get("type", "")
        email, src_url, dept = find_email(session, homepage, target_type)

        row["contact_email"] = email
        row["email_source_url"] = src_url
        row["email_dept"] = dept
        row["manual_check"] = "" if email else "Y"
        row["enrich_note"] = "ok" if email else "no_email_found"

        if email:
            filled += 1
        else:
            missing += 1

        if i % 20 == 0 or i == len(rows):
            print(f"  [{i:>3}/{len(rows)}]  채움 {filled}  /  미수집 {missing}")
        time.sleep(SLEEP)

    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    print(f"\n=== 완료 ===")
    print(f"  채움 {filled}건  (기존 보존 {preserved}건)")
    print(f"  미수집 {missing}건  (manual_check=Y 표시)")
    print(f"  → {OUTPUT}")


if __name__ == "__main__":
    main()
