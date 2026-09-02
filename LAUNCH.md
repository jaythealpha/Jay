# Aesthetic QR Studio — 배포 & 수익화 런북 (Launch Runbook)

> 목적: 앱을 공개하고 수익화하기 위한 실행 순서를 단계별로 정리한 문서입니다.
> 전략 근거는 시장조사(2026)에 기반합니다 — 요약은 §0.

---

## 0. 한눈에 보는 전략

- **애드센스는 1순위가 아님.** 2026 애드센스는 "콘텐츠 사이트"(원본 글 15~25개, About/Privacy/Contact)를 요구하고, QR 툴은 세션당 페이지뷰가 적어 RPM($2~8)이 낮음 → 승인·수익 모두 비효율.
- **지금 앱으로 가장 효율적인 수익화 = 원타임 Pro 언락(이미 구현됨)** 을 **MoR(결제대행)** 로 판매. 사업자등록·자체 서버 없이 시작 가능.
- 확장은 검증 후: (A) SEO 콘텐츠+제휴, (B) 동적 QR+분석 구독(백엔드 필요, 천장 높음).

권장 실행 순서: **Phase 0(도메인·법무·SEO) → Phase 1(원타임 Pro 판매) → Phase 2(검증 후 확장)**.

---

## Phase 0 — 공개 준비 (완료된 코드 + 남은 수동 작업)

### ✅ 코드로 완료된 것 (빌드 2026.09.03-c)
- SEO: Open Graph·Twitter 카드·canonical·JSON-LD(WebApplication)·theme-color·keywords.
- 법무/신뢰 페이지: 푸터의 **소개·개인정보처리방침·이용약관·문의** 모달(4개 언어 라벨).
- `robots.txt`, `sitemap.xml`(리포 루트).

### ⏳ 배포 전 수동 교체 (필수)
1. **연락 이메일** — `qr-studio.html`의 `CONTACT_EMAIL`(약 5300행)을 실제 이메일로 교체. (개인 이메일 노출이 부담되면 별도 문의용 주소 사용 권장.)
2. **도메인 교체** — 커스텀 도메인을 붙이면 `<head>`의 `canonical`/`og:url`/`og:image`와 `robots.txt`/`sitemap.xml`의 `jay-inky.vercel.app`을 새 도메인으로 일괄 치환.

### 🌐 커스텀 도메인 연결 (Vercel)
1. 도메인 구입(예: Namecheap/가비아/Cloudflare Registrar). `.studio`/`.app`/`.co` 등.
2. Vercel 프로젝트 → **Settings → Domains → Add** → 도메인 입력.
3. Vercel이 안내하는 DNS 레코드(A `76.76.21.21` 또는 CNAME `cname.vercel-dns.com`)를 도메인 등록기관 DNS에 추가.
4. 전파 후 HTTPS 자동 발급. 그다음 위 §"도메인 교체" 문자열 치환 → 재배포.
5. **배포 이슈 확인(중요):** Vercel **Production Branch = `claude/website-analysis-implementation-8rolis`** 인지 확인. 아니면 최신본이 라이브에 안 뜸(HANDOFF.md §1 참고).

> 도메인은 신뢰·브랜드·SEO·결제 링크에 유리하므로 **연결 권장**. 단, "애드센스 목적"으로는 권장하지 않음.

---

## Phase 1 — 원타임 Pro 판매 (실매출 시작, 백엔드 불필요)

앱에는 이미 Pro 언락 시스템이 있습니다(`PRO` 객체, 라이선스 키 검증, 게이팅, localStorage 유지). 결제만 연결하면 됩니다.

### 1) 결제대행(MoR) 선택
| 서비스 | 수수료(2026) | 특징 |
| --- | --- | --- |
| **Polar** (추천) | ~4% | 개발자 친화, 라이선스 키 발급, MoR가 부가세 처리 |
| Lemon Squeezy | 5% + $0.50 | SaaS/디지털상품, Stripe 인수됨 |
| Gumroad | 10% | 아시아 접근성↑, 수수료 높음 |

> 셋 다 **Merchant of Record** — 카드결제·해외 부가세·라이선스 발급을 대행하므로 사업자등록 없이 시작 가능. 매출 커지면 저수수료로 이전.

