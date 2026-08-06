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

## Milestone 1 — Coupon Capture Lab (다음)

이미지 업로드, 바코드 감지, OCR(기기 내 우선, 인터페이스 뒤 서버 폴백),
필드 추출, 신뢰도 표시, 사용자 수정, 테스트 데이터셋, 인식 정확도 측정.
비동기 파이프라인: 업로드 → Job 생성 → BullMQ Queue → Recognition Worker →
결과 저장 → 상태 업데이트 → 앱 조회.

## Milestone 2 — Coupon Wallet MVP

로그인, 쿠폰 저장, 쿠폰함(필터·정렬·검색), 상세, 바코드 표시, 사용 완료/복구,
Drift 로컬 DB, 서버 동기화.

## Milestone 3 — Never Expire

만료 상태 자동 전환, 30/7/3/당일 알림 발송, 딥링크, 알림 연기,
사용 완료 시 알림 취소, 홈 만료 우선 추천.

## Milestone 4+

이전 마일스톤 완료 전 거래 기능을 구현하지 않는다.
