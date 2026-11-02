# AR 이벤트 — 컨셉 · 구조 · 로드맵 (에이전트 인계용)

> 대상: 이 저장소를 이어서 작업하는 개발자 / 코딩 에이전트(Codex, Claude Code 등).
> 이 문서만 읽고 같은 방향·같은 규칙으로 다음 단계를 구현할 수 있도록 정리했다.
> 최종 정리: 2026-11-02 · 빌드 `2026.11.02-a` · 작업 규칙은 루트 `AGENTS.md` 참고.
> 근거 자료: `docs/research/ar-qr-tech-research-2026-11.md` (기술 조사 보고서).

---

## 1. 컨셉

**"사진 한 장 → 1분 안에 AR QR → 포스터에 붙이면 끝."**

- 대상: 앱 설치·코딩·3D 지식이 없는 **한국 소상공인·마케터** (카페, 매장, 행사, 브랜드 팝업).
- 고객 경험: 포스터의 QR을 휴대폰 기본 카메라로 찍는다 → **앱 설치 없이 웹페이지**가 열린다 → 카메라로 포스터를 비추면 효과/캐릭터/3D가 포스터 위에 나타난다 → 쿠폰·추첨·사진 등 **보상**을 받는다.
- 시장 포지션 (조사 결과): Meta Spark(2025-01)·Adobe Aero(2025-12)·8th Wall(호스팅 2027-02 종료)이 철수했고, 남은 해외 서비스는 월 $25–90에 조회 수 상한이 있다. 국내에는 사진만으로 AR QR을 만드는 한국어 셀프서비스가 없다(외주 건당 ₩55만+). → **조회 무제한 · 한국어 · 사진 중심 · 저렴함**이 차별점.

### 설계 원칙 (모든 단계에서 지킬 것)
1. **보상은 AR 성공과 분리한다.** 카메라/AR이 안 되는 폰에서도 쿠폰·추첨·사진 혜택을 받을 수 있어야 한다. AR은 "재미", 보상은 "약속".
2. **모든 실패에는 다음 길이 있다.** 카메라 거부·멈춤·인앱 브라우저·AR 미지원 → 항상 "기본 브라우저로 열기 / 카메라 없이 보기 / 다시 시도" 중 하나 이상을 보여준다.
3. **QR이 기준점이다.** 별도 마커·앱 없이, 포스터의 QR 자체를 추적해 그 위에 콘텐츠를 얹는다. (이미지 타깃 추적은 2단계에서 *보조*로 추가)
4. **무거운 것은 지연 로딩.** 3D 뷰어(model-viewer ~0.9MB)·얼굴 인식 등은 해당 유형일 때만 불러온다.
5. **개인정보 최소화.** 고객 카메라 영상·사진은 기기 밖으로 나가지 않는다. 사장님이 올린 이미지만 서버(Blob)에 공개 저장하며, 업로드 전 동의를 받고 원본은 배경 제거 후 삭제한다.
6. **4개 언어(ko/en/ja/zh) 동시 지원.** UI 문자열을 하드코딩하지 않는다.
7. **서버 없이도 기본은 동작.** Blob/KV/AI가 없으면 해당 기능만 비활성화하고 이유를 화면에 표시한다(조용히 실패 금지).

---

## 2. 현재 구현 상태

