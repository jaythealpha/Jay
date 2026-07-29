# Price Lens — Developer Handoff

옷 라벨/가격표를 촬영하면 상품을 식별하고, 웹 검색으로 현재 인터넷 최저가(오름차순)와 최근 1년 가격 추이를 보여주는 독립 웹 앱. `price-lens/` 폴더만으로 완결되는 단일 HTML 파일 앱이며, 저장소의 다른 프로젝트(직장인 생존기 게임, wine-lens)와는 무관하다.

작성 시점: 2026-07-15. 아래 내용은 지금까지의 개발 세션에서 실제로 구현·수정·검증한 것만 기술한다.

## 0. 한눈에 보기

| 항목 | 상태 |
|---|---|
| GitHub Pages | 🟢 자동 배포 중 — `https://jaythealpha.github.io/Jay/price-lens/` |
| Vercel | 🟡 수동 배포만 됨 — `https://price-lens-blond.vercel.app` (Git 연동 안 됨, 자동 재배포 안 됨) |
| 자동화 테스트 | ⚪ 없음 — 세션마다 Playwright 헤드리스 스크립트로 수동 검증만 함 |
| API 키 저장 방식 | 브라우저 localStorage, 서버 없음 (보안 트레이드오프 있음 — §8 참고) |

## 1. 아키텍처

- **완전한 클라이언트 사이드 단일 파일**: `price-lens/index.html` 하나에 마크업+CSS+JS 전부 포함 (약 1,500줄). 빌드 스텝 없음, 외부 라이브러리 의존성 없음.
- **백엔드 없음**: Anthropic API를 브라우저에서 직접 호출한다 (`anthropic-dangerous-direct-browser-access: true` 헤더 사용). API 키는 사용자가 앱 내 설정(⚙️)에서 입력해 `localStorage`(`pl_apikey`)에만 저장.
- **세션 기록**: 스캔 결과를 `localStorage`(`pl_sessions`, 최근 30개)에 저장. 사이드 드로어에서 재열람/삭제.
- **데모 모드**: API 키가 없으면 `DEMO_DATA` 고정 객체로 전체 UI를 체험 가능.

## 2. 핵심 데이터 흐름

```
[캡처]                     [식별 근거 확보]                [AI 호출]                    [렌더]
카메라 / 갤러리 /     →     클라이언트에서 실제      →     Claude Vision           →     JSON 파싱 →
드래그드롭 / 붙여넣기        바코드 디코딩 시도             + web_search 도구              가격 목록 정렬 +
(setCaptured)              (BarcodeDetector API)          (callClaude)                  1년 추이 차트 +
                           → 성공 시 그 숫자만               스키마 강제 출력               바로 검색 링크
                             프롬프트에 "진짜 값"으로
                             주입, 실패해도 계속 진행
```

핵심 함수 위치 (`index.html` 기준):

| 함수/상수 | 역할 |
|---|---|
| `setCaptured()` | 캡처된 이미지 저장 + API용 다운사이즈(최대 1568px) + `detectBarcode()` 트리거 |
| `detectBarcode()` | 브라우저 내장 `BarcodeDetector`로 실제 바코드 디코딩 (§7 참고) |
| `analyze()` / `analyzeQuery()` | 사진 기반 / 텍스트 기반 분석 진입점 → `runAnalysis()` |
| `callClaude()` | Anthropic API 호출부, 이미지+바코드값 또는 검색어를 프롬프트로 구성 |
| `SYSTEM_PROMPT` / `JSON_SCHEMA` | 식별 규칙(반할루시네이션 포함) + 강제 출력 스키마 |
| `renderResult()` | 응답 JSON → 가격표/차트/링크 등 DOM 렌더 |
| `buildChart()` | 1년 가격 추이 SVG 차트 생성 (호버 포함) |

## 3. AI 응답 JSON 스키마

