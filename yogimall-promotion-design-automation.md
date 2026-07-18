# 요기몰 자사몰 프로모션 디자인 시안 자동화 시스템 설계

> 작성일: 2026-07-18
> 목적: 프로모션 컨셉 프롬프트 → 자사몰(cafe24) 운용 가능한 디자인 에셋·상세페이지 자동 생성
> 대상 병목: 시안 리드타임 5~7일 → 4시간 이내 (30배 단축)

---

## 0. TL;DR

프로모션 담당자가 "8월 15일 광복절, 전 상품 15%, 3일간, 여름 마무리 세일" 한 줄만 입력하면,
- cafe24 메인 배너(PC 1920×540, 모바일 720×720)
- 카테고리 리스트 배너 (반응형 2종)
- 랜딩페이지 풀세트 (히어로/USP/상품그리드/CTA/타이머/FAQ)
- 상세페이지 상단부 프로모션 헤더 (860px)
- 이메일·카톡 채널메시지·SNS 정사각/스토리 리사이즈본

까지 **1회 실행 기준 40개 에셋**을 자동으로 뽑아, 검수 대기열에 올려주는 시스템이다.

핵심 원리: **(1) 컨셉 프롬프트 → 구조화된 브리프 JSON → (2) 카피 생성 LLM + (3) 이미지 생성 파이프라인 + (4) 템플릿 조립 엔진 → (5) 브랜드 가드레일 검증 → (6) 검수 큐**.

---

## 1. 문제 정의: "프로모션 병목"의 실체

### 1.1 현재 워크플로우 (As-Is)
```
기획팀 브리프 작성 (0.5일)
  → 디자인팀 시안 1차 (2~3일)
    → 컨펌 라운드 2~3회 (1~2일)
      → cafe24 규격·모바일 리사이즈 (1일)
        → 개발팀 랜딩페이지 조립 (0.5~1일)
           총 5~7영업일
```

### 1.2 병목의 근본 원인
| 원인 | 비율(체감) | 자동화 가능성 |
|---|---|---|
| 반복적 규격 리사이즈 (PC/모바일/SNS) | 30% | ★★★★★ |
| 카피 초안 왕복(기획 ↔ 디자이너) | 25% | ★★★★★ |
| 상품 이미지 누끼·톤보정 | 15% | ★★★★☆ |
| 브랜드 가이드 이탈로 인한 재작업 | 15% | ★★★★☆ |
| 상세페이지 섹션 재조립(HTML/CSS) | 10% | ★★★★★ |
| 창의적 컨셉 결정 | 5% | ★★☆☆☆ |

**시사점**: 병목의 95%는 "규격·조립·리사이즈" 같은 반복 작업이다. 창의성이 아니라 **파이프라인 부재**가 진짜 병목이다.

### 1.3 목표 워크플로우 (To-Be)
```
프로모션 컨셉 프롬프트 (5분)
  → 자동 생성 (10분) → 40개 에셋 초안
    → 담당자 검수·수정 (2~3시간)
      → cafe24 자동 업로드 (10분)
         총 4시간 이내
```

---

## 2. 시스템 개요 — "PromoForge"

```
              ┌──────────────────────────────────────────┐
              │        PromoForge (자동화 오케스트레이터)         │
              └──────────────────────────────────────────┘
                              │
   ┌──────────────┬───────────┼───────────┬──────────────┐
   ▼              ▼           ▼           ▼              ▼
[① Brief    [② Copy      [③ Visual   [④ Template  [⑤ Guardrail
 Extractor]  Generator]   Engine]     Assembler]    Validator]
   │              │           │           │              │
   ▼              ▼           ▼           ▼              ▼
프롬프트→JSON   Claude API   Flux/SDXL   HTML+CSS      브랜드 검증
                            +LoRA       템플릿         (색/폰트/로고)
                              │           │              │
                              └───────────┴──────┬───────┘
                                                 ▼
                                       [⑥ Review Queue]
                                                 │
                                                 ▼
                                       [⑦ cafe24 API 업로드]
```

### 2.1 구성 요소 요약
1. **Brief Extractor**: 자연어 프롬프트 → 구조화 JSON (Claude API, 스키마 강제)
2. **Copy Generator**: 헤드라인·서브카피·CTA·FAQ 카피 생성
3. **Visual Engine**: 배경/오브젝트 이미지 생성 (Flux + 요기보 LoRA)
4. **Template Assembler**: 사전 정의된 cafe24 섹션 템플릿에 카피·이미지 주입
5. **Guardrail Validator**: 브랜드 색/폰트/금칙어/할인율 상한 검증
6. **Review Queue**: 검수자 승인/반려 UI (Notion or Slack)
7. **cafe24 Publisher**: 승인된 에셋을 cafe24 관리자 API로 자동 배포