| 영역 | 상태 | 위치 |
|---|---|---|
| 이벤트 유형 6종: 포토 필터 · 쿠폰 공개 · 행운 뽑기 · 축하 효과 · 움직이는 포스터 · **이미지 AR** | ✅ | `event.html`, 빌더 `qr-studio.html` (EVB 모듈) |
| QR 코너 추적(jsQR, 원본 해상도 + 중앙 크롭 교대) → 2D 장면 앵커링, QR 사라지면 페이드아웃 | ✅ | `event.html` `scanQR()`, `pose()`, `loopScan()` |
| 이미지 AR: 업로드 → 배경 제거 → 4가지 움직임(솟아오르기·둥실·회전·입체 카드) | ✅ | `sceneImage()` |
| 이미지 → 3D(GLB) → QR 위 회전 + "내 공간에 놓기"(WebXR / Scene Viewer / Quick Look) | ✅ | `MV`, `mvLoad()`, `__placeAR()`; `vendor/model-viewer.min.js` |
| 짧은 링크 `/event.html?e=<id>` (설정을 Blob에 저장) | ✅ | `api/ar-asset.js` `op:"save"` / `?e=` |
| **1단계(진입 안정화)** — 인앱 브라우저 탈출, 카메라 타임아웃·검은 화면 감지, 실패 대체 경로, 보상 분리, 퍼널 계측, 업로드 동의, 원본 자동 삭제, 참여 통계 패널 | ✅ 2026-11-02 | §5, §6 |
| 포스터 편집기에서 만든 포스터의 QR 위치(`pg`)로 포스터 전체 영역 계산 | ✅ | `posterRect()` |
| 2단계 이후 | ⏳ | §8 로드맵 |

**외부 의존 상태 (2026-11-02)**
- Vercel Blob: ✅ 연결됨 (`BLOB_READ_WRITE_TOKEN`, 스토어 `inkyqrmaker`, icn1, public)
- Replicate: ✅ (`REPLICATE_API_TOKEN`) — 배경 제거 `851-labs/background-remover`, 3D `firtoz/trellis` (TRELLIS v1, 콜드스타트 시 최대 ~10분)
- Upstash Redis(KV): ❌ 미연결 → 퍼널 숫자는 저장되지 않고 함수 로그에만 남는다. 연결하면 코드 수정 없이 통계·3D 일일 제한이 켜진다.

---

## 3. 파일 지도

```
qr-studio.html      메인 단일 파일 앱(~9.7k줄). 빌더 UI·i18n·갤러리·포스터 편집기 전부 포함.
index.html          qr-studio.html의 복사본. 수정 후 항상 `cp qr-studio.html index.html`.
event.html          고객용 AR 런타임(단일 파일). QR 추적·장면·결과 시트·보상.
api/ar-asset.js     이미지 AR 서버 함수(Blob 업로드·배경 제거·3D·짧은 링크·퍼널 이벤트·통계·삭제).
api/art-qr.js       AI 아트 QR(Replicate) — AR과 무관.
vendor/             jsQR.js, qrcode.js, model-viewer.min.js(3.5.0, 지연 로딩), face-api, mindar-image.prod.js(미사용·2단계 후보)
assets/poster/      포스터 예시 이미지(+ t/ 썸네일)
tools/tests/        헤드리스 브라우저 테스트(§9)
docs/research/      기술 조사 보고서
```

### 빌더(qr-studio.html) 안의 AR 관련 코드
- 마크업: `#view-ar` 섹션, 유형 버튼 `#evTypes [data-k]`, 유형별 그룹 `details[data-ev="…"]`(공백 구분 다중 유형).
- 로직: `var EVB=(function(){ … })()` 모듈.
  - `cfg()` → 현재 폼 값을 이벤트 설정 객체로, `link(c)` → 고객 링크(이미지 AR은 짧은 링크 저장 후 교체), `update()` → QR·미리보기 iframe 갱신.
  - 이미지 AR 상태 `IM={local,orig,cut,gl,srv,short,del}`, 서버 호출 `api()`, 폴링 `poll()`.
  - 통계 `evIdOf(u)`, `loadStats()`.
- 미리보기: `event.html?demo=1&lang=…#c=…` iframe. demo 모드는 샘플 포스터 이미지 위에 가짜 QR을 고정해 장면을 반복 재생하고, 비콘을 보내지 않는다.
- 공용 헬퍼: `evLink(cfg)`(빈 값 제거 후 base64url → `MAP_SITE+"/event.html#c=…"`), `t(key)`, `I18N`.

