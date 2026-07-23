# Aesthetic QR Studio — 개발 인계 문서 (Handoff)

> 목적: 지금까지의 진행 상황을 개발자와 공유해 이어서 작업할 수 있도록 정리한 문서입니다.
> 최종 정리: 2026-07-17 · 현재 빌드 `2026.07.16-f`

---

## 0. 한 줄 요약

브라우저에서 도는 **단일 HTML 파일** QR 코드 디자인 스튜디오. 서버·DB·로그인 없이 100% 클라이언트 사이드로 동작(단, AI 아트 QR만 `/api/art-qr` 서버리스 함수 사용). Vercel 정적 배포, 한/영/일/중 4개 언어.

- **라이브(프로덕션 추정)**: https://jay-inky.vercel.app
- **리포지토리**: `jaythealpha/Jay`
- **작업 브랜치**: `claude/website-analysis-implementation-8rolis` ← **모든 QR 스튜디오 작업이 여기 있음**

---

## 1. ⚠️ 가장 먼저 확인할 것 — "새 프레임(우표 등)이 라이브에 안 보임" 이슈

사용자가 라이브 사이트에서 새로 추가한 프레임(우표/조개/포스터)이 안 보인다고 함. **코드에는 정상적으로 있고 브랜치에 push까지 완료된 상태**이므로, 원인은 배포 파이프라인일 가능성이 높습니다. 개발자가 아래를 확인해 주세요.

**확인된 사실**
- 새 프레임 버튼은 `qr-studio.html`(및 미러 `index.html`)에 존재하고 HEAD에 커밋됨:
  ```
  <button data-fstyle="stamp"> 우표
  <button data-fstyle="shell"> 조개 장식
  <button data-fstyle="poster"> 포스터
  ```
- headless(Chromium) + jsQR로 10종 프레임 전부 렌더·디코드 검증 통과.
- 원격에 **`main`/`master`/production 브랜치가 없음.** origin 브랜치는 2개뿐:
  - `claude/website-analysis-implementation-8rolis` → **이 QR 스튜디오**
  - `claude/expand-korean-market-strategy-dPuXy` → **전혀 다른 프로젝트(itch.io 게임)**. QR 스튜디오 아님.
- `.vercel/project.json`은 리포에 커밋돼 있지 않음(프로젝트/조직 ID를 리포에서 알 수 없음).
- `vercel.json`은 HTML에 `Cache-Control: max-age=0, must-revalidate`를 설정 → 브라우저 캐시는 원인이 아니어야 함.
- 이 개발 환경의 아웃바운드 프록시가 `jay-inky.vercel.app` 접속을 차단(HTTP 000)해서, **에이전트가 라이브 사이트 내용을 직접 확인하지 못함.**

**개발자 확인 액션 (우선순위 순)**
1. **Vercel 프로젝트의 "Production Branch" 설정**이 `claude/website-analysis-implementation-8rolis`를 가리키는지 확인. 아니라면 → 이 브랜치를 프로덕션 브랜치로 지정하거나, 프로덕션 브랜치로 머지.
2. Vercel Deployments에서 **가장 최근 커밋(`a829dd1` "Make frames boldly recognizable at a glance")이 빌드·배포됐는지** 확인. 빌드 실패/대기 상태면 재배포(Redeploy).
3. 라이브에서 `verTag`가 `2026.07.16-f`인지 확인. 낮으면 배포 미반영. (푸터 "빌드" 옆 표시)
4. 위가 모두 정상인데도 안 보이면 CDN/edge 캐시 무효화(Redeploy 시 자동) + 사용자 강력 새로고침(Ctrl/Cmd+Shift+R).

> 참고: 리포가 여러 프로젝트를 섞어 담고 있음(`v2.html`, `en.html`, `LAUNCH.md`, `yogibo-korea-10x-strategy.md`, `tools/` 등은 QR 스튜디오와 무관해 보임). QR 스튜디오의 실제 파일은 **`qr-studio.html`(원본) + `index.html`(배포 미러)** 두 개.

---

## 2. 실행 & 검증 방법

### 로컬 실행
정적 파일이라 서버만 있으면 됨:
```bash
python3 -m http.server 8799
# http://127.0.0.1:8799/index.html
```
AI 아트 QR(`/api/art-qr`)은 Vercel 서버리스 함수라 로컬 정적 서버에서는 동작 안 함(그 외 기능은 전부 로컬에서 동작).

### 스캔 가능성(핵심) 검증
이 앱의 제1원칙은 "실제로 스캔되는 QR". 디자인을 바꾸면 **반드시 jsQR로 디코드 검증**함. 방식:
- headless Chromium(`--single-process`)으로 페이지 로드 → 프리셋/옵션 적용 → `#preview` 캔버스를 offscreen에 그림 → `jsQR`로 디코드 → 원문 일치 확인.
- 단일 프로세스 Chromium이 여러 번 렌더하면 종종 크래시함 → **프레임/프리셋별로 fresh browser**를 띄우는 패턴 권장.
- 참고 하니스: 세션 스크래치패드에 다수 존재(예: `frames.js`, `bulk.js`, `pro.js`, `exportopts2.js`). 리포에는 포함 안 됨(임시 검증용).

