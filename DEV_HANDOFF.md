# 🧩 블록 블라스트 — 몬스터 배틀 · 개발 핸드오프 문서

> 다른 개발자가 이어받아 작업할 수 있도록 현재까지의 진행 상황·구조·남은 작업을 정리한 문서입니다.
> 최종 업데이트: 2026-07-23

---

## 1. 개요

| 항목 | 내용 |
|---|---|
| **게임** | 8×8 블록 퍼즐(Block Blast류) + 몬스터 수집·속성 무기 스킬·콤보·랭킹 |
| **저장소** | `jaythealpha/Jay` |
| **작업 브랜치** | `claude/block-blast-game-design-dr776w` |
| **메인 파일** | `blockblast.html` (단일 파일, 약 1,280줄, 외부 라이브러리 없음) |
| **에셋** | `assets/blockblast/` (스프라이트 PNG, BGM mp3) |
| **기술 스택** | 순수 HTML/CSS/JavaScript (프레임워크·빌드 없음), 선택적 Supabase 백엔드 |
| **상태 저장** | 브라우저 `localStorage` |

### 플레이 링크
- **바로 플레이(작업 브랜치):** https://raw.githack.com/jaythealpha/Jay/claude/block-blast-game-design-dr776w/blockblast.html
- **소스:** https://github.com/jaythealpha/Jay/blob/claude/block-blast-game-design-dr776w/blockblast.html
- **정식 배포 예정:** 기본 브랜치 병합 시 GitHub Pages (`jaythealpha.github.io/Jay/blockblast.html`)

> ⚠️ GitHub에서 파일을 클릭하면 소스만 보입니다. 실행하려면 raw.githack 링크를 열거나 파일을 받아 브라우저에서 여세요.

---

## 2. 실행 / 개발 환경

빌드가 없습니다. 로컬에서 바로 실행:

```bash
# 저장소 클론 후
python3 -m http.server 8000
# 브라우저에서 http://localhost:8000/blockblast.html
```

또는 `blockblast.html`을 브라우저에서 직접 열면 됩니다(단, 상대경로 에셋 로딩을 위해 로컬 서버 권장).

### 자동 테스트 (Playwright 스모크)
정식 테스트 스위트는 없고, 개발 중 Playwright 헤드리스로 검증했습니다. 예시(무오류 + 배치/클리어 확인):

```js
// node + playwright, chromium 실행 후:
// 1) #startBtn 클릭 → 보드 8×8 렌더 확인
// 2) 트레이 조각을 보드로 드래그(pointer 이벤트) → #board .cell.hint 뜨면 드롭
// 3) #scoreVal 증가·.cell.filled 확인, pageerror 0건 확인
```

권장: 향후 CI에 Playwright 스모크(로드·배치·클리어·랭킹 등록) 추가.

---

## 3. 코드 구조 (blockblast.html 내부)

전부 하나의 IIFE `(function(){ ... })()` 안에 캡슐화되어 있습니다. 주요 블록:

| 섹션 | 역할 |
|---|---|
| `Config` | `N=8`, `COST`(파워업 가격), **`LB_CONFIG`(랭킹 백엔드 설정)** |
| `TYPES` / `CHARS` | 11개 속성 정의 + 24종 몬스터 로스터(`id`,`name`,`emoji`,`type`,`boss`) |
| 스프라이트 프리로드 | `assets/blockblast/mon_<id>.png` 로드, 없으면 이모지 폴백 (`spriteCSS`) |
| 테마/UI 에셋 | 배경 테마(`bg.png` 등), UI 아이콘·프레임·로고 점진적 향상 로딩 |
| `SHAPES` | 조각 모양 정의 |
| `State` | `grid, score, coins, best, combo, tray, ...` 게임 상태 |
| `Audio` | **AudioContext 언락**(`ensureCtx`,`unlockAudio`) + 합성 SFX + mp3 BGM |
| `Persistence` | `localStorage` 로드/저장, 일일 연속출석·미션 |
| `Dex/Achievements` | 도감 수집, 업적 토스트 |
| `Board/Pieces` | 보드 렌더(`paint`), 트레이 생성(`newTray`), 조각 엘리먼트 |
| `Placement` | `canPlace`, `anyMove`, `place`, `maybeSpawnObstacle` |
| `applySkill` | 속성별 무기 스킬(추가 제거 셀 계산) |
| `resolveClears` | 줄 판정·점수·콤보·골든·보스·미션·이펙트 오케스트레이션 |
| `Effects` | 파티클, 화면 흔들림, 임팩트 플래시/충격파, 스코어 팝업 |
| `Drag & drop` | 포인터 기반 드래그 + **그리드 자석 스냅** + 햅틱 |
| `Power-ups` | 폭탄/망치/새몬스터 |
| **`Leaderboard`** | Supabase REST 어댑터 + 로컬 Top-10 폴백 (아래 5장 참고) |
| `Game flow` | `startGame`, `endGame` |

