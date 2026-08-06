# API Reference

OpenAPI 문서는 API 실행 중 Swagger UI로 제공된다: `http://localhost:3001/docs`

## Milestone 0 엔드포인트

### GET /health

```json
{ "status": "ok", "components": { "database": "up", "redis": "up" }, "checkedAt": "…" }
```

`status`는 모든 컴포넌트가 up일 때만 `ok`, 아니면 `degraded`.

### GET /v1/coupons?status=&limit=

유효기간 빠른 순(무기한은 뒤), 동률은 최근 등록 순. `status`는 CouponStatus
enum 값, `limit` 기본 50·최대 100. 응답 아이템에는 바코드 관련 필드가
포함되지 않는다.

```json
{ "items": [ { "id", "brandName", "productName", "category", "faceValueMinor",
  "currency", "status", "expiresAt", "requiresReview", "sourceType",
  "createdAt", "updatedAt" } ], "total": 5 }
```

### POST /v1/coupons (M1)

multipart/form-data: `image`(jpeg/png/webp, 최대 10MB), `sourceType`(선택,
CouponSourceType). 201 응답: `{ "id", "status": "PROCESSING" }`.
분석은 비동기(BullMQ) — 이후 상세를 폴링한다.

### GET /v1/coupons/:id (M1)

Summary 필드 + `usageLocationText`, `usageConditions`, `barcodeType`,
`hasBarcode`, `recognition`(필드별 confidences · duplicateSuspects · error),
`assets`(type/mimeType/**300초 signed URL**). 바코드 원문·해시는 노출하지
않는다.

### PATCH /v1/coupons/:id (M1)

body(json): brandName, productName, category, faceValueMinor(정수 원),
expiresAt(`YYYY-MM-DD`), usageLocationText, usageConditions — 전부 선택,
null로 비우기 가능. 유효기간 변경 시 날짜 기반 상태를 재계산한다
(EXPIRED 자동 부활 없음). USER_EDITED 이벤트 기록.

### POST /v1/coupons/:id/confirm (M1)

NEEDS_REVIEW → ACTIVE(날짜 기준 재계산). requiresReview=false.
다른 상태에서 호출 시 400.

### 오류 형식 (전 엔드포인트 공통)

```json
{
  "error": {
    "code": "BAD_REQUEST",
    "message": "지원하지 않는 상태 값입니다: X",
    "requestId": "uuid"
  }
}
```

모든 응답에 `x-request-id` 헤더가 포함된다.

인증: 없음 (M0 한정, 로컬 개발 전용). 타입 계약: `packages/shared-types`.
