# 보틀 렌즈 (Bottle Lens) — 개발 인수인계 문서

> 마지막 업데이트: 2026-07-23
> 대상: 이 프로젝트를 이어받아 개발할 개발자
> 목적: 지금까지의 진행 상황·구조·핵심 로직·남은 작업을 한 문서로 공유

---

## 1. 한 줄 요약

술 라벨을 카메라로 찍으면 **주종(12종)을 자동 판별**하고 연식·가격·히스토리·스토리·생산자·테이스팅·페어링 정보를 **세션별 인포그래픽**으로 보여주는 웹 앱. **빌드/백엔드 없는 순수 단일 HTML 파일**이며 Claude 비전 API를 브라우저에서 직접 호출한다.

- 배포 URL: <https://jaythealpha.github.io/Jay/wine-lens/>
- 소스: 저장소 `jaythealpha/Jay` → `wine-lens/` 폴더 (저장소 내 다른 프로젝트와 독립)
- 핵심 파일: **`wine-lens/index.html` 단 하나** (마크업 + CSS + JS 전부 포함, 외부 의존성 0)

---

## 2. 실행 / 배포

### 로컬 실행
```bash
# 저장소 루트에서
python3 -m http.server 8000
# 브라우저에서 http://localhost:8000/wine-lens/ 접속
```
카메라(`getUserMedia`)는 보안 컨텍스트(localhost 또는 HTTPS)에서만 동작한다. `file://`로 열면 JS는 돌지만 카메라는 막힌다.

### 배포
- GitHub Pages. base 브랜치(`claude/expand-korean-market-strategy-dPuXy`)에 머지되면 `.github/workflows/pages.yml`이 자동 배포.
- 배포에 보통 1~2분. Actions 탭에서 `pages.yml` 워크플로 성공 확인.

### 실제 인식 켜기
설정(⚙️) → Anthropic API 키 입력 → 저장. 키가 없으면 **데모 모드**(샘플 12종 순환)로 UI만 확인.

---

## 3. 기술 스택 / 원칙

- **순수 HTML/CSS/JS 단일 파일.** 프레임워크·번들러·npm 없음. 편집 = `index.html` 직접 수정.
- **백엔드 없음.** API 키·스캔 기록은 전부 브라우저 `localStorage`에만 저장.
- **Claude 비전 API 직접 호출** — 브라우저 `fetch`로 `https://api.anthropic.com/v1/messages` 호출. 헤더에 `anthropic-dangerous-direct-browser-access: true` 필요.
- **오프라인 우아한 폴백** — 웹폰트/문장(紋章) 배경은 없으면 시스템 폰트·절차적 렌더로 대체.
- **검증은 Playwright(헤드리스 Chromium)** — 실제 키 없이 `fetch`를 모킹해 파이프라인을 테스트한다(아래 8절).

### localStorage 키
| 키 | 용도 | 기본값 |
|---|---|---|
| `wl_apikey` | Anthropic API 키 | (없음) |
| `wl_model` | 선택 모델 | `claude-sonnet-5` |
| `wl_theme` | 테마 | `cellar`(다크) / `atelier`(라이트) |
| `wl_web` | 웹 검색 보강 ON/OFF | `'1'`(ON) — `!== '0'` 로 판정 |
| `wl_sessions` | 스캔 세션 기록(JSON 배열, 최근 40개) | `[]` |

### 지원 모델 (설정 셀렉트)
- `claude-sonnet-5` (권장·빠름, 기본)
- `claude-opus-4-8` (정밀)
- `claude-haiku-4-5-20251001` (저비용)

---

## 4. 앱 구조 (index.html 내부)

대략적인 섹션 순서:
1. `<head>` — 메타/OG/파비콘, 인라인 CSS 전체(테마 토큰, 컴포넌트 스타일)
2. 마크업 — 화면 4개: `capture`(촬영) / `loading`(분석중) / `result`(결과) / 드로어(설정·히스토리)
3. `<script>` — 아래 핵심 로직

### 화면 전환
`show(screenName)` 로 4개 화면을 전환. 결과·촬영은 rise, 로딩은 settle 모션.

