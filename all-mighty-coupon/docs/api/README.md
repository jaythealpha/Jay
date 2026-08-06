# API Reference

OpenAPI 문서는 API 실행 중 Swagger UI로 제공된다: `http://localhost:3001/docs`

인증: `POST /v1/auth/register`·`POST /v1/auth/login`(공개)이 반환하는
`accessToken`을 `Authorization: Bearer <token>`으로 전달한다. health/auth 외
모든 엔드포인트는 인증 필수이며 **요청 사용자의 쿠폰만** 다룬다.

## 엔드포인트

### POST /v1/auth/register · /v1/auth/login (M2)

body: `{ "email", "password" }` (비밀번호 8자+). 응답:
`{ "accessToken", "user": { "id", "email" } }`. 로그인 실패는 일반 메시지
하나로 응답한다. `GET /v1/auth/me` — 현재 사용자.

### GET /health

```json
{ "status": "ok", "components": { "database": "up", "redis": "up" }, "checkedAt": "…" }
```

`status`는 모든 컴포넌트가 up일 때만 `ok`, 아니면 `degraded`.

### GET /v1/coupons?status=&q=&sort=&limit=

기본 정렬은 유효기간 빠른 순(무기한은 뒤), 동률은 최근 등록 순.
`status`: CouponStatus enum · `q`: 브랜드/상품명/카테고리 검색 ·
`sort`: EXPIRATION_ASC(기본)/CREATED_DESC/VALUE_DESC/BRAND_ASC ·
`limit` 기본 50·최대 100. 응답 아이템에는 바코드 관련 필드가 포함되지
않는다.

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

### 지갑 액션 (M2)

- `POST /v1/coupons/:id/redeem` — 사용 완료(REDEEMED). 이미 사용됨 등 잘못된
  전환은 400.
- `POST /v1/coupons/:id/restore` — 사용 완료 취소. 최종 상태는 유효기간 기준
  재계산(만료된 쿠폰은 EXPIRED로 복구).
- `POST /v1/coupons/:id/archive` · `/unarchive` — 보관/해제.
- `DELETE /v1/coupons/:id` — 204, 저장 이미지 포함 완전 삭제.
- `GET /v1/coupons/:id/barcode` — `{ value, format }`. 열람마다
  BARCODE_VIEWED 감사 이벤트 기록(메타데이터는 마스킹 값만). 저장된 바코드가
  없으면 404.

### GET /v1/home (M3)

행동 우선 홈 데이터: `expiringSoon`(3일 이내, 만료 임박순 5개),
`useThisWeek`(7일 이내 ∪ 2만원+ 고가치, 5개), `recent`(최근 등록 5개),
`counts`(active/expiringSoon/redeemed/needsReview/total),
`totalValueMinor`(활성 쿠폰 총 가치, KRW 정수).

### GET /v1/notifications · POST /v1/notifications/:id/snooze (M3)

발송된 만료 알림 피드(최신 50개): `{ id, couponId(딥링크용), message,
offsetDays, sentAt }`. snooze는 24시간 뒤 재알림을 예약하고 `{ fireAt }`
반환.

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

타입 계약: `packages/shared-types`.
