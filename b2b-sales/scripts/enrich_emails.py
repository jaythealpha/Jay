"""
이메일 추출 (homepage 크롤링 + 네이버 검색 폴백 → contact_email 자동 채우기)
=============================================================================
입력 : ./pilot_seoul_gyeonggi_200.csv
출력 : ./pilot_seoul_gyeonggi_200_enriched.csv

처리 순서:
  1) homepage 대표 페이지 크롤링 (mailto: → 텍스트 정규식)
  2) 보조 페이지 (/contact, /about, /이용안내 등) 시도
  3) 그래도 못 찾으면 NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 환경변수가 있을 때
     네이버 웹문서 검색 API 로 "{기관명} 이메일" 같은 쿼리 폴백
"""

from __future__ import annotations

import csv
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

INPUT = Path("pilot_seoul_gyeonggi_200.csv")
OUTPUT = Path("pilot_seoul_gyeonggi_200_enriched.csv")

TIMEOUT = 5
WORKERS = 10
USER_AGENT = "Mozilla/5.0 (compatible; YogiboB2BBot/1.0)"

NAVER_CLIENT_ID = os.environ.get("NAVER_CLIENT_ID", "").strip()
NAVER_CLIENT_SECRET = os.environ.get("NAVER_CLIENT_SECRET", "").strip()
NAVER_ENABLED = bool(NAVER_CLIENT_ID and NAVER_CLIENT_SECRET)

DEPT_KEYWORDS = {
    "school":  ["행정실", "총무부", "교무실", "교장실"],
    "library": ["사서실", "운영팀", "관리과", "정보봉사", "문의"],
    "gov":     ["총무과", "청년정책", "복지문화", "기획", "민원"],
}

SECONDARY_PATHS = {
    "school":  ["/contact", "/about", "/이용안내"],
    "library": ["/contact", "/about", "/이용안내", "/오시는길"],
    "gov":     ["/contact", "/cs", "/cs/contact", "/main/contact",
                "/intro/intro", "/orgInfo", "/department", "/global"],
}
DEFAULT_SECONDARY = ["/contact", "/about", "/이용안내"]

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
BAD_PREFIX = ("noreply@", "no-reply@", "donotreply@", "do-not-reply@")
BAD_DOMAINS = ("example.com", "test.com", "sample.com")

EXTRA_COLS = ("email_source_url", "email_dept", "manual_check", "enrich_note")

NAVER_QUERIES = {
    "school":  ["{name} 행정실 이메일", "{name} 연락처 이메일"],
    "library": ["{name} 사서실 이메일", "{name} 이메일"],
    "gov":     ["{name} 이메일", "{name} 대표 메일"],
}


def fetch(url, session):
    try:
        r = session.get(url, timeout=TIMEOUT, headers={"User-Agent": USER_AGENT})
        if r.status_code != 200:
            return None
        r.encoding = r.apparent_encoding or "utf-8"
        return r.text
    except Exception:
        return None


def extract_candidates(html):
    soup = BeautifulSoup(html, "html.parser")
    candidates = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.lower().startswith("mailto:"):
            email = href[7:].split("?")[0].strip()
            if EMAIL_RE.fullmatch(email):
                parent = a.find_parent()
                ctx = parent.get_text(" ", strip=True)[:300] if parent else ""
                candidates.append((email, ctx, "mailto"))
    text = soup.get_text(" ", strip=True)
    for m in EMAIL_RE.finditer(text):
        email = m.group(0)
        start = max(0, m.start() - 80)
        end = min(len(text), m.end() + 80)
        candidates.append((email, text[start:end], "text"))
    return candidates


def is_junk(email):
    el = email.lower()
    if el.startswith(BAD_PREFIX):
        return True
    if any(el.endswith("@" + d) for d in BAD_DOMAINS):
        return True
    if el.endswith((".png", ".jpg", ".gif", ".svg")):
        return True
    return False


def pick_best(candidates, target_type):
    if not candidates:
        return None, "", ""
    seen = set()
    deduped = []
    for email, ctx, src in candidates:
        e = email.lower()
        if e in seen or is_junk(email):
            continue
        seen.add(e)
        deduped.append((email, ctx, src))
    if not deduped:
        return None, "", ""
    for kw in DEPT_KEYWORDS.get(target_type, []):
        for email, ctx, src in deduped:
            if kw in ctx:
                return email, kw, src
    for email, ctx, src in deduped:
        if src == "mailto":
            return email, "", src
    return deduped[0][0], "", deduped[0][2]