### 주요 함수 지도
| 함수 | 위치(대략) | 역할 |
|---|---|---|
| `store` 객체 | ~879 | localStorage 게터/세터 |
| `setCaptured(dataUrl)` | ~991 | 촬영/업로드 이미지 표시 + **API용 다운사이즈본(max 1280px, JPEG 0.82) 생성** → `capturedForApi` |
| `analyze()` | ~1063 | 분석 진입점. 키 있으면 `callClaude`, 없으면 데모. `found===false` 처리, 세션 저장, 결과 렌더 |
| `SYSTEM_PROMPT` | ~1099 | 시스템 프롬프트(주종 판별·정직성 원칙·웹 검색 지침) |
| `JSON_SCHEMA` | ~1122 | 응답 JSON 스키마(문자열로 프롬프트에 주입) |
| `webSearchTool(model)` | ~1180 | 모델별 web_search 도구 버전 선택 |
| `requestClaude(key,model,base64,useWeb)` | ~1189 | **실제 API 1회 호출** + pause_turn 루프 + 오류 분류 |
| `callClaude(key,model,base64)` | ~1265 | **오케스트레이터** — 웹 검색 시도 → 실패 시 지식 기반 폴백 |
| `parseJson(text)` / `repairJson(src)` | ~1300 | JSON 파싱 + 잘린 JSON 복구 |
| `saveSession/deleteSession` | ~1330 | 세션 CRUD(localStorage) |
| `renderResult(session)` | (하단) | 인포그래픽 렌더(레이더·미터·타임라인 등) |
| `CATS` 레지스트리 | ~1329 | 12주종별 라벨/아이콘/섹션명 |
| `DEMOS` 배열 | ~1936 | 데모 샘플 12종 |

---

## 5. 분석 파이프라인 (가장 중요 — 최근 대폭 개편)

### 흐름
```
analyze()
  └─ callClaude(key, model, base64)              // 오케스트레이터
       ├─ (설정 ON && 세션 검색 정상) requestClaude(..., useWeb=true)
       │     └─ 실패가 "검색이 원인"(WebSearchError)이면 ↓ 폴백
       └─ requestClaude(..., useWeb=false)        // 모델 지식만
             └─ parseJson → 결과 객체
```

### 핵심 설계: 웹 검색은 "실패해도 되는 보강 기능"
- 스캔 시 Anthropic **`web_search` 서버 도구**로 실제 제품을 검색해 빈티지·소매가·평점·수상을 확인(학습 지식에만 의존하지 않음). 서버 측 실행이라 브라우저 fetch로 동작하고 별도 툴 러너·베타 헤더가 필요 없다.
- 모델별 도구 버전: Sonnet 5·Opus 4.8 = `web_search_20260209`(동적 필터링), Haiku 4.5 = `web_search_20250305`(기본). — `webSearchTool()` 참고.
- **검색이 원인으로 실패하면 검색 없이 모델 지식만으로 자동 재분석한다.** 그래서 흔한 술은 검색이 깨져 있어도 항상 인식된다.
  - `WebSearchError` 클래스로 "검색이 원인인 실패"만 구분해 폴백. 그 외 오류(401·429·529 등)는 폴백하지 않고 그대로 사용자에게 안내.
  - 폴백 트리거: ① `400`(계정/모델이 web_search 미지원) ② 검색 지연으로 `pause_turn`만 반복하다 빈 응답 ③ 검색 텍스트가 토큰을 먹어 `max_tokens` 잘림.
  - `400`이 뜨면 모듈 변수 `webSearchBroken = true`로 **세션 동안 검색 비활성화**(매 스캔 2배 호출·반복 실패 방지) + 안내 토스트 1회.
- `max_tokens`는 **12000**. (과거 3000→8000→12000으로 상향된 이력. 검색 질의·중간 텍스트가 출력 토큰을 잡아먹어 최종 JSON이 잘리는 것을 방지.)
- `pause_turn`(서버 검색 루프 일시정지)은 **추가 user 메시지 없이 assistant 응답만 이어붙여 최대 4회 재요청**하는 것이 API 규약. `requestClaude` 안 루프가 이를 처리.