### localStorage 키
| 키 | 내용 |
|---|---|
| `bb_best` | 최고 점수 |
| `bb_coins` | 보유 코인 |
| `bb_muted` | 음소거 여부 |
| `bb_streak` / `bb_lastday` | 연속출석 |
| `bb_dex2` | 수집한 몬스터 이름 배열 |
| `bb_ach` | 달성 업적 id 배열 |
| `bb_mission` | 오늘의 미션 상태 |
| `bb_name` | 랭킹 등록용 이름 |
| `bb_lb` | 로컬 랭킹 Top-50 (백엔드 미설정 시) |
| `bb_theme` | 선택한 배경 테마 |

---

## 4. 게임 기능 요약 (구현 완료)

- **핵심 루프**: 조각 3개 트레이 → 드래그 배치 → 가로/세로 줄 채우면 클리어
- **중독성 요소**: 🔥콤보 배율, ⚡멀티라인 보너스, 💰코인+파워업, 📅연속출석, 🎯일일미션, 🏆업적/신기록, ⚠️위기경고
- **몬스터**: 🐾24종(오리지널 디자인) + 📖도감 수집, ⚔️속성별 무기 스킬 8종(전기/불/물/풀/에스퍼/고스트/노말/페어리 + 얼음/바위/레전드)
- **특수 요소**: 🧊얼음 블록 장애물, ✨골든 몬스터(점수3배), 👑보스 웨이브(15줄마다), 🎨배경 테마 전환
- **연출**: 파티클·화면흔들림·임팩트·충격파·히트스톱, 📳햅틱, 🔊합성 사운드 + BGM
- **랭킹**: 글로벌(Supabase) / 로컬 폴백 (아래 참고)

---

## 5. 랭킹 시스템 (중요 — 백엔드 연결 필요)

### 동작
- `blockblast.html` 상단 `LB_CONFIG`에 Supabase `url`+`key`가 있으면 **글로벌 모드**, 없으면 **로컬 Top-10 모드**로 자동 동작.
- `LB` 객체가 어댑터: `top(n)`(조회), `submit(entry)`(등록), `rankOf(score)`(순위). 온라인 실패 시 로컬로 graceful fallback.
- 게임 오버 → 이름 입력 → `랭킹 등록` → 순위 표시 + 랭킹판 자동 오픈.

### 글로벌 켜는 법 (개발자 작업)
1. **`LEADERBOARD_SETUP.md`** 참고 (5분): Supabase 무료 프로젝트 생성 → 테이블 SQL + RLS 정책 실행 → Project URL·anon 키 확보.
2. `blockblast.html`의 `LB_CONFIG` 채우기:
   ```js
   const LB_CONFIG={ url:"https://xxxx.supabase.co", key:"<anon public key>", table:"leaderboard" };
   ```
3. 새로고침 시 랭킹 화면이 `🌍 글로벌`로 전환.

> anon 키는 클라이언트 공개용이라 소스에 넣어도 안전. RLS로 읽기 + insert만 허용(수정/삭제 불가).

---

## 6. 커밋 이력 (이번 작업분)

| 커밋 | 내용 |
|---|---|
| `56b05e3` | 블록 블라스트 콤보 러시 최초 버전 |
| `4fb51e3` | 몬스터 배틀 + 무기 스킬 + 도감 + 타격감 |
| `c2e1fb1` | 오리지널 몬스터 15종 개명 + 스프라이트/사운드 로딩 구조 |
| `7f137fb` | Higgsfield 생성 에셋 통합(스프라이트15·배경·BGM·효과음) |
| `2aa2110` | 그래픽/게임플레이 강화(배경·생동감·얼음·골든·보스·미션·테마·24종) |
| `6474cdc` | 온라인 글로벌 랭킹(서버리스 + 로컬 폴백) |
| `f073192` | 무음 버그 수정(AudioContext 언락) |
| `48abab1` | 소리 합성음 전환 + 터치감(그리드 스냅·햅틱) 개선 |

---

## 7. 에셋 현황 (Higgsfield AI 생성)

### ✅ 통합 완료 (`assets/blockblast/`)
- 몬스터 스프라이트 15종: `mon_jiji, bulkkori, hwaryong, mongbul, bangul, padowang, mulyong, saessak, kkotbong, mironyang, kkummong, kulkul, yeoubyeol, pungseon, yuryeong`
- 배경 `bg.png`, 썸네일 `thumbnail.png`, 파비콘 `favicon.png`, BGM `bgm.mp3`
- 효과음 mp3 5종(현재 코드는 합성음 사용, mp3는 미사용 상태로 남아있음)

