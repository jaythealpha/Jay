# Yogibo 인스타 티징 — 후킹 이미지 1,000장 대량 생성 엔진

yogibo.kr(한국 시장 우선) 빈백 소파 **전체 라인업**을 대상으로, 스크롤을 멈추게 하는
**후킹 요소**가 강한 인스타그램 티징 이미지 1,000장을 자동으로 기획·생성하는 파이프라인.

> 1,000장을 손으로 만드는 게 아니라, **검증된 후킹 패턴을 조합 축으로 분해 → 무작위 추출로
> 1,000개 프롬프트 매니페스트 생성 → 이미지 생성 API로 배치 렌더링 → 한국어 카피 오버레이**
> 하는 구조다. 다양성·재현성·이어받기를 보장한다.

---

## 구성

| 파일 | 역할 |
|---|---|
| `data.py` | 후킹 요소 데이터셋 — 제품 18종 × 후킹 12유형(+카피 풀) × 장면 14 × 페르소나 12 × 스타일 12 |
| `generate_prompts.py` | 조합 공간에서 중복 없이 1,000개를 추출해 `prompts/manifest.{jsonl,csv}` 생성 |
| `batch_generate.py` | 매니페스트를 이미지 API로 배치 렌더링(동시성·재시도·이어받기) |
| `overlay.py` | 생성 이미지 위에 한국어 후킹 카피 합성(가독 그라데이션 + 외곽선) |
| `prompts/manifest.jsonl` | 1,000개 프롬프트(이미 생성됨, 즉시 사용 가능) |
| `prompts/manifest.csv` | 동일 내용 표 형태(검토·편집용) |

조합 공간 = 18 × 12 × 14 × 12 × 12 = **435,456개** → 이 중 1,000개를 균형 있게 샘플링.

---

## 후킹 요소(12 아키타입)

호기심 갭 · 감각/ASMR · 비포·애프터 · 문제 자극 · FOMO/희소성 · 사회적 증거 ·
변신/다용도 · 패턴 인터럽트 · 동경/라이프스타일 · 유머/공감 · 시즌/타이밍 · 가치/합리화

각 아키타입마다 한국어 티저 카피 5개씩 내장(`data.py` → `HOOKS`). 모두 1초 안에 읽히는 한 줄.

---

## 사용법

### 1) 프롬프트 매니페스트 생성 (의존성 없음)
```bash
python3 generate_prompts.py --count 1000 --seed 42
```
- 출력: `prompts/manifest.jsonl`, `prompts/manifest.csv`
- 제품·후킹·포맷별 분포 통계를 콘솔에 출력
- `--seed` 변경 시 다른 1,000개 조합(재현 가능)

### 2) 파이프라인 무료 점검 (API 없이)
```bash
pip install pillow
python3 batch_generate.py --provider mock --overlay --limit 10
```
- API 호출 없이 단색 플레이스홀더 + 한국어 카피 합성까지 전 구간 점검
- 한글 폰트 필요: `apt-get install fonts-nanum` 또는 `KOREAN_FONT=/경로/폰트.ttf`

### 3) 실제 1,000장 렌더링
```bash
pip install -r requirements.txt
export OPENAI_API_KEY=sk-...
python3 batch_generate.py --provider openai --concurrency 4 --overlay
```
- `output/yg_0001.png … yg_1000.png` 생성
- 중간에 끊겨도 재실행하면 `status == done` 항목은 건너뛰고 **이어받기**
- 25개마다 매니페스트에 진행 상태 저장

#### 다른 이미지 API를 쓰려면 (generic)
```bash
export IMAGE_API_URL=https://your-endpoint/generate
export IMAGE_API_KEY=...
python3 batch_generate.py --provider generic --concurrency 4 --overlay
```
응답 JSON에 `b64`(base64 PNG) 또는 `image_url` 필드가 있으면 된다.

---

## 옵션 요약

`batch_generate.py`
| 옵션 | 기본 | 설명 |
|---|---|---|
| `--provider` | `openai` | `openai` / `generic` / `mock` |
| `--concurrency` | `4` | 동시 생성 스레드 수(API rate limit 고려) |
| `--limit` | `0` | 처리 개수 상한(0=전체) |
| `--overlay` | off | 한국어 후킹 카피 합성 |

---

## 운영 메모

- **상표/로고 안전장치**: 이미지 프롬프트는 로고·브랜드 텍스트 없는 "프리미엄 빈백 소파"로 묘사하고,
  네거티브 프롬프트로 로고/워터마크를 배제한다. 브랜드 로고는 후반 작업에서 합성하는 것을 전제.
- **카피 검수**: 자동 생성된 카피는 발행 전 한 번 더 사람이 검수 권장(과장광고·표시광고법 유의).
- **비용/시간**: 1,000장은 API 단가 × 1,000. 먼저 `--limit 20`으로 톤을 확인한 뒤 전량 실행 권장.
- **확장**: 일본(yogibo.jp)·대만(yogibo.tw)은 `data.py`의 카피/장면 풀에 현지어 세트를 추가하면
  동일 엔진으로 재사용 가능.
