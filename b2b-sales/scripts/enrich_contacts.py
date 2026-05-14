"""
collect_targets.py가 만든 CSV를 받아서 부족한 이메일/담당부서를 보강.
홈페이지가 있는 기관은 정해진 패턴에서 '담당자 안내' 페이지를 긁어
이메일/전화/부서명을 추출한다.

사용:
  python enrich_contacts.py --input ../data/targets_school_서울특별시.csv

주의:
  - robots.txt 와 각 기관 사이트 이용약관을 확인할 것
  - 과도한 요청 방지를 위해 기본 1초 간격
"""

from __future__ import annotations

import argparse
import csv
import re
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"0\d{1,2}[-)\s]?\d{3,4}[-\s]?\d{4}")
KEYWORDS_PATHS = ["/contact", "/about", "/intro", "/organization", "/dept"]
KEYWORDS_KO = ["조직", "담당자", "연락처", "행정실", "오시는길", "안내"]


def fetch_html(url: str) -> str:
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": "yogibo-b2b/1.0"})
        if r.status_code == 200 and "text/html" in r.headers.get("Content-Type", ""):
            r.encoding = r.apparent_encoding
            return r.text
    except Exception:
        return ""
    return ""


def find_candidate_pages(homepage: str) -> list[str]:
    html = fetch_html(homepage)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    urls = {homepage}
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = (a.get_text() or "").strip()
        if any(k in href.lower() for k in KEYWORDS_PATHS) or any(k in text for k in KEYWORDS_KO):
            urls.add(urljoin(homepage, href))
    return list(urls)[:8]


def extract_contact(pages: list[str]) -> tuple[str, str]:
    for url in pages:
        html = fetch_html(url)
        if not html:
            continue
        email = EMAIL_RE.search(html)
        phone = PHONE_RE.search(html)
        if email:
            return email.group(0), (phone.group(0) if phone else "")
        time.sleep(1)
    return "", ""


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    args = p.parse_args()

    src = Path(args.input)
    rows = list(csv.DictReader(src.open(encoding="utf-8-sig")))
    for i, row in enumerate(rows, 1):
        if row.get("contact_email") or not row.get("homepage"):
            continue
        pages = find_candidate_pages(row["homepage"])
        email, phone = extract_contact(pages)
        if email:
            row["contact_email"] = email
        if phone and not row.get("phone"):
            row["phone"] = phone
        print(f"[{i}/{len(rows)}] {row['name']} → {email or '(no email)'}")
        time.sleep(1)

    out = src.with_name(src.stem + "_enriched.csv")
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    print(f"[OK] saved → {out}")


if __name__ == "__main__":
    main()