```jsonc
{
  "found": true,
  "reason": "",                          // found=false일 때 사유
  "confidence": "high|medium|low",       // 브랜드/상품명을 텍스트로 못 읽었으면 low
  "identificationBasis": "라벨 텍스트로 식별 | 디코딩된 바코드 번호로 검색 | 검색어 직접 입력",
  "brand": "",
  "productName": "",
  "modelCode": "",
  "category": "",
  "color": "",
  "size": "",
  "tagPrice": 350000,                    // 라벨 정가, 없으면 null
  "searchQuery": "",                     // 바로 검색 링크에 쓰이는 대표 검색어
  "summary": "",
  "listings": [                          // 웹 검색으로 실제 확인된 가격만 (지어내지 않음)
    { "site": "", "title": "", "price": 89000,
      "shipping": "", "condition": "새상품|중고|리퍼|불명",
      "url": "", "note": "" }
  ],
  "priceInsight": "",
  "history": {
    "points": [ { "month": "2025-08", "price": 320000 } ],  // 12~13개월, AI 추정치
    "low": { "month": "", "price": 0 },
    "high": { "month": "", "price": 0 },
    "trend": "하락|상승|보합",
    "note": ""                           // 추정 근거 명시 필수
  },
  "sources": [ { "title": "", "url": "" } ]
}
```

`renderResult()`가 이 필드를 그대로 소비하므로, 스키마를 바꾸면 렌더 함수도 함께 고쳐야 한다.

## 4. 구현된 기능

- 카메라 실시간 촬영(후면 우선, 전환 가능) + 촬영 가이드 프레임
- 사진 업로드 3경로: 갤러리 선택 / 드래그&드롭 / 클립보드 붙여넣기(Ctrl+V)
- 클라이언트 바코드 실디코딩(`BarcodeDetector`) → 프롬프트에 신뢰값으로 주입
- Claude Vision + `web_search` 도구로 상품 식별 + 실시간 가격 조사
- 가격 목록 최저가 오름차순, 새상품/중고·리퍼 상태 필터 칩
- 최근 1년 최저가 추이 SVG 라인 차트 (호버 크로스헤어, 최저/최고/현재 직접 라벨, 표 보기 폴백)
- 라벨 정가 vs 최저가 vs 할인율 KPI
- 네이버쇼핑/다나와/쿠팡/구글쇼핑/무신사/KREAM/번개장터 바로 검색 링크 + 검색어 수정 후 재조회
- 사진 없이 상품명/품번 텍스트만으로 검색
- 식별 근거·확신도 표시, 확신도 낮을 때 경고 배너
- 스캔 기록 드로어, 설정 모달(API 키·모델 선택), 공유(Web Share API/클립보드), 데모 모드

## 5. 버그 수정 이력 (원인 포함 — 회귀 주의)

### 🐛 바코드 오인식 → 전혀 다른 상품 도출 ([PR #22](https://github.com/jaythealpha/Jay/pull/22))
**원인**: 바코드 막대무늬는 OCR 텍스트와 달리 시각 모델이 "판독"할 수 있는 대상이 아님. 브랜드 텍스트가 없는 라벨(바코드 스티커만 있는 가격표)에서 모델이 막대무늬를 숫자로 추측(할루시네이션)해 완전히 다른 상품으로 이어짐.
**수정**: (1) `BarcodeDetector` API로 클라이언트에서 실제 디코딩 후 그 값만 신뢰 가능한 값으로 프롬프트에 명시. (2) 시스템 프롬프트에 "바코드 막대무늬 판독 금지", "브랜드 안 보이면 지어내지 말고 confidence=low" 규칙 추가. (3) `identificationBasis` 필드로 식별 근거를 결과 화면에 공개, 낮은 확신도일 때 경고 배너 표시.
**⚠️ 회귀 주의**: `SYSTEM_PROMPT`에서 바코드 관련 반할루시네이션 문구를 제거하거나, `detectBarcode()` 호출을 빼면 이 버그가 재발한다.

