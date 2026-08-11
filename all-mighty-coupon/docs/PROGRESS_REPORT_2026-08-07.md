# All Mighty Coupon — 개발 진행 보고서

- 기준일: 2026-08-07
- 저장소: `jaythealpha/Jay` → `all-mighty-coupon/` (모노레포)
- 작업 브랜치: `claude/all-mighty-coupon-milestone-0-7lpz9s` (최신 커밋 `0f07317`)
- 제품 비전: **"Never Lose a Coupon Again."** — 개인 쿠폰 지갑 (등록 → 인식 → 보관 → 검색 → 사용 → 만료 방지)

## 1. 한눈에 보기

| 마일스톤 | 상태 | 핵심 |
|---|---|---|
| M0 Foundation | ✅ 완료 | 모노레포, Docker(PG/Redis), Prisma, Health/목록 API, Flutter 기반 화면, CI |
| M1 Capture Lab | ✅ 완료 | 이미지 업로드 → BullMQ 비동기 인식 파이프라인, ZXing 바코드 실판독, 필드 추출+신뢰도 |
| M2 Wallet MVP | ✅ 완료 | JWT 인증·사용자 스코프, 검색/필터/정렬, 상세/바코드 표시(감사), 사용완료/복구, 오프라인 |
| M3 Never Expire | ✅ 완료 | 만료 상태 자동 전환 스케줄러, 30/7/3/당일 알림 예약·발송(인앱 피드), 스누즈, 홈 추천 |
| 확장 a–c | ✅ 완료 | FCM 푸시 채널(코드 완성/자격증명 대기), 기기 OCR 우선, 공유 시트(Android), 운영자 콘솔 |
| M4 마켓 | ✅ 완료 | 판매 등록→익명 조회→구매→소유권 이전. **결제는 전부 Mock — 실제 돈 없음** |

테스트 (전부 실제 실행·통과):

- 패키지 vitest **73** · API 단위 jest **24** · API 통합(실 PG/Redis/MinIO) **33** · Flutter **61** (+라이브 스모크 2)
- lint(eslint+prettier) / TypeScript build / Next build / flutter analyze 전부 클린

## 2. 기술 스택·구조

```
all-mighty-coupon/
├── apps/api      NestJS 11 · Prisma 6 · PostgreSQL 16 · Redis 7(BullMQ) · MinIO(S3) · JWT
├── apps/admin    Next.js 15 — 운영자 대시보드 (정적 운영 토큰)
├── apps/mobile   Flutter 3.44 · Riverpod 3 · GoRouter · Dio · secure storage · ML Kit
└── packages/     shared-types · domain · coupon-parser · barcode-utils
                  · notification-policy · design-tokens  (순수 로직 + 테스트)
```

- Modular Monolith. 비즈니스 규칙은 전부 `packages/`의 순수 함수(상태 머신, 만료 계산, 알림 정책, 파서·신뢰도, 마켓 규칙) — API/앱은 소비만.
- 외부 서비스는 전부 인터페이스 경계: `OcrProvider`, `StorageService`(S3/로컬), `PushSender`(FCM/Noop), `PaymentProvider`(Mock), `DeviceOcr`, `TokenStore`.

## 3. 구현된 주요 흐름

**등록·인식**: 카메라/사진첩/공유 시트(Android) → 기기 OCR(ML Kit) 텍스트 동봉 → `POST /v1/coupons`(multipart) → BullMQ Job → 워커: sharp 정규화/썸네일(원본 불변) → ZXing 바코드/QR 판독 → 기기 OCR 우선·서버 OCR 폴백 → 브랜드/상품/유효기간/금액 추출 + 필드별 신뢰도(유효기간 <0.95 → NEEDS_REVIEW 강제) → 바코드 AES-256-GCM 암호화 + SHA-256 해시 중복 의심 → 상태 전환 → 앱 검토 화면(신뢰도 배지, 수정, 확정).

**지갑·사용**: 유효기간 빠른 순 기본 정렬, 상태 필터 6종/검색/정렬 4종(오프라인 시 캐시에 동일 규칙 로컬 적용). 상세 → 바코드 표시(전용 열람 API, BARCODE_VIEWED 감사, 기기 보안 저장소 캐시로 오프라인 표시). redeem/restore/archive/delete — 전부 도메인 상태 머신 경유(EXPIRED 자동 부활 금지). 오프라인 redeem은 로컬 큐 → 재접속 시 자동 동기화.

**만료 방지**: 10분 주기 상태 스윕(ACTIVE⇄EXPIRING_SOON→EXPIRED), 30/7/3/당일 09:00 알림 예약(지난 시점 제외·사용완료/보관/삭제 시 취소·유효기간 변경 시 재예약), 1분 주기 디스패처 → 인앱 피드 + 푸시 채널. 알림 액션: 쿠폰 보기(딥링크)/사용 완료/하루 뒤 다시 알림. 홈: 곧 만료돼요(3일) → 이번 주 사용하세요(7일+고가치) → 최근 등록 → 요약(카운트+총 가치).

**마켓(M4, Mock 결제)**: 판매 자격은 `@amc/domain.canListCoupon`(사용 가능+검토 완료+바코드+유효기간 1일+, 가격 100원~1,000만원 정수, 수수료 5% 최소 100원). 판매 중 지갑 액션 잠금. 조회는 판매자 완전 익명·바코드 무노출·만료 임박순. 구매는 Mock 승인 → 트랜잭션 소유권 이전(동시 구매 1명만 성공) → 알림 새 소유자로 재예약. paymentRef는 `MOCK-` 접두, UI에 "실제 돈이 오가지 않음" 상시 배너.