def normalize_url(url):
    if not url:
        return None
    url = url.strip()
    if not url or url in ("-", "N/A"):
        return None
    if not url.startswith(("http://", "https://")):
        url = "http://" + url
    return url


def crawl_homepage(homepage, target_type):
    session = requests.Session()
    html = fetch(homepage, session)
    cands = extract_candidates(html) if html else []
    chosen_url = homepage if cands else ""

    if not cands:
        parsed = urlparse(homepage)
        base = f"{parsed.scheme}://{parsed.netloc}"
        for path in SECONDARY_PATHS.get(target_type, DEFAULT_SECONDARY):
            sub_url = urljoin(base, path)
            sub_html = fetch(sub_url, session)
            if sub_html:
                sub_c = extract_candidates(sub_html)
                if sub_c:
                    cands = sub_c
                    chosen_url = sub_url
                    break

    email, dept, _ = pick_best(cands, target_type)
    return (email or ""), (chosen_url if email else ""), dept


def naver_search_email(name, target_type):
    if not NAVER_ENABLED or not name:
        return "", ""
    templates = NAVER_QUERIES.get(target_type, ["{name} 이메일"])
    for tpl in templates:
        query = tpl.format(name=name)
        try:
            r = requests.get(
                "https://openapi.naver.com/v1/search/webkr.json",
                params={"query": query, "display": 10},
                headers={
                    "X-Naver-Client-Id": NAVER_CLIENT_ID,
                    "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
                    "User-Agent": USER_AGENT,
                },
                timeout=TIMEOUT,
            )
            if r.status_code != 200:
                continue
            items = r.json().get("items", [])
        except Exception:
            continue

        for item in items:
            blob = " ".join([item.get("title", ""), item.get("description", "")])
            blob = re.sub(r"<[^>]+>", " ", blob)
            for m in EMAIL_RE.finditer(blob):
                email = m.group(0)
                if is_junk(email):
                    continue
                return email, item.get("link", "")
    return "", ""


def save(rows, fieldnames):
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def process_one(idx, row):
    existing = row.get("contact_email", "").strip()
    if existing:
        return idx, existing, "", "", "", "preserved_existing"

    name = row.get("name", "").strip()
    target_type = row.get("type", "")
    homepage = normalize_url(row.get("homepage", ""))

    if homepage:
        try:
            email, src_url, dept = crawl_homepage(homepage, target_type)
        except Exception as e:
            email, src_url, dept = "", "", f"error:{type(e).__name__}"
        if email:
            return idx, email, src_url, dept, "", "ok"

    if NAVER_ENABLED:
        try:
            n_email, n_url = naver_search_email(name, target_type)
        except Exception:
            n_email, n_url = "", ""
        if n_email:
            return idx, n_email, n_url, "", "", "ok_naver"

    if not homepage:
        return idx, "", "", "", "Y", "no_homepage"
    return idx, "", "", "", "Y", "no_email_found"


def main():
    if not INPUT.exists():
        sys.exit(f"[중단] 입력 파일 없음: {INPUT}")

    with INPUT.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])

    for col in EXTRA_COLS:
        if col not in fieldnames:
            fieldnames.append(col)
        for row in rows:
            row.setdefault(col, "")

    print(f"[enrich] {len(rows)}개 행 / workers={WORKERS} / 네이버={'ON' if NAVER_ENABLED else 'OFF'}\n")
    t0 = time.time()
    done = filled = naver_hits = 0

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futures = {ex.submit(process_one, i, r): i for i, r in enumerate(rows)}
        for fut in as_completed(futures):
            idx, email, src_url, dept, manual, note = fut.result()
            rows[idx]["contact_email"] = email
            rows[idx]["email_source_url"] = src_url
            rows[idx]["email_dept"] = dept
            rows[idx]["manual_check"] = manual
            rows[idx]["enrich_note"] = note
            done += 1
            if email:
                filled += 1
                if note == "ok_naver":
                    naver_hits += 1
            if done % 25 == 0 or done == len(rows):
                elapsed = time.time() - t0
                print(f"  [{done:>3}/{len(rows)}]  채움 {filled} (네이버 {naver_hits})  /  경과 {elapsed:.0f}s")
                save(rows, fieldnames)

    save(rows, fieldnames)
    print(f"\n=== 완료 ===")
    print(f"  채움 {filled}건 (홈페이지 {filled-naver_hits} + 네이버 {naver_hits})")
    print(f"  미수집 {len(rows)-filled}건 / 총 {time.time()-t0:.0f}s")
    print(f"  → {OUTPUT}")


if __name__ == "__main__":
    main()