### 편집 규칙
- `qr-studio.html`을 수정한 뒤 **반드시 `cp qr-studio.html index.html`로 미러 동기화** (배포는 `index.html` 기준).
- 푸터의 `verTag`(빌드 번호) 갱신.

---

## 3. 코드 구조 (single-file 아키텍처)

`qr-studio.html` 한 파일에 HTML/CSS/JS 전부 인라인. 주요 부분:

- **전역 상태 `S`** (IIFE 스코프, `page.evaluate`에서 직접 못 읽음 → DOM 통해 관찰): 색상/모듈/눈/프레임/센터/애니메이션/내보내기/Pro 등 모든 디자인 상태.
- **QR 인코딩**: 벤더 `qrcode-generator`(MIT). UTF-8 바이트모드 강제(한글/이모지 라운드트립).
- **렌더 파이프라인**: `render(g, exportSize)` → `getMatrix()`(빌드+캐시) → `drawModule`/`drawEye`(모듈·눈 도형) → 프레임/센터/라벨/애니 오버레이.
- **i18n**: `I18N` 딕셔너리 + `t(key)` + `applyLang(lang)`. DOM 속성 `data-i18n`(textContent) / `data-i18n-html`(innerHTML) / `data-i18n-tip`(data-tip) / `data-i18n-ph`(placeholder). **주의: `data-i18n`은 textContent를 덮어써서 중첩 자식을 지움** — 부분 스타일 텍스트는 문자열 자체에 넣을 것.
- **갤러리 프리셋**: `CATS`(standard/animation/logo/pictogram/frame/usecases) + `renderPreset()`(상태 save/복원 후 오프스크린 렌더).
- **벤더 라이브러리**: `vendor/` — jsQR(스캔 디코드), face-api(얼굴 트래킹), mindar-image(이미지 마커). face-api·MindAR 둘 다 TensorFlow.js 번들 → **동시 로드 시 충돌** → 지연 로드 + 가드로 회피.

### 자주 건드리는 함수/위치 (이름으로 검색)
| 기능 | 함수/식별자 |
| --- | --- |
| 프레임 배경/액자 | `drawFrameBackground(g,size,fi,rg)` |
| 프레임 인셋(크기) | `FRAME_INSET` 맵 (render 내부) |
| 프레임 필드 표시 | `frameStyleVis()` |
| PNG/JPG 내보내기 | `exportPNG()` / `copyPNG()` / `S.exportRes`,`S.exportFmt` |
| 대량 생성 | `generateBulkSheet()` |
| Pro(유료) 시스템 | `PRO` 객체, `isPro()`, `proGated()`, `validateLicense()`, `openPro()` |
| 픽토그램 투명도 곡선 | `centerOpacity()`, `_COPACITY` |
| 라벨(텍스트/프레임) | `S.labelOn/labelText`, render의 label 패스 |

---

## 4. 이번 세션까지 완료된 기능 (요약)

- **픽토그램 크기 100% + 적응형 투명도**: 크기 커지면 QR 비치도록 자동 투명(실측 곡선, 9종 픽토그램 33~100% 디코드 검증).
- **프리미엄 UX/UI 리디자인**: 글래스모피즘, 오로라 배경(순수 CSS) + 필름그레인, 스티키 글래스 헤더, 히어로 개선.
- **히어로 아트 훅**: `assets/hero-bg.webp`(다크 오로라, PIL 제작) + `--hero-bg` CSS 변수로 on/off. 교체는 같은 파일명 덮어쓰기.
- **툴팁 z-index/클리핑 수정**: 글래스 쌓임맥락으로 가리던 문제 해결.
- **로고 갤러리 정비**: 애니 캡션이 배경에 구워져 흔들리던 버그 수정(라이브 라벨로 분리), 텍스트 전용 로고 12종 삭제, **오리지널 브랜드 10종**(맥주 5·커피·테크·에너지·스포츠·리빙)으로 재구성. *실제 상표는 저작권 문제로 미사용 — 전부 오리지널 그래픽.*
- **내보내기 옵션**: 해상도 1024/2048/4096 + 형식 PNG/JPG(투명→흰 배경 처리), 인쇄 크기(300DPI) 툴팁.
- **대량(Bulk) 생성**: 여러 항목 → 인쇄용 PNG 시트(테이블번호·티켓·라벨). 백엔드 불필요.
- **수익화(Pro) 시스템**: 원타임 언락 스캐폴딩(아래 6장).
- **문구 재포지셔닝**: "100% 무료" 제거 → 애니메이션·프라이버시 강조.
- **프레임 대개편**(현재 작업): 6종 대담화/신규(아래 5장).

---

## 5. 프레임 시스템 상세 (현재 활성 작업)

`drawFrameBackground`가 QR **뒤에** 배경+액자를 그림. 스캔 유지를 위해 **장식은 바깥 밴드에만**, 그리고 각 스타일 끝에서 흰 카드(`fillRoundCard`)를 마지막에 칠해 QR 영역을 항상 깨끗하게 덮음.