---

## 4. 이벤트 설정 키 (`event.html`의 `C`)

링크 `#c=` 의 base64url(JSON) 또는 `?e=<id>`로 Blob에서 받은 JSON. **키는 짧게 유지**(QR 밀도).

| 키 | 의미 | 키 | 의미 |
|---|---|---|---|
| `k` | 유형: photo · coupon · lucky · confetti · scene · image (info: 레거시 텍스트 페이지) | `t` `s` `b` | 제목 · 부제 · 브랜드 |
| `c` | 강조색 hex(# 없이) | `l` `lt` | 연결 링크 · 버튼 문구 |
| `h` | 해시태그(포토) | `lang` | 강제 언어 |
| `f` `e` `es` `ss` `fs` `ft` `d` | 포토: 프레임 · 스티커 세트 · 사용자 스티커 · 스티커 크기 · 얼굴 스티커 · 글꼴 · 날짜 표시 | `rm` | 포토 보상 조건: none · capture · share |
| `rx` `rd` `ru` | 보상 이름 · 코드 · 유효기간 | `pn` | 직원 PIN 해시 FNV-1a(`pin+"|"+t`) |
| `pr` | 행운 뽑기 등급 `[[이름,%],…]` (레거시 `p`,`wx`) | `lx` | 꽝 문구 |
| `sd` `ed` | 이벤트 기간 YYYY-MM-DD | `ct` `ic` `pk` | 쿠폰 카드 테마 · 아이콘 · 파티클 |
| `sc` `si` `ms` | 움직이는 포스터: 연출 · 강도(1–3) · 캐릭터 이모지 | `pg` | 포스터 기하 `[qrCx/W, qrCy/H, qrSymbolW/W, H/W]` |
| `im` | 이미지 URL(Blob) | `ia` | 움직임: rise · float · spin · card |
| `iz` | 크기 배율 0.6–1.8 | `gl` | GLB 모델 URL(있으면 3D 오버레이 + 내 공간에 놓기) |
| `it` `i` | (info 전용) 카드 제목 · `|` 구분 내용 | | |

새 키를 추가할 때: `event.html`에서 읽고, 빌더 `cfg()`에서 쓰고, 이 표를 갱신한다. 기본값은 키를 생략해서 표현한다.

---

## 5. 서버 API — `api/ar-asset.js`

| 호출 | 결과 | 비고 |
|---|---|---|
| `GET ?status=1` | `{blob, ai, kv}` | 빌더가 기능 활성화 판단 |
| `POST {op:"upload", data:"data:image/...;base64,…"}` | `{url}` | ≤4MB, Blob `ar/i-<rand>.(png\|jpg\|webp)` |
| `POST {op:"cutout", url}` → `GET ?id=&kind=cutout` | `{id}` → `{status, url}` | 결과는 Blob `ar/c-*.png`로 복사(Replicate 결과는 1시간 뒤 삭제되므로 즉시 복사) |
| `POST {op:"model3d", url}` → `GET ?id=&kind=model3d` | `{id}` → `{status, url}` | Blob `ar/m-*.glb`. KV 있으면 IP당 하루 `AR_3D_DAILY_LIMIT`(기본 5) |
| `POST {op:"save", cfg}` / `GET ?e=<id>` | `{id}` / cfg | Blob `ev/<id>.json` |
| `POST {op:"delete", url}` | `{ok}` | `ar/i-*` 원본만 허용 |
| `POST {op:"ev", id, n, k, ia, os}` | 204 | 퍼널 비콘. `sendBeacon`(text/plain). KV 있으면 `evs:<id>:<n>`, `evs:<id>:<n>:<KST날짜>`(40일) |
| `GET ?stats=<id>` | `{kv, total, days}` | 최근 14일 |

- URL 검증: cutout/model3d/delete는 **우리 Blob 호스트(`*.public.blob.vercel-storage.com`)** URL만 받는다(오픈 프록시 방지).
- 환경변수: `BLOB_READ_WRITE_TOKEN`, `REPLICATE_API_TOKEN`, (선택) `KV_REST_API_URL`/`KV_REST_API_TOKEN` 또는 `UPSTASH_REDIS_REST_*`, `AR_CUTOUT_MODEL`, `AR_CUTOUT_FIELD`, `AR_3D_MODEL`, `AR_3D_INPUT`(JSON 템플릿, `{url}` 치환), `AR_3D_DAILY_LIMIT`.
- Blob REST(SDK 없이 fetch): `PUT https://blob.vercel-storage.com/?pathname=…` 헤더 `authorization: Bearer`, `x-api-version: 9`, `x-content-type`, `x-add-random-suffix`; 목록 `GET /?prefix=`; 삭제 `POST /delete {urls:[…]}`.
- `package.json`이 루트에 없다(정적 사이트 + 의존성 없는 함수). 루트에 추가하지 말 것 — 빌드 방식이 바뀐다.

---

## 6. 1단계(진입 안정화) 동작 명세 — 구현 완료

### 6.1 인앱 브라우저
- 감지(UA): `kakao`(KAKAOTALK) · `naver` · `instagram` · `facebook`(FBAN/FBAV/FB_IAB) · `line` · `band` · `daum`.
- 카카오톡: 첫 방문 시 1회 자동으로 `kakaotalk://web/openExternal?url=<현재URL>` (세션당 1회, `sessionStorage.esc_tried`). 비공식 스킴이므로 실패해도 페이지는 그대로 동작해야 한다.
- 그 외 Android: 배너 버튼 → `intent://<host/path>#Intent;scheme=https;package=com.android.chrome;S.browser_fallback_url=<URL>;end`.
- 그 외 iOS: 자동 이동 불가 → "⋯ 메뉴 → Safari로 열기" 안내 + 링크 복사 버튼.
- 배너는 랜딩 하단 `#inapp`. 사용자는 무시하고 그대로 시도할 수 있다.

### 6.2 카메라
- `getUserMedia` 12초 타임아웃(카카오톡 Android에서 오류 없이 멈추는 사례), `play()` 5초, 이후 4초 내 `videoWidth`가 0이면 "프레임 없음"으로 실패 처리. 늦게 도착한 스트림은 즉시 정지.
- 실패 시 `camFailed()` → 원인 문구 + `#fb` 버튼: [기본 브라우저로 열기(인앱일 때)] · [카메라 없이 혜택 받기(포토+보상) / 카메라 없이 보기] · [다시 시도].

### 6.3 보상 분리
- 포토 필터에 보상이 있으면(`rm` ≠ none) 카메라 실패 시 `__rewardNoCam()`으로 보상 시트를 바로 준다. 카메라 없이 보기 경로의 `sheetHTML()`도 포토 보상을 반환.
- 쿠폰·행운 뽑기는 기존 "카메라 없이 보기"로 동일한 결과·PIN 사용 처리를 받는다. 행운 뽑기 결과는 기기당 1회(`localStorage`).

### 6.4 퍼널 이벤트 (`track(name)`, 페이지 로드당 이름별 1회)
`land` 방문 → `cam_start` → `cam_ok` → `found`(QR 인식=AR 시작) → `sheet`(결과·혜택 표시) → `redeem`(직원 PIN 사용 처리)
보조: `inapp`, `escape`, `cam_fail`, `nocam`, `shot`, `share`, `save`, `place`(내 공간에 놓기), `link`(외부 링크 클릭).
- 이벤트 ID: 짧은 링크면 `<id>`, 아니면 `#c=` 페이로드의 FNV-1a 32bit 16진수 8자리(앞 0 채움). 빌더 `evIdOf()`와 반드시 동일하게 계산.
- demo 모드·file:// 에서는 보내지 않는다. 이름은 서버 화이트리스트(`EV_NAMES`)와 일치해야 집계된다.
- 빌더 "📊 참여 통계": 방문 대비 각 단계 %와 보조 지표. KV 없으면 연결 안내.

### 6.5 업로드 동의 · 원본 삭제
- 이미지 AR 그룹의 동의 체크(`#evConsent`, 기본 해제) 전에는 업로드하지 않고 로컬 미리보기만.
- 배경 제거 성공 → 원본(`ar/i-*`) 즉시 삭제. 사용자가 배경 제거를 끄면 메모리의 원본을 다시 업로드, 다시 켜면 재삭제.
- 사이트 개인정보처리방침 3항에 "이미지 AR 공개 저장" 문단(4개 언어) 있음. 얼굴 사진 업로드 금지 안내.

---

## 7. 장면·추적 내부 (확장 시 참고)

- 렌더 루프 `loopScan(tm)`: 120ms마다 `scanQR()` → 코너 `Q`(지수 평활) → `pose()={cx,cy,s,a}` → `g.translate(cx,cy); g.rotate(a)` 후 유형별 장면 함수를 **QR 로컬 좌표**(원점=QR 중심, 단위 px, y 아래)로 그린다. `vis`가 220ms에 걸쳐 0↔1.
- 장면 함수 시그니처 `sceneX(P, el[, dt])` — `el`은 공개 후 경과 ms. 공개 후 `SETTLE[KIND]` ms 지나면 결과 시트(`showPanel`).
- 3D: `<model-viewer>`를 `#stage` 위 절대 위치로 올리고 매 프레임 `mvPlace(P, vis)`로 위치·크기·회전만 맞춘다(원근 없음). 3D 로드 전에는 2D 이미지가 대신 보인다.
- 현재 한계: QR 4코너로 **원근(기울기)** 을 반영하지 않는다(회전·크기만). QR이 화면 밖이면 장면이 사라진다.

---

## 8. 로드맵 (다음 작업)

비용·난이도·가치 기준 우선순위. 각 항목은 **완료 조건**을 만족해야 한다. 가격은 조사 시점 검색 기반이라 구현 전 재확인.

### 2단계 — 부품 교체 (2–6주)
1. **QR 검출기 교체**: Android Chrome은 `BarcodeDetector`(있으면), 그 외 `zxing-wasm`(MIT, 2026-10 릴리스). jsQR은 폴백으로 유지.
   - 완료 조건: 동일 테스트 영상에서 인식 지연·실패율이 jsQR 대비 같거나 개선, iOS Safari 동작, 번들은 지연 로딩.
2. **원근 반영 포즈**: 4코너 → 호모그래피로 장면을 포스터 평면에 원근 투영(2D 캔버스는 `setTransform` 근사 또는 three.js 평면). 3D는 IPPE(solvePnP) 또는 호모그래피 분해로 카메라 포즈 → three.js.
   - 완료 조건: 45° 기울인 포스터에서 오버레이가 포스터 평면에 붙어 보임. `pg`가 있으면 포스터 전체 사각형 정합.
3. **QR 사이 광학 흐름 추적**: QR 인식 프레임 사이를 Lucas-Kanade 등으로 보간해 흔들림·끊김 감소.
4. **3D 엔진 업그레이드**: TRELLIS v1 → **TRELLIS.2**(MIT, 2025-12). 상시 가동 호스트(fal 등)로 콜드스타트 제거. `AR_3D_MODEL`/`AR_3D_INPUT`/폴링 출력 파싱만 바꾸면 된다(`findUrl`이 `.glb` 탐색).
   - 완료 조건: 평균 생성 < 90초, 결과 GLB ≤ 5MB.
   - 금지: **Hunyuan3D 오픈 웨이트**(라이선스가 대한민국 제외).
5. **GLB 경량화 + iOS용 USDZ 사전 생성**: 서버에서 `gltf-transform`(메시 단순화, meshopt *또는* Draco 하나만, 텍스처 ≤1024 KTX2/WebP) 후 USDZ를 만들어 `ios-src`로 지정(model-viewer 자동 변환은 방향 틀어짐·버전 오류 이슈).
6. **3D 대기 UX**: 생성 중에도 배경 제거 카드로 이벤트를 먼저 게시하고, 3D 완성 시 같은 짧은 링크의 설정을 갱신(덮어쓰기 저장 op 추가 필요).

### 3단계 — 움직이는 사진/포스터 (1–3개월)
1. **깊이 기반 2.5D 패럴랙스(무료 기본값)**: 업로드 이미지에서 Depth Anything V2 Small(Apache-2.0, Transformers.js, 브라우저 실행)로 깊이맵 → WebGL 셰이더로 기울기에 따른 입체감. 서버 비용 0, 루프 자동.
2. **AI 루프 영상(유료 크레딧)**: 첫 프레임 = 마지막 프레임 = 업로드 이미지로 5초 클립(Kling/Veo/Runway 등, 약 $0.25/클립 추정). 투명이 필요 없으면 포스터를 덮는 불투명 영상, 필요하면 **stacked-alpha**(색+알파를 한 영상에 쌓아 셰이더로 합성) 방식. `muted playsinline` 필수.
3. **이미지 타깃 추적(보조)**: MindAR(MIT, 2024-01 이후 정체) — 업로드 시 브라우저에서 `.mind` 컴파일. QR로 콘텐츠를 식별·초기 정렬하고 이후 포스터 이미지로 추적.
4. **한국형 템플릿**: AR 명함, 메뉴판(3D 음식), 모바일 청첩장, 매장 POP.

### 4단계 — 프리미엄·실험
캐릭터 자동 리깅(Meshy/Tripo API, 사람형만), 얼굴 포토부스(MediaPipe Face Landmarker, Apache-2.0), 말하는 사진(LivePortrait — 동봉 InsightFace는 비상업이므로 교체 필요), 가우시안 스플랫(웹 전용).

### 운영 과제 (코드 외)
- Upstash Redis 연결 → 통계·3D 일일 제한 활성화.
- 업로드 이미지 개인정보 처리 법률 검토(PIPA: 얼굴 = 민감정보, 국외 이전 고지).
- 실기기 확인: 카카오톡 Android/iOS, 네이버 앱, 인스타그램 인앱, Galaxy A 시리즈 ARCore, iPhone Quick Look.

---

## 9. 검증 방법

```bash
npm install --prefix tools/tests          # playwright-core (최초 1회)
node tools/tests/ar-entry.test.mjs        # 인앱 탈출·카메라 실패·보상 분리·비콘
node tools/tests/ar-image.test.mjs        # 이미지 AR 빌더→고객 흐름(서버 모킹)
```
- 테스트는 저장소 루트를 자체 정적 서버(8099)로 띄우고 `/api/ar-asset`을 `context.route()`로 모킹한다. Chromium 경로는 `CHROME_PATH` 또는 Playwright 캐시에서 찾는다.
- 카메라 시뮬레이션: `addInitScript`로 `navigator.mediaDevices.getUserMedia`를 reject/영원히 대기로 교체. 실제 영상 테스트는 Chromium `--use-fake-device-for-media-stream --use-file-for-fake-video-capture=<y4m>`.
- 장면 확인: `event.html?demo=1&lang=ko#c=<base64url>` 스크린샷.
- 서버 함수 단위 확인: `globalThis.fetch`를 가짜로 바꾸고 `import('./api/ar-asset.js')`의 기본 export에 가짜 `req/res`를 넣어 호출.
- 실서버 확인이 필요하면 임시 self-test 쿼리를 추가해 배포 → 확인 후 **반드시 제거 커밋**(이번 작업에서 그렇게 했다).