---

## 3. 입력 스키마 — "프로모션 브리프"

### 3.1 자연어 프롬프트 예시 (담당자 입력)
```
8월 15일 광복절 기념 프로모션.
전 상품 15% 할인, 특별 컬러 "코리아 레드" 한정판 30% 할인.
기간: 8/13(수) 00:00 ~ 8/17(일) 23:59.
타깃: 20~30대 1인 가구.
톤: 시원한 여름 마무리 + 애국심 자극(과하지 않게).
포함 상품: Max 라인 3종, Midi 라인 2종, Mini K.
```

### 3.2 자동 추출되는 구조화 JSON
```json
{
  "campaign": {
    "id": "yg-2026-0815-liberation",
    "name": "광복절 기념 코리아 레드 세일",
    "start_at": "2026-08-13T00:00:00+09:00",
    "end_at":   "2026-08-17T23:59:59+09:00",
    "theme": "liberation-day-summer-closing",
    "tone": ["cool", "patriotic-subtle", "premium"]
  },
  "offer": [
    { "scope": "all",            "type": "percent", "value": 15 },
    { "scope": "sku:korea-red",  "type": "percent", "value": 30, "highlight": true }
  ],
  "audience": {
    "age": "20-39",
    "household": "single",
    "lifestyle": ["home-office", "small-apt"]
  },
  "products": [
    { "sku": "max-premium",   "line": "Max"  },
    { "sku": "max-lounger",   "line": "Max"  },
    { "sku": "max-double",    "line": "Max"  },
    { "sku": "midi-standard", "line": "Midi" },
    { "sku": "midi-classic",  "line": "Midi" },
    { "sku": "mini-k",        "line": "Mini" }
  ],
  "constraints": {
    "avoid_words": ["대박", "최저가", "폭탄세일"],
    "must_include": ["요기 타임", "무료 반품 30일"],
    "max_discount_visible": 30
  }
}
```

### 3.3 스키마 규칙
- `start_at`/`end_at`는 KST 명시 필수 (타이머 렌더링 정확도)
- `offer.scope`는 `all` | `sku:*` | `category:*` 만 허용
- `constraints.avoid_words`는 브랜드 톤 유지용 금칙어 (기본값 시스템 프리셋 + 캠페인 추가)
- LLM 파싱 실패 시 담당자에게 재질문 3턴까지 허용

---

## 4. 출력 에셋 정의

### 4.1 에셋 카탈로그 (1회 실행 = 40장)

| 카테고리 | 항목 | 규격 (px) | 수량 |
|---|---|---|---|
| **cafe24 메인** | PC 히어로 배너 | 1920×540 | 2 (A/B) |
|  | 모바일 히어로 | 720×720 | 2 (A/B) |
|  | 카테고리 상단 | 1200×300 | 3 |
| **랜딩페이지** | 히어로 섹션 | 1920×900 | 1 |
|  | USP 3분할 | 1200×400 | 1 |
|  | 상품 그리드 카드 | 400×500 | 6 (상품별) |
|  | CTA 배너 | 1920×280 | 2 |
|  | 카운트다운 배경 | 1920×200 | 1 |
|  | FAQ 아이콘셋 | 80×80 | 5 |
| **상세페이지 헤더** | 프로모션 스티커 | 860×300 | 6 (상품별) |
| **SNS 리사이즈** | 인스타 정사각 | 1080×1080 | 2 |
|  | 인스타 스토리 | 1080×1920 | 2 |
|  | 카카오톡 채널 메시지 | 800×400 | 1 |
| **이메일** | 뉴스레터 헤더 | 600×300 | 1 |
| **HTML** | 랜딩페이지 조립본 | - | 1 |
|  | 상세페이지 프로모션 섹션 스니펫 | - | 1 |

### 4.2 파일 명명 규칙
```
{campaign_id}/{surface}/{variant}_{width}x{height}.{ext}
예: yg-2026-0815-liberation/main/hero-A_1920x540.jpg
    yg-2026-0815-liberation/landing/index.html
```

---

## 5. 파이프라인 아키텍처

