# All Mighty Coupon

> **Never Lose a Coupon Again.**

쿠폰을 빠르게 등록하고, 정확히 인식하고, 쉽게 찾고, 유효기간 전에 실제로
사용하게 돕는 개인 쿠폰 지갑입니다. 현재 **Milestone 0 (실행 가능한 기반)**
단계이며, 거래소·결제·판매 기능은 범위에 없습니다.

## 구성

| 앱/패키지     | 스택                                                            | 상태                                                              |
| ------------- | --------------------------------------------------------------- | ----------------------------------------------------------------- |
| `apps/api`    | NestJS 11 · Prisma 6 · PostgreSQL 16 · Redis 7 · BullMQ · MinIO | Health, 쿠폰 목록/업로드/상세/수정/확정, 비동기 인식 파이프라인   |
| `apps/admin`  | Next.js 15 (App Router)                                         | API 상태 표시 최소 화면                                           |
| `apps/mobile` | Flutter 3.44 · Riverpod · GoRouter · Dio · image_picker         | 등록(카메라/사진첩) → 인식 결과 확인·수정 → 쿠폰함, 오프라인 캐시 |
| `packages/*`  | TypeScript strict                                               | 도메인 로직 + 파서 + 정확도 데이터셋 + 테스트                     |

## 사전 요구사항

- Node.js ≥ 20, npm
- Docker + Docker Compose
- Flutter SDK 3.44.x (모바일 앱)

## 빠른 시작

```bash
cd all-mighty-coupon

# 1. 인프라 (PostgreSQL 5432, Redis 6379, MinIO 9000/9001)
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
npm run test          # 패키지 빌드 → vitest(67) → API 단위(jest, 21)
npm run test:api:e2e  # 실제 DB/Redis/MinIO 통합 테스트 9개 (compose 필요)
npm run build         # packages → api(tsc) → admin(next build)
npm run accuracy      # 인식 파서 정확도 리포트 (16샘플 데이터셋)
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

## API 엔드포인트 (Milestone 0–1)

- `GET /health` — DB·Redis 연결 상태
- `GET /v1/coupons?status=&limit=` — 쿠폰 목록, **유효기간 빠른 순** (무기한은 뒤로)
- `POST /v1/coupons` — 이미지 업로드(multipart) → 비동기 인식 파이프라인
- `GET /v1/coupons/:id` — 상세 + 필드별 신뢰도 + 중복 의심 + signed URL 에셋
- `PATCH /v1/coupons/:id` — 인식 결과 수정 (Confirm, Do Not Type)
- `POST /v1/coupons/:id/confirm` — 확인 완료 (NEEDS_REVIEW → ACTIVE)
- `GET /docs` — Swagger UI

오류는 공통 envelope로 반환됩니다:
`{ "error": { "code", "message", "requestId" } }`

## 알려진 제한 (Milestone 1 기준)

- 인증 없음 — 모든 작업이 로컬 데모 사용자 스코프. 이 상태로 배포 금지.
  사용자 인증·스코프는 Milestone 2
- **실제 OCR 엔진 미연동** — `OcrProvider` 인터페이스 + 결정적 Mock만 존재
  (mock 결과에는 `[MOCK OCR SAMPLE]` 표시). 기기 내 OCR(ML Kit)·서버 OCR
  폴백은 이후 마일스톤. 바코드/QR 판독(ZXing)은 실제 동작
- 정확도 수치는 합성 OCR 텍스트 기준 파서 정확도 (실이미지 종단 정확도 아님)
- 푸시 발송 미구현 — 알림 _정책_ 로직만 (`packages/notification-policy`)
- 공유 시트(SHARE_EXTENSION) 등록 경로는 enum만 존재, 네이티브 연동 미구현
- 모바일 실기기/에뮬레이터 UI 실행(카메라 포함)은 CI 환경 제약으로 미검증
  (analyze/test + 라이브 API 스모크 테스트로 검증)

자세한 내용: [docs/product/MVP_SCOPE.md](docs/product/MVP_SCOPE.md),
[docs/architecture/SYSTEM_OVERVIEW.md](docs/architecture/SYSTEM_OVERVIEW.md)