### 🐛 갤러리 버튼을 눌러도 카메라가 열림 ([PR #30](https://github.com/jaythealpha/Jay/pull/30))
**원인**: `<input type="file" capture="environment">`의 `capture` 속성이 iOS Safari 등에서 파일 선택 대신 카메라 앱을 강제로 먼저 엶.
**수정**: `capture` 속성 제거. 대신 PC 테스트 편의를 위해 드래그&드롭·클립보드 붙여넣기 추가.
**⚠️ 회귀 주의**: `#fileInput`에 `capture` 속성을 다시 추가하지 말 것.

## 6. 배포 현황

### GitHub Pages — 자동
- 워크플로: `.github/workflows/pages.yml` (저장소 기본 브랜치 push 시 전체 저장소를 `gh-pages`로 발행)
- 앱 경로: `/price-lens/` 서브패스
- 상태: 정상 작동 확인됨 (매 머지마다 재배포 성공)

### Vercel — 수동만 됨, Git 연동 안 됨
- 사용자가 로컬(맥미니)에서 `vercel --prod`로 직접 배포함. **Git 저장소와 연결되지 않아 이후 커밋이 자동 반영되지 않는다.**
- 프로젝트: `price-lens` (팀 `okyoutobeyou-9553's projects`, team id `team_NbYpn27yFDE3HyVtUzV0Lizq`)
- 배포 주소: `https://price-lens-blond.vercel.app` (고정 별칭)
- **재배포하려면**: 로컬에서 `git pull && cd price-lens && vercel --prod`
- **자동화하려면**: Vercel 대시보드 → 해당 프로젝트 → Settings → Git → Connect Git Repository (`jaythealpha/Jay`) → Root Directory를 `price-lens`로 지정. (아직 미완료)
- `.github/workflows/vercel-price-lens.yml` — GitHub Actions로 배포하는 대안 워크플로도 있으나, `VERCEL_TOKEN`/`VERCEL_ORG_ID`/`VERCEL_PROJECT_ID` 시크릿이 등록되지 않아 현재는 매번 스킵됨.
- **중요 — AI 에이전트가 직접 배포 시도 금지**: 연결된 Vercel MCP 커넥터로 실제 배포를 3회 시도했으나(프로덕션/프리뷰/신규 프로젝트 생성) 매번 `403 forbidden`으로 거부됨 — 해당 계정이 이 팀에서 배포·프로젝트 생성 권한이 없는 역할로 연결되어 있기 때문. 네트워크 문제가 아니라 권한 문제이므로, 재시도해도 해결되지 않는다. 사람이 CLI 또는 대시보드로 직접 해야 한다.

## 7. 알려진 제약 · 리스크

- **API 키 노출 리스크**: 브라우저에서 Anthropic API를 직접 호출하므로(`anthropic-dangerous-direct-browser-access`) 키가 클라이언트에 그대로 남는다. 백엔드 프록시가 없다는 전제 하의 의도된 설계지만, 공유 기기·XSS에 취약하다는 점을 인지하고 있어야 한다.
- **1년 가격 추이는 실측 데이터가 아니라 AI 추정치**다. 국내 쇼핑몰의 과거 가격 원본을 얻을 공개 API가 없어, 검색에서 발견한 단서 + 카테고리 일반 할인 패턴으로 추정한다. UI의 "추정치" 문구를 임의로 제거하지 말 것.
- **웹 검색 기반 식별의 한계**: 브랜드 로고가 없거나 희귀한 상품은 여전히 오식별 가능성이 있다 (바코드 관련 사례는 수정됐지만, 근본적으로 검색 결과 품질에 의존).
- **`BarcodeDetector` 브라우저 지원 편차**: 구형 Safari 등 미지원 브라우저에서는 조용히 건너뛰고 텍스트 인식으로만 진행한다 (정상 동작이지만 인식률은 떨어짐). 디코딩된 바코드 번호를 실제 상품 DB(UPC/EAN 데이터베이스)와 매칭하는 기능은 없음 — 검색어 힌트로만 사용.
- **자동화 테스트 없음**: 지금까지의 검증은 세션마다 Playwright(`playwright-core`) + 로컬 헤드리스 Chromium 스크립트를 즉석에서 작성해 실행한 것이며, 리포지토리에 정식 테스트로 편입되어 있지 않다 (§9 참고).
- **모니터링/에러 로깅 없음**: 실패는 토스트 메시지로만 사용자에게 노출되고, 어디에도 기록되지 않는다.

