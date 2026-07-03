# LemioCode 분석 & 재구현 — Aesthetic QR Studio

참고 사이트: **https://lemiocode.com/gallery** (LemioCode — Transform the Ordinary. Aesthetic QR Codes)

이 문서는 LemioCode의 컨셉과 핵심 기술을 분석하고, 동일한 기술을 오픈소스로 재구현한
웹앱 **`qr-studio.html`** 의 설계를 정리한 것입니다.

---

## 1. 원본 사이트 분석

### 컨셉
- **슬로건**: "Transform the Ordinary." — 평범한 흑백 QR 코드를 **브랜드 디자인 자산**으로 변환.
- **제품**: 미적(aesthetic) QR 코드 생성기. 핵심은 로고 삽입이 아니라 **이미지·영상 전체가 QR 코드 그 자체가 되는 "아트 QR"**.
  - **정적(Static)** QR — 이미지 기반, 그림 전체가 코드.
  - **애니메이션(Animated)** QR — 영상/GIF 기반, 움직이는 아트 QR.
- **갤러리(`/gallery`)**: 영감을 주는 디자인 샘플 쇼케이스(애니 캐릭터·동물·만화풍 등 그림 전체가 QR).
- **타깃**: 마케팅 에이전시, 이벤트 주최자, 크리에이터 — 심미성·브랜드 정합성·분석을 중시하는 세그먼트.

### 실제 원본의 핵심 기술 — Stable Diffusion + ControlNet
LemioCode는 **AI 생성(Stable Diffusion) + ControlNet** 기반의 아트 QR입니다(특허 출원 중 스캔 최적화).
ControlNet이 **QR 패턴을 "밝음/어둠 조건(condition)"** 으로 확산 모델에 주입해, AI가 그림의
명암·질감·오브젝트 배치를 **QR 모듈에 맞춰** 생성 → 그림 전체가 스캔 가능한 코드가 됩니다.

### 이 재구현의 접근 — 서버 없이 동일한 결과
브라우저에는 GPU 확산 모델이 없으므로, **이미지 블렌딩(halftone/per-cell overlay)** 으로 동일한
*결과*(그림이 코드 전체에 반영 + 스캔됨)를 재현합니다. 업로드 미디어를 QR 영역 전체에 깔고,
각 셀을 **반투명 명암 오버레이**로 덮어 셀 평균 밝기가 모듈을 정확히 인코딩하게 합니다.
"아트 노출도" 슬라이더로 그림 노출 vs 스캔 안정성을 조절합니다.

### 핵심 질문 — "예쁜데 어떻게 스캔이 되는가?"
QR 규격의 **Reed–Solomon 오류 정정(Error Correction)** 이 비밀입니다.
QR은 오류정정 레벨에 따라 최대 **30%(레벨 H)** 손상돼도 원본 데이터를 복원합니다.
이 "여유분"을 **디자인 예산**으로 사용해 색·형태·로고·움직임을 얹어도 스캐너가 데이터를 복구합니다.

| ECC 레벨 | 복원 가능 손상률 | 용도 |
|---|---|---|
| L | ~7% | 데이터 최대, 디자인 최소 |
| M | ~15% | 기본 |
| Q | ~25% | 로고 중간 |
| H | ~30% | 로고/헤비 스타일 (권장) |

---

## 2. 재구현 — Aesthetic QR Studio

### 파이프라인
```
텍스트/URL
   │  ① 인코딩 (ECC 레벨 선택, 자동 버전, UTF-8)
   ▼
QR 매트릭스 (모듈 격자, boolean 2D)
   │  ②-A 🖼️ 이미지·영상 아트 QR (핵심)
   │      - 미디어를 QR 전체에 cover-fit
   │      - 셀 단위 반투명 명암 오버레이 → 그림 반영 + 스캔 보장
   │      - 영상 → 프레임 실시간 합성(애니메이션 QR)
   │  ②-B 스타일 렌더링 (아트 미사용 시)
   │      - 모듈 5종(사각/둥근/점/클래시/다이아) · 눈 4종
   │      - 연결형 라운딩(neighbour-aware) → 스캔성 유지
   │  ③ 컬러(단색/선형·원형 그라디언트) · ④ 로고 합성 · ⑤ 애니메이션
   ▼
내보내기: PNG(1024px) · SVG(벡터) · WebM(애니메이션) · 클립보드
   │  ⑥ 📷 AR 미리보기: getUserMedia 카메라 위에 QR 배치·촬영
```

### 핵심 기술 결정

**① 검증된 인코더**
- Kazuhiko Arase의 `qrcode-generator` (MIT) 사용 — Reed–Solomon 포함, 검증된 스캔성.
- **UTF-8 인코딩 강제** (`stringToBytesFuncs['UTF-8']`): 라이브러리 기본값은 Latin1이라
  한글/일본어/이모지가 깨짐 → UTF-8로 전환해 유니코드 라운드트립 보장.

**② 연결형 라운딩 (Connected Rounding) — 스캔성의 핵심**
- 순진한 방식(각 모듈을 독립된 점/둥근사각으로 렌더)은 잉크 커버리지가 낮아
  엄격한 디코더(jsQR)에서 **디코딩 실패**.
- 해결: 각 모듈의 **상하좌우 이웃(dark neighbour)** 을 검사해, 이웃이 없는 모서리만 둥글게 처리.
  인접한 채워진 셀은 변을 공유하며 **매끄러운 덩어리(blob)로 병합** → 높은 잉크 커버리지 + 유기적 외형.