### ⏳ 생성 대기 (파일 없으면 이모지/기본 배경으로 자동 폴백 — 게임은 정상 동작)
아래 파일들을 `assets/blockblast/`에 넣으면 코드가 자동 인식(별도 수정 불필요):
- 신규 몬스터 스프라이트 9종: `mon_seorigom, mon_nunsongi, mon_binghapeng, mon_bawidori, mon_moraeyeou, mon_sujeong, mon_beongaetokki, mon_hwasanagi, mon_hwanggeummong`(보스)
- UI 아이콘: `ui_bomb.png, ui_hammer.png, ui_refresh.png`
- 보드 프레임 `ui_frame.png`(가운데 빈 액자), 타이틀 로고 `ui_logo.png`(16:9)
- 배경 테마 2종: `bg_ice.png, bg_volcano.png`
- 스타일 가이드: 청키 16비트 픽셀아트, 속성별 선명한 색, 스프라이트는 마젠타/그린 키컬러 배경 → 키컬러 제거 후 128px

> 이미 생성 제출된 4종(서리곰·빙하펭·망치아이콘·수정사슴)은 Higgsfield 계정 라이브러리에 있음 — 다운로드해 저장만 하면 됨.

---

## 8. 남은 작업 (TODO)

### 🔴 우선 — 백엔드 연결 (랭킹 실사용 전제)
- [ ] Supabase 프로젝트 생성 + `LB_CONFIG` 연결 → 글로벌 랭킹 활성화 (`LEADERBOARD_SETUP.md`)
- [ ] (선택) 어뷰징 방지: Edge Function 서버 검증 또는 rate-limit

### 🟡 실시간 1:1 대전 (설계됨, 미구현)
Supabase Realtime 채널 기반 듀얼 모드. **주의: 코어 루프를 건드리고, 실제 2대 기기 + 라이브 백엔드가 있어야 테스트 가능.** 백엔드 연결 후 착수 권장.
- [ ] 방 코드(4자리)로 매칭 — Supabase Realtime presence/broadcast
- [ ] 방 코드로 시드된 결정론적 RNG(공정한 조각 순서) — 현재 `Math.random` 사용부(`randShape`,`randChar`) 추상화 필요
- [ ] 90초 타이머 + 상대 점수 실시간 HUD
- [ ] 2줄+ 클리어 시 상대에게 🧊얼음 방해 블록 전송(기존 obstacle 시스템 재활용)
- [ ] 승패 판정 + 재대결

### 🟢 에셋 마감
- [ ] 신규 스프라이트/UI/배경 12종 생성·후처리·커밋 (7장 참고)

### ⚪ 배포
- [ ] 기본 브랜치 병합 → GitHub Pages 활성화 (`.github/workflows/pages.yml` 참고, 현재 기본 브랜치는 `claude/expand-korean-market-strategy-dPuXy`)

---

## 9. 알려진 이슈 / 참고

- **효과음 mp3 미사용**: `sfx_*.mp3`는 무음/재생실패 시 폴백이 안 되는 구조적 취약점 때문에 합성음(WebAudio)으로 대체함. mp3를 다시 쓰려면 재생 검증 로직 보강 필요.
- **오디오 자동재생**: 브라우저 정책상 첫 사용자 제스처 전에는 소리 안 남(정상). `unlockAudio`가 첫 pointerdown/touchstart/keydown에서 언락.
- **드래그 좌표**: `hoveredCell`이 손가락 오프셋(`offX/offY`)을 빼서 앵커 셀 계산 → 유효 시 그리드에 자석 스냅. 오프셋 수정 시 배치 정확도 영향.
- **저작권**: 몬스터는 전부 오리지널 디자인(포켓몬 등 실제 IP 미사용) — 공개 배포 안전. 이 방향 유지 권장.

---

## 10. 파일 맵

```
Jay/
├─ blockblast.html          ← 게임 본체 (이 작업의 메인)
├─ DEV_HANDOFF.md           ← (이 문서)
├─ LEADERBOARD_SETUP.md     ← 글로벌 랭킹 Supabase 설정 가이드
├─ assets/blockblast/       ← 스프라이트·배경·BGM (+ 대기 중 에셋 자리)
├─ README.md                ← (기존: 직장인 생존기 게임 설명)
├─ index.html / v2.html / en.html  ← (기존 별개 게임)
└─ .github/workflows/pages.yml     ← GitHub Pages 배포 워크플로
```

> 참고: `index.html`, `v2.html` 등은 이 저장소의 **다른 게임**(직장인 생존기)입니다. 블록 블라스트는 `blockblast.html` 단일 파일입니다.