- **인셋 = 프레임 크기**: `FRAME_INSET` 맵으로 스타일별 지정. 장식 프레임은 크게(예: neon/wood/stamp 0.15, shell/poster 0.185~0.20, circle 0.20). 값이 클수록 액자가 크고 QR이 작아짐(60~70%). "프레임이 티가 안 난다" 피드백 → 인셋을 키워 해결.
- **폴라로이드**: `polaBottom`으로 하단 흰 여백을 크게 잡아 QR을 위로 올림(실제 즉석사진 느낌) + 손글씨 밑줄/하트/워시테이프.
- 스타일: `card`(기본), `wood`(3D 몰딩+마이터), `gold`(금박 액자), `polaroid`, `shadow`(패스파르투), `neon`(두꺼운 이중 네온관+글로우+나사), `stamp`(천공+AIR MAIL 세리프+소인+₩), `shell`(스캘럽 도일리+조개 부채), `poster`(비비드+"스캔하세요" 헤드라인+떠있는 카드), `circle`(닷 링).
- 각 프레임 색상은 컬러 픽커(`frameBg1`/`frameBg2`)로 변경. 어떤 스타일이 어떤 색을 쓰는지는 `frameStyleVis()`가 제어.
- **검증 완료**: 10종 전부 jsQR 디코드 OK, 페이지 에러 없음.

---

## 6. 수익화(Pro) 시스템 현황 — 오너가 채워야 실제 과금 가능

원타임 "Pro" 언락 스캐폴딩만 구현됨(실제 결제는 미연결).

- **아키텍처**: Merchant-of-Record(Lemon Squeezy / Gumroad / Paddle) 권장 → 카드결제 + 한국 부가세 + 라이선스 키 발급을 대행 → **자체 백엔드/사업자등록 없이 시작 가능**. 앱은 라이선스 검증 fetch 한 번만.
- **오너 설정(코드 `PRO` 객체)**: `PRO.checkoutUrl`(결제 링크), `PRO.validateUrl`(라이선스 검증 API) 두 값만 채우면 됨. 미설정 시 개발용 오프라인 키 `QRPRO-XXXX-XXXX`로 플로우 테스트 가능.
- **현재 게이팅**: 고해상도 내보내기(2048/4096)만 Pro. `PRO.gate`에 `aiArt`, `cleanAnim` 등 한 줄로 추가 가능(예정).
- **정직한 한계**: 정적 페이지라 클라이언트 검증은 우회 가능(저가 툴 업계 표준). 진짜 비용 드는 AI 아트는 서버(`/api/art-qr`)에서 라이선스 강제 권장.
- 시장 근거: 크몽에서 디자인 QR 대행이 건당 5,000~10,000원, 대량 30,000원에 거래(상위 기그 판매 422건). 이 앱은 그 셀프서비스 대체재.

---

## 7. 남은 결정 / TODO

- [ ] **배포 이슈 해결**(1장) — 최우선.
- [ ] Pro 결제 연결: MoR 상품 생성 + `PRO.checkoutUrl`/`validateUrl` 입력 + 가격 확정(₩9,900~19,900 원타임 검토).
- [ ] Pro 게이팅 범위 확정: AI 아트 / 워터마크 없는 애니 / 대량 생성 중 어디까지 잠글지.
- [ ] AR: 베타 유지 / 완전 제거(앱 경량화) / 투자 중 방향 결정. 현재 `BETA` 배지.
- [ ] (선택) 동적 QR + 스캔 분석 — 경쟁사 핵심 유료 기능이나 **백엔드 대형 프로젝트**(URL단축·리다이렉트·DB·대시보드). 제품이 SaaS로 전환됨.
- [ ] 리포 정리: QR 스튜디오와 무관한 파일/브랜치(게임 프로젝트) 분리 검토.

---

## 8. 알려진 제약 & 주의사항

- **AI 이미지 생성 MCP(Higgsfield)**: 이 개발 환경(비대화형)에서 승인 벽으로 **사용 불가**(비용 프리플라이트조차 실패). 그래서 히어로/프레임 등은 전부 코드(캔버스)·PIL로 제작. 스캔되는 QR 프레임엔 캔버스가 오히려 적합(4096px 선명, 에셋·스캔 문제 없음).
- **아웃바운드 프록시**: 외부 사이트 fetch가 대부분 403/000으로 차단됨(라이브 사이트 직접 확인 불가, 리서치 원문 재검증 불가).
- **사운드**: 앱에 오디오 기능 없음(버튼음/스캔음 없음). 영상 아트 QR은 음소거 재생이 기본, WebM 저장물은 오디오 트랙 없음(캔버스만 녹화).
- **트레이드마크/저작권**: 실제 브랜드 로고·제품 이미지는 미사용 원칙. 오리지널 그래픽만.
- **커밋 규칙**: 커밋 메시지/PR/코드에 모델 식별자 넣지 않음. 트레일러 유지(Co-Authored-By / Claude-Session).

---

*문의: 이 문서는 진행 상황 스냅샷입니다. 세부 커밋 이력은 `git log`(브랜치 `claude/website-analysis-implementation-8rolis`) 참고.*