## 4. API 요약 (Swagger: `/docs`)

- 인증: `POST /v1/auth/register|login`, `GET /v1/auth/me` — 이외 전부 Bearer 필수
- 쿠폰: `GET/POST /v1/coupons`, `GET/PATCH /v1/coupons/:id`, `POST /:id/confirm|redeem|restore|archive|unarchive`, `DELETE /:id`, `GET /:id/barcode`
- 홈/알림: `GET /v1/home`, `GET /v1/notifications`, `POST /v1/notifications/:id/snooze`
- 푸시 기기: `POST/DELETE /v1/devices`
- 마켓: `GET/POST /v1/market/listings`, `DELETE /v1/market/listings/:id`, `POST /:id/purchase`, `GET /v1/market/orders`
- 운영자: `GET /v1/admin/stats` (x-admin-token, 기본 비활성)
- 공통 오류 envelope `{error:{code,message,requestId}}` + `x-request-id`

## 5. 데이터 모델 (Prisma, 마이그레이션 6개 적용)

User(+passwordHash) · Coupon(상태 8종, faceValueMinor 정수 KRW, encryptedBarcode/barcodeHash, recognitionData) · CouponAsset(ORIGINAL/NORMALIZED/THUMBNAIL) · CouponEvent(append-only, 거래 이벤트 포함 18종) · ScheduledNotification(PENDING/SENT/CANCELLED) · PushDevice · Listing(LISTED/SOLD/CANCELLED) · Order(MOCK paymentRef). 시간은 전부 UTC, 금액은 정수만.

## 6. 보안·개인정보 (구현·테스트로 강제)

- 바코드 원문: AES-256-GCM 암호화 저장, 로그/이벤트/목록·마켓 응답 무노출(마스킹 값만), 열람은 소유자 전용 API + 감사 이벤트 — e2e가 직렬화 검사로 강제
- 로그 마스킹(barcode/token/password/email 패턴), 요청 로깅은 메서드/경로/상태/latency/requestId만
- 토큰·오프라인 바코드는 플랫폼 보안 저장소만, 푸시 토큰 값 무기록, 판매자 익명, 계정 존재 여부 비노출(로그인 실패 단일 메시지, 타인 쿠폰 404)
- `.env` 미커밋(.env.example만), 운영자 API는 사용자 JWT와 분리된 정적 토큰(기본 비활성)

## 7. 실행 방법 (로컬)

```bash
cd all-mighty-coupon
docker compose up -d                     # PG 5432 / Redis 6379 / MinIO 9000
npm install && cp .env.example .env && cp .env.example apps/api/.env
#  ↳ .env에서 JWT_SECRET·BARCODE_ENCRYPTION_KEY를 openssl rand -hex 32 값으로 교체
npm run db:generate && npm run db:migrate && npm run db:seed
npm run dev:api                          # http://localhost:3001 (/docs)
npm run dev:admin                        # http://localhost:3002
# 모바일: cd apps/mobile && flutter pub get && flutter run
# 데모 계정: demo@allmightycoupon.local / demo-password-1234
# 검증: npm run lint · npm run test · npm run test:api:e2e · npm run build · npm run accuracy
```

## 8. 미구현·미검증 (정직하게)

| 항목 | 상태 | 비고 |
|---|---|---|
| 실제 PG 결제/에스크로/정산/환불/분쟁 | 미구현 | PaymentProvider 경계 뒤에 연동. 외부 서비스 가입 필요 — 별도 승인 사항 |
| FCM 실발송 | 코드 완성·미검증 | `FIREBASE_SERVICE_ACCOUNT_JSON` 필요. 모바일 firebase_messaging도 구글 설정 파일 필요 |
| 서버 OCR 실엔진 | 미연동 | Mock Provider만(`[MOCK OCR SAMPLE]` 표시). 기기 OCR(ML Kit)이 1차 경로 |
| ML Kit·카메라·보안 저장소 실기기 동작 | 미검증 | CI에 에뮬레이터 없음 (analyze/test/라이브 API 스모크로 대체 검증) |
| iOS 공유 확장 | 미구현 | Xcode 네이티브 타깃 필요 (Android는 구현) |
| refresh token·비밀번호 재설정·rate limiting | 미구현 | 프로덕션 배포 전 필수 |
| 인식 정확도 수치(100%) | 주의 | 합성 OCR 텍스트 16종 기준 파서 정확도 — 실이미지 종단 정확도 아님 |

## 9. 문서 위치

`all-mighty-coupon/README.md`(실행), `AGENTS.md`(작업 규칙), `docs/product/`(비전·범위·플로우·지표), `docs/architecture/`(시스템·데이터·보안·오프라인·인식), `docs/adr/`(ADR 5종), `docs/qa/TEST_PLAN.md`, CI: 저장소 루트 `.github/workflows/all-mighty-coupon-ci.yml`.

## 10. 권장 다음 단계

1) Firebase 프로젝트 생성 후 자격증명 주입 → FCM 실발송 검증
2) 실기기에서 ML Kit OCR·카메라·공유 시트·바코드 화면 QA
3) 실 PG 선정·승인 → PaymentProvider 실구현 + 에스크로/정산 설계
4) refresh token·rate limiting 등 프로덕션 하드닝