### 정직성 원칙 (프롬프트에 내장)
- 응답 스키마에 `knowledge: rich|moderate|sparse`, `confidence`, `basis` 필드가 있어 "이 제품을 실제로 아는지 vs 일반 추정인지"를 구분해 UI에 신뢰도 미터로 표기한다. 모르는 제품을 지어내지 않도록 강하게 지시.
- **`found` 판정:** 라벨의 글자·브랜드·주종이 조금이라도 판별되면 `found=true`로 두고 최대한 분석(과도한 `found=false` 방지). `found=false`는 술 라벨이 전혀 아니거나 글자를 하나도 못 읽을 때만.

### 이미지 처리
`capturedForApi`는 `image/jpeg` base64(prefix 제거). media_type이 실제 인코딩과 일치해야 400을 피한다. 최대 1280px, 품질 0.82로 다운사이즈.

---

## 6. 응답 JSON 스키마 (요약)

`JSON_SCHEMA`(index.html ~1122)에 전체 정의. 주요 필드:
- 식별: `found, reason, confidence, knowledge, basis, category, name, producer, type, vintage, region, country, alcohol`
- 색/시각: `liquidColor`(액체 색 hex — 결과 배경 글로우에 사용)
- 가격: `priceRange, priceNote, priceTier(1~5)`
- 맛: `tasteProfile`(주종별 축 4개, value 0~100), `tastingNotes`
- 제원: `specs`(2~5개), 맥주 전용 `ibu`, `srm`
- 음용 적기: `drinkFrom, drinkPeak, drinkUntil` (숙성형 와인 위주, 없으면 null)
- 서사: `history`(3~5개 연대), `story`, `winery`
- 페어링: `foodPairing[{emoji,food,why}], pairingTip, avoidPairing`
- 부가: `ratings[{source,score}], similar[], trivia, servingTemp, servingNote, aging, tips[]`

> `category`는 12종 중 하나: `wine|sake|whisky|traditional|beer|brandy|baijiu|tequila|rum|gin|soju|spirits`. `CATS` 레지스트리가 각 카테고리의 아이콘·섹션명(와이너리/증류소/양조장 등)을 매핑한다.

---

## 7. 진행 이력 (머지된 PR)

| PR | 내용 |
|---|---|
| #24 | 맛 프로필 "플레이버 시그니처" 레이더(주종별 축 자동 적응) |
| #25 | **와인 렌즈 → 보틀 렌즈 리브랜딩** + 결과 히어로 절차적 문장(紋章) 배경 |
| #26 | 분석 결과 보완(페어링 이유·평점·유사주·상식·히스토리 확장) + 햅틱 |
| #27 | 브랜드 자산(로고·파비콘·OG) 자체 제작(SVG→PNG 렌더) |
| #28 | **"결과 없음" 버그 수정** — max_tokens 3000→8000, `repairJson` 폴백 |
| #29 | 에디토리얼 럭셔리 디자인(명조 + Cormorant Garamond, 종이 그레인) |
| #30 | 사진 업로드 경로 보강(갤러리·드래그앤드롭·붙여넣기) |
| #31 | UX/UI 4대 개선 — 모션·카메라 가이드·드로어 제스처·접근성(포커스 트랩·스킵링크·aria) |
| #32 | **웹 검색 정보 보강** — web_search 서버 도구 도입(기본 ON) |
| #33 | **분석 안정성 강화** — 웹 검색 실패 시 지식 기반 자동 폴백(self-healing) |

현재 배포 상태 = **#33까지 반영**. 작업 브랜치: `claude/wine-label-camera-app-7gargt` → base `claude/expand-korean-market-strategy-dPuXy`.

---

## 8. 개발 / 검증 방법

실제 API 키가 없어도 **Playwright로 `window.fetch`를 모킹**해 파이프라인을 테스트할 수 있다. (자동 폴백 검증에 실제로 사용한 방식.)

```js
// 페이지 로드 후, api.anthropic.com 호출을 가로채 캔드 응답 반환
window.fetch = async (url, opts) => {
  const body = JSON.parse(opts.body);
  const hasTools = !!body.tools;           // 웹 검색 사용 여부
  // 예: 웹 검색이면 400, 아니면 정상 JSON 반환 → 폴백 동작 확인
  if (hasTools) return new Response(JSON.stringify({error:{message:'...'}}), {status:400});
  return new Response(JSON.stringify({ stop_reason:'end_turn',
    content:[{type:'text', text: JSON.stringify({found:true, category:'wine', name:'...'})}]}), {status:200});
};
const result = await callClaude('sk-test', 'claude-sonnet-5', 'AAAA');
```

