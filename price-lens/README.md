# 🏷️ 프라이스 렌즈 (Price Lens)

옷 라벨(가격표·품질표시 태그 등)을 카메라로 찍으면 상품을 인식하고,
**지금 인터넷 판매가를 최저가 기준 오름차순**으로 비교해 판매처 링크와 함께 보여주며,
**최저가 기준 최근 1년 가격 추이**를 차트로 정리해 주는 웹 앱입니다.

> 이 프로젝트는 저장소의 게임과 별개인 **독립 앱**입니다. `price-lens/` 폴더만으로 완전히 동작합니다.

## ✨ 특징

- 📷 **라벨 스캔** — 카메라 실시간 촬영 또는 갤러리 사진 불러오기 (모바일 후면 카메라 우선, 촬영 가이드 프레임)
- 📊 **실제 바코드 디코딩** — 브라우저 내장 `BarcodeDetector` API로 EAN/UPC/CODE128 등을 그 자리에서 실제 해독.
  AI는 바코드 막대무늬를 눈으로 "판독"하지 않고(할루시네이션의 주 원인), 이렇게 디코딩된 진짜 숫자만 신뢰해 검색합니다
- 🤖 **AI 상품 인식** — Claude 비전 모델이 라벨에서 브랜드·상품명·품번·사이즈·정가를 읽어냄. 브랜드 텍스트가
  안 보이면 지어내지 않고 확신도를 낮춰 솔직히 표시 (식별 근거를 결과 화면에 함께 공개)
- 🌐 **실시간 가격 검색** — Claude **웹 검색 도구**로 네이버쇼핑·다나와·쿠팡·G마켓·11번가·무신사·KREAM 등의
  현재 판매가를 조사, **최저가 오름차순** 목록 + 판매처 **바로가기 링크** 제공
- 📈 **1년 가격 추이** — 최저가 기준 월별 추이를 SVG 라인 차트로 표시 (호버 툴팁, 최저/최고/현재 직접 라벨,
  1년 최저·최고·변동률 요약, 표 보기 지원). 검색 결과 기반 **AI 추정치**임을 명시
- 🔗 **바로 검색** — 인식된 검색어로 네이버쇼핑/다나와/쿠팡/구글쇼핑/무신사/KREAM/번개장터 검색 결과로 즉시 이동
- ⌨️ **텍스트 검색** — 사진 없이 상품명/품번 입력만으로도 가격 조회 가능, 결과 화면에서 검색어를 다듬어 **다시 조회**
- 🏷️ **상태 필터** — 가격 목록을 전체/새상품/중고·리퍼로 필터링 (필터 기준으로 순위·최저가 배지 재계산)
- 🗂️ **세션 기록** — 스캔마다 하나의 세션으로 저장, 사이드 드로어에서 다시 열람/삭제
- 🔒 **프라이버시** — API 키와 스캔 기록은 **브라우저(localStorage)에만** 저장. 별도 백엔드/서버 없음
- 🧪 **데모 모드** — API 키가 없어도 샘플 가격 리포트로 UI 체험 가능
- 📤 **공유** — 최저가 TOP3와 링크를 시스템 공유 시트 또는 클립보드로 내보내기
- 빌드/설치 불필요 — 순수 HTML/CSS/JS 단일 파일

## 🚀 실행하기

브라우저에서 `price-lens/index.html`을 열기만 하면 됩니다. 단, **카메라(getUserMedia)는 보안 컨텍스트**가
필요하므로 로컬 서버(또는 HTTPS)에서 실행하는 것을 권장합니다.

```bash
# 저장소 루트에서
python3 -m http.server 8000
# 브라우저에서 http://localhost:8000/price-lens/ 접속
```

GitHub Pages로 배포된 경우: `https://<user>.github.io/<repo>/price-lens/`

## ▲ Vercel로 배포하기

정적 사이트라 빌드 없이 바로 배포됩니다. `price-lens/vercel.json`에 보안 헤더(카메라 권한 포함)가 설정되어 있습니다.

**방법 A — Vercel Git 연동 (권장, 클릭만으로 끝)**

1. [vercel.com/new](https://vercel.com/new) → **Import** → GitHub 저장소 `jaythealpha/Jay` 선택
2. **Root Directory**를 `price-lens`로 지정 (Framework Preset: Other, 빌드 명령 없음)
3. **Deploy** — 이후 저장소에 push할 때마다 자동으로 재배포됩니다
4. 배포 주소 예: `https://<project>.vercel.app/` (HTTPS라 카메라 촬영도 바로 동작)

**방법 B — GitHub Actions 수동 배포**

`.github/workflows/vercel-price-lens.yml` 워크플로가 포함되어 있습니다.

1. [vercel.com/account/tokens](https://vercel.com/account/tokens)에서 토큰 발급
2. 저장소 **Settings → Secrets and variables → Actions**에 아래 3개 시크릿 등록
   - `VERCEL_TOKEN` — 발급한 토큰
   - `VERCEL_ORG_ID` — Vercel 팀 ID (`team_...`)
   - `VERCEL_PROJECT_ID` — Vercel 프로젝트 ID (`prj_...`)
3. GitHub **Actions 탭 → Deploy Price Lens to Vercel → Run workflow**로 실행 (production/preview 선택 가능)

시크릿이 없으면 워크플로는 배포를 건너뛰기만 하고 실패하지 않습니다.

## 🔑 실제 인식·가격 검색 켜기 (선택)

1. [console.anthropic.com](https://console.anthropic.com/settings/keys) 에서 API 키 발급
2. 앱 우상단 **⚙️ 설정** → API 키 입력 → 저장
3. 라벨을 촬영하면 실제 인식 + 웹 검색 가격 조회가 동작합니다 (검색 포함이라 30초~1분 소요)

> 키는 브라우저에서 Anthropic API로 **직접** 호출됩니다(`anthropic-dangerous-direct-browser-access`).
> 공유 기기에서는 사용을 피하고, 개인용 키만 등록하세요. 웹 검색 도구는 API 요금 외 검색 비용이 추가됩니다.

## 🧱 구조

```
price-lens/
├── index.html   # 앱 전체 (마크업 + 스타일 + 로직, 외부 의존성 없음)
└── README.md
```

## ⚠️ 유의

- 가격·링크는 조회 시점의 웹 검색 결과를 AI가 정리한 것으로, 옵션·쿠폰·재고에 따라 실제와 다를 수 있습니다.
- 바코드 자동 디코딩은 브라우저가 `BarcodeDetector` API를 지원해야 동작합니다 (Chrome/Android는 대부분 지원,
  구형 브라우저는 미지원). 디코딩이 안 되면 라벨의 인쇄 텍스트(브랜드·품번)만으로 식별합니다 — 이 경우 결과
  화면 상단의 "🔍 식별 근거"와 확신도 배지를 확인해 실제 상품과 맞는지 검증하세요.
- **1년 가격 추이는 추정치**입니다. 한국 쇼핑몰의 과거 가격 원본 데이터는 공개 API로 제공되지 않아,
  검색에서 발견한 과거 가격 단서(세일 소식, 시세 언급 등)와 카테고리의 일반적 할인 패턴을 근거로 만들어집니다.
- 구매 전 반드시 판매처에서 최종 가격을 확인하세요.