### 2) 상품 만들기 (예: Polar)
1. 계정 생성 → **Products → New** → "One-time" 상품 생성.
2. 이름: "Aesthetic QR Studio — Pro (평생 이용)", 가격 **₩7,900~12,900 (약 $6~9)**.
3. **License Keys** 기능 켜기(구매 시 키 자동 발급·이메일 발송).
4. 체크아웃 링크(Checkout URL)와 라이선스 검증 API 정보 확보.

### 3) 앱에 연결 (`qr-studio.html`의 `PRO` 객체, 약 5389행)
```js
var PRO = {
  active:false,
  price:"₩9,900",                    // ← 상품 가격과 일치
  checkoutUrl:"https://…/checkout",  // ← MoR 체크아웃 링크
  validateUrl:"https://…/validate",  // ← 라이선스 검증 API (POST {license_key})
  gate:{ hiresExport:true }          // ← 유료로 잠글 기능
};
```
- `checkoutUrl`만 채워도 "구매" 버튼이 결제창을 엽니다.
- `validateUrl`이 비어 있으면 개발용 오프라인 키(`QRPRO-XXXX-XXXX` 형식)로 언락 플로우를 테스트할 수 있습니다.
- `validateUrl`은 라이선스 키를 검증하는 엔드포인트(직접 만든 서버리스 함수 또는 MoR API 프록시). 응답이 유효하면 언락.

### 4) 유료 게이팅 범위 정하기 (`PRO.gate`)
현재: 고해상도 내보내기(2048/4096)만 Pro. 추가 후보(한 줄로 확장):
- `hiresExport:true` — 인쇄용 고해상도 (적용됨)
- `bulk:true` — 대량 QR 시트
- `cleanAnim:true` — 워터마크 없는 애니메이션(WebM)
- `aiArt:true` — AI 아트 QR (유일하게 실제 서버비용 발생 → 서버에서 강제 권장)

> 원칙: **무료로 강력하게(디자인·24유형·프레임·로고) → "인쇄·대량·상업용"만 잠금** → 바이럴 + 전환.

### 5) 정직한 한계
- 정적 앱이라 클라이언트 라이선스 검증은 우회 가능(저가 툴 업계 표준). 진짜 비용 드는 AI 아트만 서버에서 강제하면 충분.

---

## Phase 2 — 확장 (Phase 1 매출 검증 후 택1)

### A. 콘텐츠 + 제휴/애드센스 (패시브, 느림)
- "카페 WiFi QR 만드는 법", "식당 메뉴판 QR", "명함 QR" 등 use-case 가이드 15~25개 작성 → 롱테일 유입.
- 그 후 애드센스/제휴. **이 단계까지 가야 애드센스가 의미 있음.**

### B. 동적 QR + 스캔 분석 구독 (고위험·고수익)
- 백엔드 구축: 단축URL·리다이렉트 서버·스캔 이벤트 DB·대시보드·로그인.
- 경쟁사 과금대($5~250/mo)에 진입. 차별점 = **디자인 품질**(우리 강점) + 가격.
- 실제 엔지니어링·운영비 발생 → **Phase 1 유료 전환이 검증되면** 착수.

---

## 출시 체크리스트

- [ ] `CONTACT_EMAIL` 실제 값 교체
- [ ] 커스텀 도메인 연결 + canonical/og/robots/sitemap 도메인 치환
- [ ] Vercel Production Branch 확인(라이브 최신본 반영)
- [ ] OG 이미지(`assets/cover.png`) 확인(소셜 공유 미리보기)
- [ ] MoR 상품 생성 + `PRO.checkoutUrl`/`validateUrl`/`price` 입력
- [ ] Pro 게이팅 범위 확정(`PRO.gate`)
- [ ] 실제 기기로 대표 QR 스캔 테스트
- [ ] (선택) Google Search Console에 사이트 등록 + sitemap 제출

---

*근거 데이터: QR SaaS 가격(QR Tiger $7 / EZQR $5 / Bitly $10 / Flowcode $25~ / Uniqode $49~), 애드센스 2026 콘텐츠 요건, MoR 수수료(Polar 4% / Lemon Squeezy 5% / Gumroad 10%). 상세 출처는 대화 이력 참고.*
