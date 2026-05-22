#!/usr/bin/env python3
"""
요기보 인스타 티징 — 대량 이미지 생성 배치 러너

manifest.jsonl 의 1,000개 프롬프트를 이미지 생성 API로 렌더링한다.
- 동시성(스레드 풀) + 지수 백오프 재시도
- 이어받기(resume): status == "done" 인 항목은 건너뜀
- 생성 후 한국어 후킹 카피를 이미지 위에 합성(overlay.py, 선택)

지원 프로바이더:
  openai  : OPENAI_API_KEY 사용, gpt-image-1 (기본)
  generic : 임의 HTTP 엔드포인트(POST). 환경변수로 URL/키 지정
  mock    : API 호출 없이 플레이스홀더 PNG 생성(파이프라인 점검용)

사용 예:
  export OPENAI_API_KEY=sk-...
  python batch_generate.py --provider openai --concurrency 4
  python batch_generate.py --provider mock --limit 10   # 무료 점검
  python batch_generate.py --overlay                    # 카피 합성 켜기
"""
import argparse
import base64
import json
import os
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(HERE, "prompts", "manifest.jsonl")
OUT_DIR = os.path.join(HERE, "output")

_write_lock = threading.Lock()


def load_manifest(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def save_manifest(path, records):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def with_retry(fn, attempts=4, base_delay=2.0):
    last = None
    for n in range(attempts):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            last = e
            if n < attempts - 1:
                time.sleep(base_delay * (2 ** n))
    raise last


# --------------------------- 프로바이더 ---------------------------------
def gen_openai(rec):
    """OpenAI gpt-image-1. PNG bytes 반환."""
    from openai import OpenAI  # 지연 임포트
    client = OpenAI()
    # gpt-image-1 지원 사이즈로 매핑
    ar = rec["aspect_ratio"]
    size = {"1:1": "1024x1024", "4:5": "1024x1536", "9:16": "1024x1536"}.get(ar, "1024x1536")
    resp = client.images.generate(
        model="gpt-image-1",
        prompt=rec["image_prompt"],
        size=size,
        n=1,
    )
    return base64.b64decode(resp.data[0].b64_json)


def gen_generic(rec):
    """범용 HTTP 프로바이더. 응답에서 b64 또는 url을 추출."""
    import urllib.request
    url = os.environ["IMAGE_API_URL"]
    key = os.environ.get("IMAGE_API_KEY", "")
    payload = json.dumps({
        "prompt": rec["image_prompt"],
        "negative_prompt": rec["negative_prompt"],
        "size": rec["size"],
    }).encode()
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    if key:
        req.add_header("Authorization", f"Bearer {key}")
    with urllib.request.urlopen(req, timeout=120) as r:
        body = json.loads(r.read())
    if "b64" in body:
        return base64.b64decode(body["b64"])
    if "image_url" in body:
        with urllib.request.urlopen(body["image_url"], timeout=120) as ir:
            return ir.read()
    raise RuntimeError("generic 프로바이더 응답에 b64/image_url 없음")


def gen_mock(rec):
    """API 없이 단색 플레이스홀더 PNG. 파이프라인/오버레이 점검용."""
    try:
        from PIL import Image
    except ImportError as e:
        raise RuntimeError("mock 모드는 Pillow 필요: pip install pillow") from e
    import io
    w, h = (int(x) for x in rec["size"].split("x"))
    img = Image.new("RGB", (w, h), (220, 214, 205))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


PROVIDERS = {"openai": gen_openai, "generic": gen_generic, "mock": gen_mock}


# --------------------------- 워커 ---------------------------------------
def process(rec, provider_fn, do_overlay):
    out_path = os.path.join(OUT_DIR, f"{rec['id']}.png")
    img_bytes = with_retry(lambda: provider_fn(rec))
    with open(out_path, "wb") as f:
        f.write(img_bytes)
    if do_overlay:
        try:
            import overlay
            overlay.apply(out_path, rec["overlay_text_kr"])
        except Exception as e:  # noqa: BLE001
            print(f"[{rec['id']}] 오버레이 생략: {e}")
    rec["status"] = "done"
    rec["image_path"] = out_path
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", choices=list(PROVIDERS), default="openai")
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--limit", type=int, default=0, help="처리 개수 상한(0=전체)")
    ap.add_argument("--overlay", action="store_true", help="한국어 후킹 카피 합성")
    ap.add_argument("--manifest", default=MANIFEST)
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    records = load_manifest(args.manifest)
    provider_fn = PROVIDERS[args.provider]

    todo = [r for r in records if r.get("status") != "done"]
    if args.limit:
        todo = todo[: args.limit]
    print(f"대상 {len(todo)}개 / 전체 {len(records)}개 · provider={args.provider} · 동시성={args.concurrency}")

    done = 0
    from concurrent.futures import ThreadPoolExecutor, as_completed
    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futures = {ex.submit(process, r, provider_fn, args.overlay): r for r in todo}
        for fut in as_completed(futures):
            r = futures[fut]
            try:
                fut.result()
                done += 1
                print(f"  [{done}/{len(todo)}] {r['id']} ✓  {r['overlay_text_kr']}")
            except Exception as e:  # noqa: BLE001
                r["status"] = "error"
                print(f"  [ERR] {r['id']}: {e}")
            if done % 25 == 0:
                with _write_lock:
                    save_manifest(args.manifest, records)

    with _write_lock:
        save_manifest(args.manifest, records)
    ok = sum(1 for r in records if r.get("status") == "done")
    err = sum(1 for r in records if r.get("status") == "error")
    print(f"\n완료: 성공 {ok} · 실패 {err} · 출력 폴더 {OUT_DIR}")


if __name__ == "__main__":
    main()
