# AGENTS.md — All Mighty Coupon

AI 에이전트와 새 기여자를 위한 작업 가이드. 제품 비전은 단 하나다:

> **"Never Lose a Coupon Again."**

## 제품 판단 기준

모든 기능은 네 가지 질문으로 판단한다.

1. 사용자가 쿠폰을 더 빨리 등록할 수 있는가? (Three-Second Capture)
2. 시스템이 쿠폰 정보를 더 정확하게 이해하는가? (Confirm, Do Not Type)
3. 사용자가 필요한 쿠폰을 더 쉽게 찾을 수 있는가? (Expiration First)
4. 사용자가 유효기간 전에 실제로 행동하게 하는가? (Trust Over Automation)

## 저장소 구조

```
all-mighty-coupon/
├── apps/
│   ├── api/        NestJS API (TypeScript strict, Prisma, PostgreSQL, Redis)
│   ├── admin/      Next.js 운영자 콘솔 (최소 기반)
│   └── mobile/     Flutter 앱 (Riverpod, GoRouter, Dio, feature-first)
├── packages/
│   ├── shared-types/         API 계약 타입 (DTO, enum, 에러 envelope)
│   ├── domain/               쿠폰 상태 전환·만료 계산·정렬 (순수 로직)
│   ├── coupon-parser/        날짜·금액·브랜드 추출 + 신뢰도 정책
│   ├── barcode-utils/        바코드 정규화·해시·마스킹
│   ├── notification-policy/  만료 알림 정책 (순수 로직)
│   └── design-tokens/        색상·간격·타이포 토큰
├── docs/           product / architecture / adr / qa / operations
└── infrastructure/ docker, migrations 안내
```

CI 워크플로우는 **저장소 루트** `.github/workflows/all-mighty-coupon-ci.yml`에 있다
(모노레포가 기존 저장소의 하위 디렉터리이기 때문).

## 실행 명령 (모두 all-mighty-coupon/ 기준)

```bash
docker compose up -d      # PostgreSQL + Redis
npm install
npm run db:generate       # prisma generate
npm run db:migrate        # prisma migrate dev
npm run db:seed           # 데모 유저 + 샘플 쿠폰
npm run dev:api           # API (포트 3001, Swagger는 /docs)
npm run dev:admin         # 운영자 웹 (포트 3002)
npm run lint              # eslint + prettier
npm run test              # 패키지 빌드 → vitest → API jest
npm run test:api:e2e      # 실제 DB/Redis 대상 통합 테스트
npm run build             # packages → api → admin

cd apps/mobile
flutter pub get && flutter analyze && flutter test
flutter run --dart-define=AMC_API_BASE_URL=http://10.0.2.2:3001  # Android 에뮬레이터
```

## 절대 규칙

- **바코드 원문·쿠폰 번호·토큰을 로그, 분석 이벤트, API 응답에 노출하지 않는다.**
  중복 검사는 항상 `@amc/barcode-utils`의 해시로만 한다.
- 금액은 정수(`faceValueMinor`, KRW 원 단위)로만 저장한다. 부동소수점 금지.
- 서버 저장 시간은 전부 UTC. 사용자 표시 시점에만 타임존 변환.
- 인식하지 못한 값은 null 유지. 임의 문자열·현재 날짜로 채우지 않는다.
- 유효기간 신뢰도 0.95 미만이면 반드시 사용자 확인(`requiresReview`).
- `EXPIRED`를 시스템이 임의로 `ACTIVE`로 되돌리지 않는다.
  상태 전환은 `@amc/domain`의 `transition()`/`canTransition()`만 사용.
- `.env`는 커밋 금지, `.env.example`만 커밋.
- 비즈니스 로직을 UI 위젯/컨트롤러에 쓰지 않는다. 순수 로직은 packages/로.
- Mock/샘플 데이터는 `recognitionData.sampleData=true`처럼 명시적으로 표시.
- 실행하지 않은 명령을 실행했다고 보고하지 않는다.

## 현재 단계

Milestone 0 (기반) · 1 (Capture Lab) · 2 (Wallet MVP) · 3 (Never Expire) 완료.
남은 주요 갭: 실제 푸시 발송(FCM/APNs), 실제 OCR 엔진(기기 내 ML Kit 우선),
공유 시트 등록, 운영자(Admin) 기능, refresh token. 거래·결제·에스크로 기능은
사용자 승인 전 구현하지 않는다 (Milestone 4 이전 금지 원칙 유지).

개발용 데모 계정(시드): demo@allmightycoupon.local / demo-password-1234.
쿠폰 API는 전부 JWT 필수 — 새 엔드포인트는 `@Public()` 없이는 기본 보호됨.

## 승인 없이 하지 말 것

Git push(지정된 작업 브랜치 제외)·PR 생성·merge·배포·프로덕션 변경·유료 서비스
결제·실제 이메일/푸시 발송·기존 파일 삭제·기존 저장소 구조의 대규모 변경.