### 5.1 데이터 플로우
```
[프롬프트]
    ↓  Claude API (structured output, JSON schema 강제)
[Brief JSON]
    ↓  fan-out (5개 병렬 워커)
    ├──→ [Copy Worker]     → headlines[], sub[], CTAs[], FAQs[]
    ├──→ [Visual Worker]   → background_prompts[] → Flux 이미지 N장
    ├──→ [Product Worker]  → SKU 이미지 조회 → 누끼 자동화(rembg) → 톤 통일
    ├──→ [Layout Worker]   → 그리드/스택 레이아웃 계산 (규격별)
    └──→ [Timer Worker]    → 카운트다운 JS 컴포넌트 파라미터
        ↓
[Template Assembler] — 사전 정의 HTML/CSS/SVG 템플릿에 슬롯 채움
        ↓
[Rasterizer] — Playwright + headless Chrome → PNG/JPG 렌더 (Retina 2x)
        ↓
[Guardrail Validator] — 색/폰트/금칙어/할인율/로고 clearspace 자동 체크
        ↓
[Review Queue] — Slack 스레드 + Notion 데이터베이스 로우 자동 생성
        ↓ (승인 시)
[cafe24 Publisher] — 관리자 API로 배너 슬롯·게시판·상품 상단 이미지 교체
```

### 5.2 병렬성·성능 예산
- Claude API 호출: 브리프 파싱 1회 + 카피 1회 = 2회 (~15초)
- 이미지 생성: 8장 병렬, 장당 6초 = 총 24초 (동시성 8)
- 누끼·리사이즈·라스터화: 40장 병렬, 장당 1.5초 = 총 8초
- 템플릿 조립+검증: 15초
- **엔드투엔드 목표: 90초 이내 (버퍼 포함 10분)**

---

## 6. 기술 스택

| 계층 | 선택 | 이유 |
|---|---|---|
| 오케스트레이션 | Node.js + Temporal | 워크플로우 재시도·중단·재개 |
| LLM (카피/브리프) | Claude Opus 4.8 (구조화 출력) | 한국어 카피 톤, JSON 강제 |
| 이미지 생성 | Flux.1 Pro + 요기보 브랜드 LoRA | 자체 학습 LoRA로 브랜드 일관성 |
| 상품 누끼 | rembg + BiRefNet | 오픈소스, 서버리스 배치 |
| 라스터화 | Playwright + Chromium | HTML→PNG, 픽셀 완벽 재현 |
| 템플릿 | React + Tailwind CSS + SVG | 반응형/2x/컴포넌트화 |
| 검수 UI | Notion Database + Slack Workflow | 조직 이미 사용, 커스텀 UI 불필요 |
| 저장소 | S3 + CloudFront | CDN 원본·라스터본 분리 관리 |
| cafe24 연동 | cafe24 Admin API v2 | 배너/게시판/상품 API 지원 |

### 6.1 브랜드 LoRA 학습
- 학습 이미지: 요기보 공식 화보 300장 + 3D 렌더 500장 + 실제 룩북 200장
- 학습 대상: 빈백 텍스처·앉음새·컬러 매칭·조명 톤
- 트리거 워드: `<yogibo-style>` / `<yogibo-max>` / `<yogibo-mini>`

---

## 7. 브랜드 가드레일 (자동 검증 규칙)

### 7.1 하드 룰 (위반 시 자동 반려)
```yaml
color:
  primary_allowed: ["#E60023", "#111111", "#FFFFFF"]  # 요기보 코리아 레드/블랙/화이트
  discount_badge: "#111111 on #FFD400"                # 할인 뱃지 조합 고정
  max_non_brand_ratio: 0.15                           # 비브랜드 컬러 15% 이하

typography:
  hero:      { family: "Pretendard", weight: 800, min_size: 48 }
  subhead:   { family: "Pretendard", weight: 600, min_size: 24 }
  body:      { family: "Pretendard", weight: 400, min_size: 16 }

logo:
  clearspace: 1.0        # 로고 높이의 100% 여백
  min_height_px: 32
  allowed_variants: ["red-on-white", "white-on-red", "black-on-white"]

copy:
  forbidden_words: ["최저가", "폭탄", "대박", "역대급", "무조건"]
  discount_display:
    max_percent: 40
    require_original_price: true

accessibility:
  wcag_contrast_min: 4.5
  alt_text_required: true
```

### 7.2 소프트 룰 (경고만, 검수자 판단)
- 상품 이미지 하나에 로고 2개 이상
- 히어로 카피 20자 초과
- CTA 버튼 3개 초과
- 카피 감탄사(!!!) 2개 초과

