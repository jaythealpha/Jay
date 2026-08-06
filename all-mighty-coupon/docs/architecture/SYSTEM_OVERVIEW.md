# System Overview

Modular Monolith. Microservices, Kubernetes, Event Sourcing 전면 도입,
GraphQL Federation, 다중 DB는 도입하지 않는다.

```
┌─────────────┐   HTTPS    ┌──────────────────────────┐
│ Flutter App │ ─────────▶ │ NestJS API (apps/api)    │
│ (mobile)    │            │  HealthModule            │
│  로컬 캐시   │            │  CouponsModule           │
└─────────────┘            │  Prisma / Redis (global) │
┌─────────────┐            └─────┬──────────────┬─────┘
│ Next.js     │ ─────────▶       │              │
│ Admin       │            ┌─────▼─────┐  ┌─────▼─────┐
└─────────────┘            │ PostgreSQL│  │  Redis    │
                           │ (Prisma)  │  │ (health,  │
                           └───────────┘  │  M1 queue)│
                                          └───────────┘
```

## 실제 구현 상태 (Milestone 0)

- **API**: `GET /health`(DB+Redis 체크), `GET /v1/coupons`(실 DB 조회, 유효기간
  빠른 순, status 필터), Swagger `/docs`. 전역 오류 필터(공통 envelope),
  요청 로깅 인터셉터(requestId, 바디/쿼리 미기록), zod 환경변수 검증.
- **모바일**: feature-first 구조(`features/home`, `features/coupon_wallet`),
  Riverpod 상태, Dio 네트워크 계층(오류 → 타입드 예외), SharedPreferences
  기반 오프라인 캐시 폴백.
- **공유 패키지**: 순수 도메인 로직만 — API·앱 어디서든 재사용.
- **Redis**: 현재 health check 전용. Milestone 1에서 BullMQ 인식 큐가 사용.

## 인식 파이프라인 (M1 설계, 미구현)

API 이미지 업로드 → 분석 Job 생성 → Queue 등록 → Recognition Worker →
결과 저장 → 쿠폰 상태 업데이트 → 앱 조회.
OCR/이미지 분석을 API 요청 안에서 장시간 동기 처리하지 않는다.

## 백엔드 모듈 로드맵

현재: Health, Coupons, Prisma(global), Redis(global).
예정: Auth, Users, CouponAssets, CouponRecognition, Barcode, Brands,
Notifications, CouponEvents, Admin, Audit — 단일 NestJS 앱 내 모듈로 추가.
