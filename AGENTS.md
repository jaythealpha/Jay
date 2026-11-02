# AGENTS.md — 작업 규칙 (Codex · Claude Code 공통)

이 저장소에는 두 가지가 섞여 있다. **작업 대상은 "Aesthetic QR Studio"** (QR 디자인 스튜디오 + AR 이벤트)이다.
`README.md`, `v2.html`, `en.html`, `tools/build_itch.sh`, `yogibo-*.md`는 다른 프로젝트(게임 등)이므로 건드리지 않는다.

- 라이브: https://jay-inky.vercel.app (Vercel 프로젝트 `jay`) — 아래 브랜치에 push하면 프로덕션으로 자동 배포된다.
- 작업 브랜치: `claude/website-analysis-implementation-8rolis` (main 브랜치 없음).
- 먼저 읽을 문서: **`docs/ar-concept.md`** (AR 컨셉·구조·설정 키·API·로드맵·검증), `HANDOFF.md`(앱 전반, 일부 오래됨), `docs/research/ar-qr-tech-research-2026-11.md`(기술 조사).

## 구조
| 파일 | 역할 |
|---|---|
| `qr-studio.html` | 메인 앱, 단일 HTML(CSS·JS 인라인). 빌드 단계 없음. |
| `index.html` | `qr-studio.html`의 **복사본**. 수정 후 항상 `cp qr-studio.html index.html`. |
| `event.html` | 고객용 AR 이벤트 런타임(단일 파일). |
| `map.html`, `motion.html` | 지도 앱 선택 페이지, 모션 실험실. |
| `api/*.js` | Vercel 서버리스 함수(ESM `export default handler`, npm 의존성 없음, `fetch`만 사용). |
| `vendor/` | 서드파티 JS를 직접 동봉(CDN 금지 — 일부 환경에서 차단됨). |
| `tools/tests/` | 헤드리스 브라우저 테스트(`npm install --prefix tools/tests` 후 `node tools/tests/<name>.test.mjs`). |

## 반드시 지킬 규칙
1. **루트에 `package.json`/빌드 설정을 추가하지 않는다.** Vercel이 정적 사이트 + 의존성 없는 함수로 배포 중이다.
2. **버전 태그 올리기**: `qr-studio.html`의 `<b id="verTag">YYYY.MM.DD-x</b>` (같은 날 여러 번이면 a→b→c). 그다음 `index.html` 복사.
3. **i18n (ko/en/ja/zh 4개 언어 모두)**
   - UI 문자열은 `I18N` 객체에 `"key":{ko:"…",en:"…",ja:"…",zh:"…"}`로 추가하고(관례상 `"foot.contact":` 줄 바로 앞), 마크업은 `data-i18n="key"`(HTML이면 `data-i18n-html`), JS는 `t("key")`.
   - 갤러리 이름·태그는 한국어 원문 + `GAL_TR` 번역.
   - `event.html`은 파일 안의 `ALL={ko:{…},en:{…},ja:{…},zh:{…}}`에 같은 키를 4개 언어로 추가.
   - 다른 언어 화면에 한국어가 섞이면 버그다.
4. **QR은 스캔되어야 한다.** 갤러리/프리셋을 바꾸면 jsQR 디코드 테스트로 확인(로고·이미지 중앙 배치는 ECC H, 로고는 QR 폭 ~38% 이하).
5. **AR 원칙**(상세는 `docs/ar-concept.md` §1): 보상은 AR 성공과 분리, 모든 실패에 대체 경로, 무거운 라이브러리는 지연 로딩, 고객 카메라 영상은 기기 밖으로 보내지 않음, 서버 기능이 없으면 이유를 화면에 표시.
6. **이벤트 설정 키는 짧게**(QR 밀도). 새 키 = `event.html`에서 읽기 + 빌더 `EVB.cfg()`에서 쓰기 + `docs/ar-concept.md` §4 표 갱신.
7. **퍼널 이벤트 이름**은 `event.html`의 `track()` 호출과 `api/ar-asset.js`의 `EV_NAMES`를 함께 수정. 이벤트 ID 계산은 `event.html`(`EVID`)과 빌더(`evIdOf`)가 같아야 한다.
8. **비밀값**(토큰·키)을 코드·커밋·로그에 넣지 않는다. 환경변수는 Vercel 프로젝트 설정에서 관리.
9. 사이트 공개 연락처는 `jay@jaythealpha.com`. 개인 이메일을 노출하지 않는다.
10. 서드파티 상표/로고를 새로 만들지 않는다(공식 브랜드 로고 외). 갤러리 로고 이름은 가상의 이름.
11. `research_notes/`, `reports/`, `tools/tests/node_modules`는 커밋하지 않는다(.gitignore). 저장소 루트는 그대로 웹에 공개되므로 작업용 파일을 루트에 두지 않는다.
12. 실서버 확인용 임시 코드(self-test 엔드포인트 등)는 확인 후 같은 작업 안에서 제거 커밋한다.

## 작업 흐름
1. 변경 → 관련 테스트 실행(§ `docs/ar-concept.md` 9) → 화면 스크린샷으로 확인(데스크톱 1280px + 모바일 390px, 가로 스크롤 없음).
2. 버전 태그 올리기 → `cp qr-studio.html index.html`.
3. 커밋 메시지는 영어 요약 1줄 + 변경 목록. push는 위 브랜치로만. PR은 요청이 있을 때만.
4. 배포 후 Vercel 배포 상태(READY)와 라이브 동작 확인.