---

## 8. 템플릿 라이브러리

### 8.1 랜딩페이지 섹션 컴포넌트 (React)
```
<PromoLanding>
  <Hero variant="split|full|video-bg" />
  <Countdown deadline={end_at} />
  <BenefitStrip items={3} />
  <ProductGrid skus={products} layout="2col-mobile-4col-pc" />
  <UGCWall source="instagram-hashtag" limit={9} />
  <FAQAccordion items={faqs} />
  <StickyBottomCTA />
</PromoLanding>
```

### 8.2 cafe24 배너 슬롯 매핑
| cafe24 슬롯 | 노출 위치 | 자동 갱신 방법 |
|---|---|---|
| `main_banner_top` | 홈 최상단 슬라이드 | `PUT /api/v2/admin/banners/{id}` |
| `main_banner_mid` | 홈 중단 배너 | 위와 동일 |
| `category_top_{cid}` | 카테고리 상단 | `PUT /api/v2/admin/categories/{cid}/banner` |
| `product_detail_header_{sku}` | 상세페이지 상단 프로모션 이미지 | `PATCH /api/v2/admin/products/{sku}` (`detail_image` 필드) |
| `board_notice_new` | 공지사항 게시글 (프로모션 안내) | `POST /api/v2/admin/boards/notice/articles` |

### 8.3 상세페이지 상단 스니펫 (HTML)
```html
<!-- yogibo:promo-header:start id={{campaign_id}} -->
<div class="yg-promo-header" style="--accent:#E60023;">
  <div class="yg-promo-badge">{{discount_headline}}</div>
  <div class="yg-promo-title">{{campaign_name}}</div>
  <div class="yg-promo-period">{{period_display}}</div>
  <div class="yg-promo-countdown" data-end="{{end_at_iso}}"></div>
</div>
<!-- yogibo:promo-header:end -->
```
- 시작/끝 코멘트로 구간 식별 → 프로모션 종료 시 스니펫만 안전하게 제거
- CSS 변수 `--accent`로 캠페인별 강조색 오버라이드

---

## 9. 프롬프트 → 결과물 예시

### 9.1 입력 (담당자)
> "9월 첫째 주 신학기 프로모션. Yogibo Work 라인 20% 할인. 재택근무 대학원생 타깃. 톤은 차분한 프리미엄. 기간 9/1~9/7."

### 9.2 자동 생성 카피 (Claude 출력 예)
```
[히어로 헤드라인 A]  집중이 오래 가는 자세.
[히어로 헤드라인 B]  하루 8시간, 허리를 위한 선택.
[서브카피]           Yogibo Work 라인 20% · 9/1(월) - 9/7(일)
[CTA]               지금 편해지기 →
[FAQ 3종]           1) 사이즈 선택 · 2) 조립 필요 여부 · 3) 30일 홈트라이얼
```

### 9.3 자동 생성 이미지 (Flux 프롬프트 예)
```
photo of a person in their late 20s working on a laptop
while sitting on a large <yogibo-work> beanbag chair in warm gray,
minimalistic scandinavian home office, soft afternoon light,
natural window light, shot on 35mm, cinematic, 4k, calm mood
--ar 16:9 --style raw
```

### 9.4 검수자 확인 링크 (Slack 알림 자동 발송)
```
✅ [PromoForge] 신학기 프로모션 시안 40장 생성 완료
▸ Notion 검수 페이지: notion.so/yogibo/promoforge/yg-2026-0901-newsem
▸ 예상 노출: 9/1 00:00
▸ 승인 필요 항목: 히어로 A/B, 상품 카드 6종, 이메일 헤더
[승인] [수정 요청] [전체 재생성]
```

---

## 10. 구현 로드맵

### Phase 0 — 사전 준비 (2주)
- 요기보 브랜드 가이드 디지털화 (색/폰트/로고/톤앤매너 JSON)
- 과거 프로모션 시안 100건 라벨링 (템플릿 유형 분류)
- 상품 SKU 마스터 이미지 정비 (누끼 원본 확보)

### Phase 1 — MVP (4주)
- 브리프 파서(Claude 구조화 출력)
- 배너 3규격 자동 생성 (PC 히어로, 모바일 히어로, 카테고리 상단)
- Notion 검수 큐 연동
- **목표**: 리드타임 5일 → 1일