검증한 폴백 시나리오(전부 결과 반환 성공):
| 시나리오 | 호출 순서 | 기대 |
|---|---|---|
| 웹 검색 400(미지원) | `WEB → NOWEB` | 결과 + 토스트 1회 + `webSearchBroken=true` |
| 웹 검색 `pause_turn` 지연 | `WEB…(4회)→ NOWEB` | 결과 반환 |
| 정상 | `WEB` | 결과 반환 |

Playwright 실행 시 브라우저는 `executablePath: '/opt/pw-browsers/chromium'`(이 환경) 또는 시스템 설치본을 사용. 헤드리스 로드 시 `ERR_CONNECTION_RESET`은 오프라인 웹폰트 폴백이라 정상(무시).

---

## 9. 남은 작업 / 알려진 이슈

### (A) 주종별 포토리얼리스틱 병 이미지 통합 — **미완, PC 작업 필요**
- 결과 화면의 문장(紋章) 배경은 현재 **절차적 SVG 렌더**(사진 아님). 더 실사적인 병 이미지를 얹는 방향으로 논의됨.
- Higgsfield MCP로 **와인 병 이미지 1장**은 생성 완료(포토리얼리스틱, 사용자 승인). 나머지 주종(위스키/사케/맥주/소주 등)은 미생성.
- **블로커:** 생성 이미지가 이 원격 세션의 저장소로 들어오지 못함 —
  - Higgsfield CDN(`d8j0ntlcm91z4.cloudfront.net`)이 에이전트 프록시 정책상 차단(403).
  - 채팅 첨부 이미지는 뷰 전용이라 디스크 경로로 접근 불가.
  - 모바일 GitHub 웹은 업로드 비활성("Uploads are disabled").
- **다음 단계(사용자 예정):** PC에서 PNG를 `wine-lens/assets/`에 직접 업로드/커밋 → 결과 히어로 렌더 코드에서 카테고리별 이미지 매핑. 파일명·매핑 규약을 정해 두면 통합이 쉬움.

### (B) 관찰 포인트
- 웹 검색이 계정에서 지원되는지에 따라 첫 스캔이 2배 호출(웹→폴백)될 수 있음. `webSearchBroken` 세션 캐시로 이후 스캔은 1회. 계정에 web_search가 있으면 폴백 자체가 안 일어남.
- 특정 술이 여전히 부실하게 나오면: 그 라벨 사진 + `knowledge`/`basis` 값을 함께 확인. sparse가 잦으면 프롬프트/스키마 튜닝 대상.

---

## 10. 협업 규약

- **작업 브랜치:** `claude/wine-label-camera-app-7gargt`. base는 `claude/expand-korean-market-strategy-dPuXy`.
- base가 squash-merge로 앞서가 diff가 갈리면: `git fetch` → `git reset --soft origin/<base>` → 순수 변경분만 재커밋 → `--force-with-lease` 푸시. (이 저장소에서 반복 사용한 패턴.)
- **보안/프라이버시:** API 키는 브라우저 localStorage에만. 저장소에 시크릿 커밋 금지. 공유 기기 사용 경고를 UI에 노출.
- 이 앱은 `wine-lens/` 폴더로 **자기완결**. 저장소의 다른 프로젝트와 코드/자산을 섞지 말 것.

---

## 11. 빠른 시작 (새 개발자 체크리스트)

1. `python3 -m http.server 8000` → `http://localhost:8000/wine-lens/` 접속, 데모 모드로 UI 파악
2. 본인 Anthropic 키를 설정에 넣고 실제 라벨(유명 술: 발렌타인·참이슬·카스 등)로 스캔
3. `index.html`에서 5절(분석 파이프라인) 함수부터 읽기 — `analyze → callClaude → requestClaude`
4. 변경 후 8절 방식으로 Playwright 모킹 검증 → 커밋 → PR → base 머지 → Pages 배포 확인
