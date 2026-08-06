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
