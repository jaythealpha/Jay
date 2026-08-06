# All Mighty Coupon

> **Never Lose a Coupon Again.**

쿠폰을 빠르게 등록하고, 정확히 인식하고, 쉽게 찾고, 유효기간 전에 실제로
사용하게 돕는 개인 쿠폰 지갑입니다. 현재 **Milestone 0 (실행 가능한 기반)**
단계이며, 거래소·결제·판매 기능은 범위에 없습니다.

## 구성

| 앱/패키지     | 스택                                           | 상태                                      |
| ------------- | ---------------------------------------------- | ----------------------------------------- |
| `apps/api`    | NestJS 11 · Prisma 6 · PostgreSQL 16 · Redis 7 | Health + 쿠폰 목록 API 동작               |
| `apps/admin`  | Next.js 15 (App Router)                        | API 상태 표시 최소 화면                   |
| `apps/mobile` | Flutter 3.44 · Riverpod · GoRouter · Dio       | Health 확인 + 쿠폰함 목록 + 오프라인 캐시 |
| `packages/*`  | TypeScript strict                              | 도메인 로직 + 테스트                      |

## 사전 요구사항

- Node.js ≥ 20, npm
- Docker + Docker Compose
- Flutter SDK 3.44.x (모바일 앱)

## 빠른 시작

```bash
cd all-mighty-coupon

# 1. 인프라 (PostgreSQL 5432, Redis 6379)
docker compose up -d

# 2. 의존성
npm install

# 3. 환경변수 — .env.example을 복사해 .env 생성 (API는 apps/api/.env도 읽음)
cp .env.example .env
cp .env.example apps/api/.env

# 4. 데이터베이스
npm run db:generate   # Prisma Client 생성
npm run db:migrate    # 마이그레이션 적용 (prisma migrate dev)
npm run db:seed       # 데모 유저 + 샘플 쿠폰 5개

# 5. 실행
npm run dev:api       # http://localhost:3001 (Swagger: /docs)
npm run dev:admin     # http://localhost:3002
```

### 검증 명령

```bash
npm run lint          # eslint + prettier check
npm run test          # 패키지 빌드 → vitest(59) → API 단위(jest, 11)
npm run test:api:e2e  # 실제 DB/Redis 통합 테스트 4개 (compose 필요)
npm run build         # packages → api(tsc) → admin(next build)
npm run format        # prettier --write
```

### 모바일 앱

```bash
cd apps/mobile
flutter pub get
flutter analyze
flutter test          # 단위 + 위젯 테스트 17개

# 실행 (기기/에뮬레이터 필요)
flutter run                                                     # iOS 시뮬레이터/데스크톱
flutter run --dart-define=AMC_API_BASE_URL=http://10.0.2.2:3001 # Android 에뮬레이터

# 라이브 API 스모크 테스트 (스택 실행 중일 때, 기본 suite에서는 skip)
flutter test test/manual/api_smoke_test.dart --dart-define=API_SMOKE=true
```

## API 엔드포인트 (Milestone 0)

- `GET /health` — DB·Redis 연결 상태
- `GET /v1/coupons?status=&limit=` — 쿠폰 목록, **유효기간 빠른 순** (무기한은 뒤로)
- `GET /docs` — Swagger UI

오류는 공통 envelope로 반환됩니다:
`{ "error": { "code", "message", "requestId" } }`

## 알려진 제한 (Milestone 0)

- 인증 없음 — 쿠폰 API는 시드된 샘플 데이터 전용, 사용자 스코프는 Milestone 2
- OCR·바코드 인식·이미지 업로드 미구현 (Milestone 1) — 정책·파서·해시 로직과
  테스트만 존재
- 푸시 발송 미구현 — 알림 _정책_ 로직만 (`packages/notification-policy`)
- 모바일 실기기/에뮬레이터 UI 실행은 CI 환경 제약으로 미검증
  (analyze/test + 라이브 API 스모크 테스트로 검증)

자세한 내용: [docs/product/MVP_SCOPE.md](docs/product/MVP_SCOPE.md),
[docs/architecture/SYSTEM_OVERVIEW.md](docs/architecture/SYSTEM_OVERVIEW.md)
