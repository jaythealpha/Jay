"""
이메일 추출 (homepage 크롤링 → contact_email 자동 채우기)
===========================================================
입력 : ./pilot_seoul_gyeonggi_200.csv
출력 : ./pilot_seoul_gyeonggi_200_enriched.csv

특징:
  - ThreadPoolExecutor 로 10개 동시 처리
  - 타임아웃 5초, 보조 페이지 3개로 축소
  - 매 25건마다 중간 저장 (job 타임아웃 대비)
"""

from __future__ import annotations

import csv
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

DEPT_KEYWORDS = {
    "school":  ["행정실", "총무부", "교무실", "교장실"],
    "library": ["사서실", "운영팀", "관리과", "정보봉사", "문의"],
    "gov":     ["총무과", "청년정책", "복지문화", "기획", "민원"],
}

SECONDARY_PATHS = ["/contact", "/about", "/이용안내"]

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
BAD_PREFIX = ("noreply@", "no-reply@", "donotreply@", "do-not-reply@")
BAD_DOMAINS = ("example.com", "test.com", "sample.com")

EXTRA_COLS = ("email_source_url", "email_dept", "manual_check", "enrich_note")


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


def find_email_for(homepage, target_type):
    session = requests.Session()
    html = fetch(homepage, session)
    cands = extract_candidates(html) if html else []
    chosen_url = homepage if cands else ""

    if not cands:
        parsed = urlparse(homepage)
        base = f"{parsed.scheme}://{parsed.netloc}"
        for path in SECONDARY_PATHS:
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


def save(rows, fieldnames):
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def process_one(idx, row):
    """병렬 워커가 호출하는 단위 작업"""
    existing = row.get("contact_email", "").strip()
    if existing:
        return idx, existing, "", "", "", "preserved_existing"

    homepage = normalize_url(row.get("homepage", ""))
    if not homepage:
        return idx, "", "", "", "Y", "no_homepage"

    target_type = row.get("type", "")
    try:
        email, src_url, dept = find_email_for(homepage, target_type)
    except Exception as e:
        return idx, "", "", "", "Y", f"error:{type(e).__name__}"

    if email:
        return idx, email, src_url, dept, "", "ok"
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

    print(f"[enrich] {len(rows)}개 행, workers={WORKERS}, timeout={TIMEOUT}s\n")
    t0 = time.time()
    done = filled = 0

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
            if done % 25 == 0 or done == len(rows):
                elapsed = time.time() - t0
                print(f"  [{done:>3}/{len(rows)}]  채움 {filled}  /  경과 {elapsed:.0f}s")
                save(rows, fieldnames)  # 중간 저장

    save(rows, fieldnames)
    print(f"\n=== 완료 ===  채움 {filled}건 / 미수집 {len(rows)-filled}건 / {time.time()-t0:.0f}s")
    print(f"  → {OUTPUT}")


if __name__ == "__main__":
    main()