### Phase 2 — 랜딩페이지 조립 (6주)
- React 섹션 컴포넌트 라이브러리 완성
- Playwright 라스터화 파이프라인
- cafe24 배너 API 자동 업로드
- **목표**: 리드타임 1일 → 4시간

### Phase 3 — 상세페이지·SNS 확장 (4주)
- 상품 상세페이지 상단 스니펫 삽입/제거 자동화
- 인스타·카카오톡 리사이즈 자동화
- 브랜드 LoRA v1 학습 완료
- **목표**: 캠페인당 담당자 실작업 30분

### Phase 4 — 최적화 & 학습 루프 (지속)
- A/B 테스트 결과를 프롬프트 라이브러리에 자동 반영
- 검수자 반려 사유 학습 → 프롬프트 자동 튜닝
- 시즌별 프리셋 자동 제안 (여름/겨울/신학기/블프)

---

## 11. 품질 관리 & 승인 플로우

### 11.1 3단계 게이트
```
[게이트 1] 자동 검증        → 하드 룰 위반 시 자동 재생성 (최대 3회)
[게이트 2] 담당 디자이너 검수 → 예술적 판단·미세 수정
[게이트 3] 마케팅 리드 승인   → 캠페인 전략 일치 여부 최종 확인
```

### 11.2 반려 사유 코드 (학습용)
| 코드 | 사유 | 재학습 반영 |
|---|---|---|
| R01 | 브랜드 톤 이탈 | 프롬프트 negative에 추가 |
| R02 | 카피 어색함 | Claude 시스템 프롬프트 업데이트 |
| R03 | 이미지 상품 왜곡 | LoRA 재학습 데이터 추가 |
| R04 | 규격 오류 | 템플릿 CSS 수정 |
| R05 | 오탈자 | 사전 사전 강화 |

### 11.3 롤백
- 각 캠페인 발행은 **원자적 커밋**으로 기록 (배포 전 스냅샷)
- 문제 발생 시 `promoforge rollback {campaign_id}` 한 줄로 cafe24 배너 원복

---

## 12. KPI

| 지표 | 현재 | Y1 목표 |
|---|---|---|
| 캠페인 시안 리드타임 | 5~7일 | 4시간 |
| 디자이너 1인당 월 캠페인 처리 수 | 4건 | 20건 |
| 브랜드 가이드 위반 리워크율 | 22% | 3% |
| 프로모션 발행 지연으로 인한 매출 손실(추정) | 월 3% | 월 0.3% |
| A/B 테스트 실행 건수 | 월 2회 | 월 30회 |
| SNS·이메일·랜딩 크로스채널 동시 발행률 | 40% | 95% |

---

## 13. 리스크와 대응

| 리스크 | 시그널 | 대응 |
|---|---|---|
| LLM 카피 톤 이탈 | 검수 반려율 15% 초과 | 캠페인 유형별 few-shot 예시 라이브러리 강화 |
| 이미지 생성 품질 편차 | LoRA 신뢰도 저하 | 분기별 재학습, 시드 고정 옵션 |
| cafe24 API 스펙 변경 | 배너 슬롯 업로드 실패 | 어댑터 계층 분리, 스키마 버전 관리 |
| 담당자 프롬프트 미숙 | 브리프 파싱 실패 3회 이상 | 프리셋 템플릿 20종 제공, 대화형 재질문 |
| 상품 실물과 이미지 괴리(고지) | 클레임 증가 | 생성 이미지 하단 "이미지는 연출입니다" 필수 워터마크 |

---

## 14. 90일 즉시 실행

1. **D+7**  브랜드 가이드 JSON화 완료, 과거 시안 100건 라벨링
2. **D+14** Claude 브리프 파서 프로토타입, 스키마 정의 확정
3. **D+30** 배너 3규격 MVP 시연, 마케팅팀 첫 실전 캠페인 투입
4. **D+45** 랜딩페이지 React 컴포넌트 8종 완성
5. **D+60** cafe24 배너 자동 업로드 성공, 검수 큐 정식 오픈
6. **D+75** 요기보 LoRA v1 학습 완료
7. **D+90** 리드타임 4시간 달성, 정식 운영 전환

---

## 부록. 한 줄 요약

> **"디자이너의 창의력을 배너 리사이즈에 쓰지 말자. PromoForge는 반복을 삼키고, 사람은 컨셉만 판단한다."**
> — 자동화의 목적은 디자이너 대체가 아니라, 디자이너를 병목에서 해방시키는 것.