- 이 기법으로 `둥근`·`클래시` 스타일이 예쁘면서도 안정적으로 스캔됩니다.

**③ 눈(Finder) 렌더링**
- 3개의 파인더 패턴을 별도 스타일(사각/둥근/원형/잎사귀)로 렌더.
- 중앙 스캔라인의 1:1:3:1:1 비율을 최대한 보존해 디코더 호환성 유지.

**④ 애니메이션 = 고정 패턴 + 움직이는 컬러**
- QR 패턴(모듈 위치)은 고정, 그라디언트 레이어만 애니메이션 → **모든 프레임이 스캔 가능**.
- `MediaRecorder` + `canvas.captureStream()` 로 WebM 영상 내보내기(외부 인코더 불필요).

**⑤ 스캔성 실시간 경고**
- 전경↔배경 **대비(contrast ratio)** 계산 → 2.6 미만이면 경고.
- ECC 대비 로고 크기 초과 경고, 장식용 모듈(다이아) 경고.

### 기술 스택
| 영역 | 기술 |
|---|---|
| 인코딩 | `qrcode-generator` (MIT, Reed–Solomon) + UTF-8 |
| 렌더링 | 순수 Canvas 2D (연결형 라운딩, 그라디언트, 로고 합성) |
| 벡터 출력 | 런타임 SVG 생성 (모듈별 path/circle + gradient defs) |
| 애니메이션 | MediaRecorder + captureStream → WebM |
| 배포 | 빌드 없는 단일 HTML, GitHub Pages |
| 프라이버시 | 100% 클라이언트 사이드 — 데이터가 기기를 떠나지 않음 |

---

## 3. 스캔성 검증 (자동)

헤드리스 Chromium(Playwright)으로 렌더링 → **jsQR 디코더**로 실제 디코딩하여
스캔 가능 여부를 자동 검증했습니다.

**결과: 24개 시나리오 중 23개 통과 (95.8%)**

- ✅ 모든 실용 모듈 스타일: 사각 / 둥근 / 점 / 클래시
- ✅ 모든 눈 스타일: 사각 / 둥근 / 원형 / 잎사귀
- ✅ 선형·원형 그라디언트 (적정 대비)
- ✅ 유니코드: 한글 · 일본어 · 이모지 (UTF-8 라운드트립)
- ✅ WiFi 접속 문자열, 300자 장문
- ✅ 전 ECC 레벨 (L/M/Q/H)
- ✅ 투명 배경, 하단 라벨
- ✅ 실사용 프리셋 (네온/오션/선셋)
- ⚠️ `다이아` 모듈만 jsQR 실패 — 완전 분리형 모듈. **장식용**으로 분류하고 UI에서 스캔 경고 표시
  (jsQR은 실제 폰 카메라보다 엄격하므로 폰에서는 스캔되는 경우가 많음).

> 검증 방식이 엄격한 소프트웨어 디코더(jsQR) 기준이므로, 통과 항목은 실제 스캐너에서
> 더 안정적으로 동작합니다.

---

## 4. 사용법

`qr-studio.html` 을 브라우저로 열기만 하면 됩니다 (서버·빌드 불필요).

1. **갤러리** 탭에서 마음에 드는 프리셋 클릭 → 스튜디오로 로드
2. **스튜디오** 탭에서 콘텐츠·색상·모듈·눈·로고·애니메이션 편집
3. **PNG / SVG / 애니메이션(WebM) / 클립보드** 로 내보내기
4. **기술 분석** 탭에서 원리 확인

---

## 5. 배포 (Deployment)

빌드 과정이 없는 정적 웹앱이라 어떤 정적 호스팅에도 그대로 올라갑니다.

### Vercel (원클릭)

루트(`/`)가 `qr-studio.html` 로 뜨도록 `vercel.json` 에 rewrite를 설정해 두었습니다.

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https://github.com/jaythealpha/jay/tree/claude/website-analysis-implementation-8rolis)

**대시보드로 배포**
1. [vercel.com/new](https://vercel.com/new) 접속 → GitHub 저장소 `jaythealpha/jay` 임포트
2. **Branch** 를 `claude/website-analysis-implementation-8rolis` 로 선택
3. Framework Preset: **Other** (설정 불필요 — `vercel.json` 이 자동 인식됨)
4. **Deploy** → `https://<프로젝트명>.vercel.app` 에서 루트에 QR 스튜디오가 열립니다.

**CLI로 배포**
```bash
npm i -g vercel
vercel            # 최초: 로그인 + 프로젝트 연결
vercel --prod     # 프로덕션 배포
```

`vercel.json`:
```json
{
  "cleanUrls": true,
  "rewrites": [{ "source": "/", "destination": "/qr-studio.html" }]
}
```

### GitHub Pages
저장소는 기본 브랜치 push 시 `gh-pages` 로 자동 발행됩니다. 이 브랜치가 병합되면
`https://jaythealpha.github.io/jay/qr-studio.html` 로 접속할 수 있습니다.

### 직접 열기 / 자체 호스팅
`qr-studio.html` 단일 파일만 있으면 됩니다. 파일을 더블클릭해 브라우저로 열거나
(`file://`), 정적 파일 서버(`python -m http.server`) 에 올려도 동일하게 동작합니다.

---

*QR Code는 DENSO WAVE의 등록상표입니다. 인코더: qrcode-generator (MIT, © Kazuhiko Arase).*
