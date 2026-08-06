# All Mighty Coupon

> **Never Lose a Coupon Again.**

쿠폰을 빠르게 등록하고, 정확히 인식하고, 쉽게 찾고, 유효기간 전에 실제로
사용하게 돕는 개인 쿠폰 지갑입니다. **Milestone 0–3 완료** (기반 → 인식
파이프라인 → 지갑 MVP → 만료 알림). 거래소·결제·판매 기능은 범위에 없습니다.

## 구성

| 앱/패키지     | 스택                                                                  | 상태                                                                              |
| ------------- | --------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| `apps/api`    | NestJS 11 · Prisma 6 · PostgreSQL 16 · Redis 7 · BullMQ · MinIO · JWT | 인증 + 쿠폰 CRUD·검색·정렬 + 인식 파이프라인 + 사용 완료/복구 + 바코드 열람(감사) |
| `apps/admin`  | Next.js 15 (App Router)                                               | API 상태 표시 최소 화면                                                           |
| `apps/mobile` | Flutter 3.44 · Riverpod · GoRouter · Dio · secure storage             | 로그인 → 등록 → 검토 → 쿠폰함(필터·검색·정렬) → 상세 → 바코드, 오프라인 지원      |
| `packages/*`  | TypeScript strict                                                     | 도메인 로직 + 파서 + 정확도 데이터셋 + 테스트                                     |

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
npm run test          # 패키지 빌드 → vitest(67) → API 단위(jest, 24)
npm run test:api:e2e  # 실제 DB/Redis/MinIO 통합 테스트 24개 (compose 필요)
npm run build         # packages → api(tsc) → admin(next build)
npm run accuracy      # 인식 파서 정확도 리포트 (16샘플 데이터셋)
npm run format        # prettier --write
```

### 모바일 앱

```bash
cd apps/mobile
flutter pub get
flutter analyze
flutter test          # 단위 + 위젯 테스트 56개

# 실행 (기기/에뮬레이터 필요)
flutter run                                                     # iOS 시뮬레이터/데스크톱
flutter run --dart-define=AMC_API_BASE_URL=http://10.0.2.2:3001 # Android 에뮬레이터

# 라이브 API 스모크 테스트 (스택 실행 중일 때, 기본 suite에서는 skip)
flutter test test/manual/api_smoke_test.dart --dart-define=API_SMOKE=true
```

## API 엔드포인트 (Milestone 0–3)

- `POST /v1/auth/register` · `login` — 이메일+비밀번호 → JWT (이후 전부 Bearer 필수)
- `GET /health` — DB·Redis 연결 상태 (공개)
- `GET /v1/coupons?status=&q=&sort=&limit=` — 내 쿠폰 목록·검색·정렬 (**유효기간 빠른 순** 기본)
- `POST /v1/coupons` — 이미지 업로드(multipart) → 비동기 인식 파이프라인
- `GET /v1/coupons/:id` — 상세 + 필드별 신뢰도 + 중복 의심 + signed URL 에셋
- `PATCH /v1/coupons/:id` · `POST /:id/confirm` — 인식 결과 수정·확정
- `POST /v1/coupons/:id/redeem` · `restore` · `archive` · `unarchive`, `DELETE /:id`
- `GET /v1/coupons/:id/barcode` — 바코드 열람 (감사 이벤트 기록)
- `GET /v1/home` — 만료 우선 홈 (곧 만료/이번 주/최근/요약)
- `GET /v1/notifications` · `POST /:id/snooze` — 만료 알림 인앱 피드·연기
- `POST/DELETE /v1/devices` — 푸시 기기 토큰 등록/해제
- `GET /v1/admin/stats` — 운영자 통계 (x-admin-token, 기본 비활성)
- `GET /docs` — Swagger UI

개발용 데모 계정(시드): `demo@allmightycoupon.local` / `demo-password-1234`

오류는 공통 envelope로 반환됩니다:
`{ "error": { "code", "message", "requestId" } }`

## 알려진 제한 (Milestone 3 기준)

- 인증은 JWT 액세스 토큰 단일(7d) — refresh token·비밀번호 재설정·rate
  limiting 미구현. 프로덕션 배포 전 필수
- **기기 내 OCR(ML Kit) 실기기 미검증** — 기기 OCR 우선→서버 폴백 구조와
  서버 측 처리(provider='device')는 e2e 검증 완료, ML Kit 자체는 실기기
  필요. 서버 OCR은 여전히 Mock(`[MOCK OCR SAMPLE]` 표시). 바코드/QR
  판독(ZXing)은 실제 동작
- 정확도 수치는 합성 OCR 텍스트 기준 파서 정확도 (실이미지 종단 정확도 아님)
- **FCM 발송 미검증** — 발송 코드·토큰 등록·무효 토큰 정리까지 구현됐지만
  실제 Firebase 프로젝트 자격증명 없이는 Noop(인앱 피드 전용)으로 동작.
  모바일 firebase_messaging 연동(구글 설정 파일)도 미구현
- 오프라인 동기화는 redeem 재생 큐까지 — 필드 수정의 오프라인 큐잉·충돌
  해소는 미구현
- 공유 시트: Android intent-filter + 수신·자동 업로드 구현(실기기 미검증), **iOS 공유 확장 미구현**
- 바코드 화면의 기기 밝기 자동 상향은 미구현(고대비 UI만) — 실기기 검증 필요
- 모바일 실기기/에뮬레이터 UI 실행(카메라·보안 저장소 포함)은 CI 환경 제약으로
  미검증 (analyze/test + 라이브 API 스모크 테스트로 검증)

자세한 내용: [docs/product/MVP_SCOPE.md](docs/product/MVP_SCOPE.md),
[docs/architecture/SYSTEM_OVERVIEW.md](docs/architecture/SYSTEM_OVERVIEW.md)
