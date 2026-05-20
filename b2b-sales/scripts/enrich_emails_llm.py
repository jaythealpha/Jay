"""
LLM 기반 이메일 추출 — 홈페이지 크롤링 + 네이버 검색으로 못 찾은 행만 처리
=========================================================================
입력 : pilot_seoul_gyeonggi_200_enriched.csv (manual_check=Y 인 행만 대상)
출력 : 같은 파일 in-place 업데이트

LLM이 페이지 텍스트를 직접 읽고 가장 적합한 부서 이메일을 추출.
"""

from __future__ import annotations

import csv
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import anthropic
import requests
from bs4 import BeautifulSoup

INPUT = OUTPUT = Path("pilot_seoul_gyeonggi_200_enriched.csv")
MODEL = "claude-haiku-4-5"
WORKERS = 5
TIMEOUT = 8
PAGE_TEXT_LIMIT = 8000  # 토큰 절약
USER_AGENT = "Mozilla/5.0 (compatible; YogiboB2BBot/1.0)"

SYSTEM_PROMPT = """당신은 한국 공공기관/학교/도서관 웹페이지에서 담당자 이메일을 찾는 전문 추출기입니다.

규칙:
1. 페이지 내용을 분석하여 가장 적합한 담당자의 이메일 주소를 찾으세요.
2. 부서 우선순위:
   - 학교(school): 행정실 > 총무부 > 교무실 > 교장실
   - 도서관(library): 사서실 > 운영팀 > 관리과 > 정보봉사 > 문의처
   - 시·구청(gov): 총무과 > 청년정책과 > 복지문화과 > 기획과 > 민원실
3. 페이지에 이메일이 없거나 의심스러우면 email 필드에 "NONE" 반환.
4. noreply/no-reply 같은 자동발송 이메일은 NONE 처리.
5. 페이지에 명시된 부서명이 있으면 정확히 그대로 기재.
"""

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "email": {
            "type": "string",
            "description": "찾은 이메일 주소 또는 'NONE'",
        },
        "department": {
            "type": "string",
            "description": "이메일과 연관된 부서명 (예: 행정실). 모르면 빈 문자열.",
        },
        "confidence": {
            "type": "string",
            "enum": ["high", "medium", "low"],
            "description": "high=mailto/명확 부서, medium=페이지에 있음, low=추측",
        },
    },
    "required": ["email", "department", "confidence"],
    "additionalProperties": False,
}

EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")

client = anthropic.Anthropic()


def fetch_page_text(url: str) -> str | None:
    try:
        r = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": USER_AGENT})
        if r.status_code != 200:
            return None
        r.encoding = r.apparent_encoding or "utf-8"
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = soup.get_text(" ", strip=True)
        return text[:PAGE_TEXT_LIMIT]
    except Exception:
        return None


def extract_email_with_llm(name: str, target_type: str, page_text: str) -> dict | None:
    user_msg = (
        f"기관명: {name}\n유형: {target_type}\n\n"
        f"페이지 내용:\n{page_text}\n\n"
        "위 페이지에서 가장 적합한 담당자 이메일을 찾아 JSON으로 반환하세요."
    )
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=200,
            system=[{
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{"role": "user", "content": user_msg}],
            output_config={"format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}},
        )
    except anthropic.APIError as e:
        print(f"  [api_error] {name}: {type(e).__name__}", flush=True)
        return None

    text = next((b.text for b in response.content if b.type == "text"), "")
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def normalize_url(url: str) -> str | None:
    if not url:
        return None
    url = url.strip()
    if not url or url in ("-", "N/A"):
        return None
    if not url.startswith(("http://", "https://")):
        url = "http://" + url
    return url


def process_row(idx: int, row: dict) -> tuple[int, dict | None]:
    homepage = normalize_url(row.get("homepage", ""))
    if not homepage:
        return idx, None

    page_text = fetch_page_text(homepage)
    if not page_text:
        return idx, None

    result = extract_email_with_llm(row.get("name", ""), row.get("type", ""), page_text)
    if not result:
        return idx, None

    email = result.get("email", "NONE").strip()
    if email == "NONE" or not EMAIL_RE.match(email):
        return idx, None
    if email.lower().startswith(("noreply@", "no-reply@", "donotreply@")):
        return idx, None

    return idx, {
        "email": email,
        "dept": result.get("department", ""),
        "url": homepage,
        "confidence": result.get("confidence", "medium"),
    }


def save(rows, fieldnames):
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    if not os.environ.get("ANTHROPIC_API_KEY", "").strip():
        sys.exit("[중단] ANTHROPIC_API_KEY 환경변수가 비어 있습니다.")
    if not INPUT.exists():
        sys.exit(f"[중단] 입력 파일 없음: {INPUT} (먼저 enrich_emails.py 가 실행되어야 함)")

    with INPUT.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])

    targets = [(i, r) for i, r in enumerate(rows) if r.get("manual_check", "") == "Y"]
    print(f"[LLM] {len(targets)}개 대상 / 전체 {len(rows)} 중 / model={MODEL} / workers={WORKERS}\n")

    if not targets:
        print("처리할 대상 없음.")
        return

    t0 = time.time()
    filled = done = 0
    by_conf = {"high": 0, "medium": 0, "low": 0}

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futures = {ex.submit(process_row, i, r): i for i, r in targets}
        for fut in as_completed(futures):
            idx, result = fut.result()
            done += 1
            if result:
                rows[idx]["contact_email"] = result["email"]
                rows[idx]["email_source_url"] = result["url"]
                rows[idx]["email_dept"] = result["dept"]
                rows[idx]["manual_check"] = ""
                rows[idx]["enrich_note"] = f"ok_llm_{result['confidence']}"
                by_conf[result["confidence"]] += 1
                filled += 1
            if done % 20 == 0 or done == len(targets):
                elapsed = time.time() - t0
                print(f"  [{done:>3}/{len(targets)}] 채움 {filled}  /  경과 {elapsed:.0f}s", flush=True)
                save(rows, fieldnames)

    save(rows, fieldnames)
    print(f"\n=== LLM 완료 ===")
    print(f"  추가 채움 {filled}건 (high {by_conf['high']} / medium {by_conf['medium']} / low {by_conf['low']})")
    print(f"  대상 {len(targets)}건 / 총 {time.time()-t0:.0f}s")
    print(f"  → {OUTPUT}")


if __name__ == "__main__":
    main()
