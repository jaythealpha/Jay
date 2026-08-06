# MVP Scope & Milestones

## Milestone 0 — Foundation ✅ (현재, 완료)

실행 가능하고 테스트 가능한 프로젝트 기반.

구현됨:

- 모노레포 (npm workspaces) + Docker Compose (PostgreSQL 16, Redis 7)
- Prisma 스키마·마이그레이션 (User, Coupon, CouponAsset, CouponEvent)
- NestJS API: `GET /health`, `GET /v1/coupons` (실 DB, 유효기간 빠른 순),
  공통 오류 envelope, 환경변수 검증, 요청 로깅 + 민감정보 마스킹, Swagger
- Flutter 앱: Foundation 홈(실 API health 표시), 쿠폰함 목록(실 API 조회),
  로딩/성공/오류 상태, 오프라인 캐시 폴백(SharedPreferences 스냅샷)
- Next.js 운영자 콘솔 최소 화면 (API 상태 표시)
- 도메인 패키지: 상태 전환, 만료 계산, 정렬, 파서(날짜·금액·브랜드),
  신뢰도 정책, 바코드 해시·마스킹, 알림 정책 — 전부 단위 테스트 포함
- GitHub Actions CI (TypeScript + Flutter)

미구현(의도적): 인증, OCR, 이미지 업로드, 푸시 발송, 쿠폰 CRUD 쓰기 API.

## Milestone 1 — Coupon Capture Lab ✅ (완료)

구현됨:

- 이미지 업로드 API (`POST /v1/coupons`, multipart, jpeg/png/webp, 10MB 제한)
- S3 호환 private 스토리지 (MinIO dev + 로컬 파일시스템 폴백), 300초 signed URL
- 비동기 파이프라인: 업로드 → BullMQ Queue → Recognition Worker(동일 프로세스)
  → 결과 저장 → 상태 전환(PROCESSING → ACTIVE/NEEDS_REVIEW/INVALID) → 앱 조회
- 바코드/QR 감지: ZXing(WASM) 실제 판독, AES-256-GCM 암호화 저장 + SHA-256 해시
- OCR: `OcrProvider` 인터페이스 + 결정적 Mock Provider (실제 OCR 엔진은 미연동,
  기기 내 OCR이 M2 이후 1차 경로)
- 필드 추출: 브랜드/상품명/유효기간/금액 + 필드별 신뢰도, 중복 의심 감지
- 검토 API: `GET /v1/coupons/:id`, `PATCH /v1/coupons/:id`, `POST /:id/confirm`
- 모바일: 등록 화면(카메라/사진첩), 분석 대기 폴링, 인식 결과 확인 화면
  (신뢰도 배지, 필드 수정, 저장·확정, 중복/바코드/실패 안내)
- 테스트 데이터셋 16종 + 정확도 측정 (`npm run accuracy`) + 회귀 테스트

미구현(의도적): 실제 OCR 엔진(테서랙트/클라우드), 기기 내 OCR(ML Kit),
공유 시트 등록, perceptual hash 중복 감지.

## Milestone 2 — Coupon Wallet MVP ✅ (완료)

구현됨:

- 이메일+비밀번호 인증(scrypt 해시, JWT) — 모든 쿠폰 API가 사용자 스코프로
  보호되고, 타인 쿠폰은 404 (존재 여부 비노출)
- 쿠폰함: 상태 필터 6종, 브랜드/상품/카테고리 검색, 정렬 4종(서버 측 +
  오프라인 시 캐시에 동일 규칙 로컬 적용)
- 상세 화면: 정보 전체, 원본 이미지, 사용 완료/취소, 보관/해제, 삭제
- 바코드 표시: 전용 열람 API(감사 이벤트 BARCODE_VIEWED, 마스킹 로그),
  barcode_widget 렌더(Code128/QR 등 11종 매핑), 기기 보안 저장소 캐시로
  오프라인 표시, 고대비 확대 UI
- 사용 완료/복구: 도메인 전환 규칙 준수(만료된 쿠폰 복구 → EXPIRED)
- 오프라인 사용 완료 임시 처리: 실패한 redeem을 로컬 큐에 저장, 다음 통신 시
  자동 재생(서버 거부 시 서버 상태 우선)
- 모바일 로그인/회원가입 화면, 인증 라우팅 가드, 401 자동 로그아웃

미구현(의도적): refresh token/토큰 갱신, Drift 구조화 로컬 DB(ADR-0003 —
스냅샷 캐시가 M2 요구를 충족, 양방향 동기화가 필요한 시점에 도입),
양방향 필드 동기화·충돌 해소(현재는 redeem 재생 큐만).

## Milestone 3 — Never Expire ✅ (완료)

구현됨:

- **만료 상태 자동 전환**: BullMQ 반복 작업(10분 주기 + 부팅 시 1회)이
  ACTIVE⇄EXPIRING_SOON→EXPIRED를 도메인 규칙으로 재계산 (EXPIRED 자동 부활
  없음, STATUS_CHANGED 이벤트 기록)
- **알림 예약**: 30/7/3/당일 09:00 터치포인트를 `ScheduledNotification`으로
  저장. 등록 시 지난 시점은 제외(5일 남은 쿠폰 → 3일+당일만). 인식 완료·
  확정·복구·보관 해제 시 예약, 사용 완료·보관·삭제 시 취소, 유효기간 변경 시
  재예약 — 전부 `@amc/notification-policy` 순수 로직 기반
- **알림 발송**: 1분 주기 디스패처가 due 알림을 **인앱 피드**로 전달
  (`GET /v1/notifications`). 메시지는 브랜드+상품/금액+남은 기간 규칙 강제.
  발송 시점에 REDEEMED/ARCHIVED면 취소(이중 방어)
- **딥링크·액션**: 피드 항목 → 쿠폰 보기(상세 이동) / 사용 완료 / 하루 뒤
  다시 알림(snooze, +24h 재예약)
- **홈 화면 만료 우선 추천** (`GET /v1/home`): 곧 만료돼요(3일) → 이번 주
  사용하세요(7일+고가치) → 최근 등록 5개 → 내 쿠폰 요약(상태별 카운트+총 가치)

미구현(의도적): **실제 푸시 발송(FCM/APNs)** — 동일한 ScheduledNotification
행을 푸시 채널이 재사용하도록 설계됨. 기기 푸시 토큰 등록·발송 연동은 별도
마일스톤.

## Milestone 4+

이전 마일스톤 완료 전 거래 기능을 구현하지 않는다.
