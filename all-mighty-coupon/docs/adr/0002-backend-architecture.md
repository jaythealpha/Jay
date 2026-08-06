# ADR-0002: 백엔드 아키텍처 — NestJS Modular Monolith

- 상태: 채택됨 (Milestone 0에서 구현)
- 날짜: 2026-08-06

## 결정

TypeScript strict 모드의 단일 NestJS 애플리케이션. 기능은 Nest 모듈로 분리
(Health, Coupons 구현됨; Auth/Recognition/Notifications 등 예정).
DB는 PostgreSQL + Prisma, 큐는 Redis + BullMQ(M1), API 문서는 OpenAPI.

## 근거

- 초기 제품은 요구사항 변화가 빠르다 — 모듈 경계는 유지하되 배포 단위는
  하나로 두는 것이 반복 속도에 유리하다.
- OCR/이미지 분석은 장시간 작업이므로 요청-응답에서 분리해야 하지만,
  같은 코드베이스의 워커 프로세스 + BullMQ로 충분하다.
- 도메인 로직을 `packages/domain` 등 순수 패키지로 분리해 프레임워크 결합을
  낮췄다 — 이후 서비스 분리가 필요해도 로직은 이동 가능.

## 명시적 비도입

Microservices, Kubernetes, 전면 Event Sourcing, 전면 CQRS,
GraphQL Federation, 다중 DB, 자체 메시지 브로커, Multi-Agent 구조.
(CouponEvent append-only 기록은 유지하되 이벤트 소싱으로 상태를 재구성하지는
않는다.)