## 8. 다음 개발 후보 (제안)

우선순위 제안이며 확정 사항은 아니다:

1. **Vercel Git 연동 마무리** — 자동 배포화 (§6 참고, 대시보드 작업만 남음)
2. **API 키 노출 완화 검토** — 서버리스 프록시(Vercel Function 등)로 브라우저에 키를 직접 두지 않는 구조 검토
3. **정식 테스트 스위트화** — 임시로 짜온 Playwright 스크립트 패턴(§9)을 리포에 편입해 회귀 방지
4. **가격 히스토리 신뢰도 개선** — 실제 시세 데이터 소스 연동 가능성 조사, 불가하면 추정 로직 고도화 및 근거 문구 강화
5. **실사용 회귀 QA** — 바코드 없음/흐림/외국어 라벨 등 다양한 케이스로 실제 API 키를 넣고 재검증

## 9. 로컬 개발 · 검증 방법

```bash
# 저장소 루트에서
python3 -m http.server 8000
# http://localhost:8000/price-lens/ 접속 (API 키 없이도 데모 모드로 확인 가능)
```

카메라(`getUserMedia`)는 보안 컨텍스트가 필요해 `file://`로 열면 동작하지 않는다 — 반드시 로컬 서버나 HTTPS에서 확인할 것.

이번 개발 세션들에서 쓴 헤드리스 검증 패턴 (정식 테스트는 아니고 즉석 스크립트):

```js
// playwright-core + 로컬 Chromium, 카메라 없는 환경이라 파일 업로드 경로로 대체 테스트
import { chromium } from 'playwright-core';
const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome' });
const page = await b.newPage({ viewport: { width: 420, height: 900 } });
page.on('pageerror', e => console.log('pageerror:', e.message));
await page.goto('file:///.../price-lens/index.html');
await page.locator('#fileInput').setInputFiles('/path/to/real-label-photo.jpeg');
await page.waitForTimeout(300);
await page.screenshot({ path: 'out.png', fullPage: true });
```

## 10. 관련 PR

| PR | 내용 | 커밋 |
|---|---|---|
| [#12](https://github.com/jaythealpha/Jay/pull/12) | 최초 앱 구현 + Vercel 배포 구성 | `22875d9` |
| [#13](https://github.com/jaythealpha/Jay/pull/13) | 텍스트 검색 + 상태 필터 + 재조회 | `c926eb6` |
| [#22](https://github.com/jaythealpha/Jay/pull/22) | 바코드 오인식 수정 | `6ca3766` |
| [#30](https://github.com/jaythealpha/Jay/pull/30) | 사진 업로드 경로 보강 | `a5a0cc7` |

## 11. 파일 구조

```
price-lens/
├── index.html    # 앱 전체 (마크업+스타일+로직, 외부 의존성 없음)
├── README.md     # 사용자 대상 문서 (설치/사용법)
├── HANDOFF.md     # 이 문서 — 개발자 인수인계 노트
└── vercel.json    # Vercel 정적 배포 설정 + 보안 헤더

.github/workflows/
├── pages.yml               # GitHub Pages 자동 배포 (저장소 전체 대상)
└── vercel-price-lens.yml   # Vercel 배포용 대안 워크플로 (시크릿 미등록 상태로 현재 스킵됨)
```

저장소 기본 브랜치는 `claude/expand-korean-market-strategy-dPuXy`이며, 다른 독립 프로젝트(wine-lens, 직장인 생존기 게임)와 커밋을 공유하므로 PR 전 반드시 최신 기본 브랜치 위로 rebase할 것.
