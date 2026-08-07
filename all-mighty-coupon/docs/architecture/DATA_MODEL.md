# Data Model

스키마 원본: `apps/api/prisma/schema.prisma` (마이그레이션 적용·시드 완료).

## 모델

- **User**: id(cuid), email(unique), coupons[]
- **Coupon**: 브랜드/상품/카테고리, `faceValueMinor`(정수, KRW 원 단위 —
  부동소수점 금지), status, issuedAt/expiresAt(UTC), 사용처/조건,
  `encryptedBarcode`(원문은 암호화 저장 예정, M0에서는 미사용),
  `barcodeHash`(중복 검사용 SHA-256), sourceType, requiresReview,
  recognitionData(Json), redeemedAt/archivedAt
- **CouponAsset**: ORIGINAL / NORMALIZED / THUMBNAIL / BARCODE_CROP —
  원본과 파생 이미지를 분리 보관 (Original Image Is Ground Truth)
- **CouponEvent**: 도메인 이벤트 append-only 기록 (감사·분석 기반)
- **Listing** (M4): 판매 글 — priceMinor/feeMinor(정수 KRW), 상태
  LISTED/SOLD/CANCELLED. 쿠폰당 활성 1개, 판매 중 지갑 액션 잠금.
- **Order** (M4): 구매 기록 — buyer/seller, 금액·수수료, paymentRef
  (MOCK- 접두 = 모의 결제). 완료 시 Coupon.userId가 구매자로 이전.
- **ScheduledNotification** (M3): 만료 알림 인스턴스 — offsetDays(30/7/3/0),
  fireAt(UTC), status(PENDING/SENT/CANCELLED), message(발송 시 렌더).
  인앱 피드가 1차 채널이며 푸시 연동 시 동일 행을 재사용한다.

인덱스: userId, expiresAt, status, barcodeHash, (couponId, createdAt).

## 쿠폰 상태 머신 (`@amc/domain` `status-transitions.ts`, 테스트 포함)

```
PROCESSING ──ANALYSIS_SUCCEEDED──▶ ACTIVE
    │─ANALYSIS_NEEDS_REVIEW──▶ NEEDS_REVIEW ──USER_CONFIRMED──▶ ACTIVE
    └─ANALYSIS_FAILED──▶ INVALID
ACTIVE ⇄ EXPIRING_SOON (CLOCK_*, 재계산 시 양방향)
ACTIVE|EXPIRING_SOON ──CLOCK_EXPIRED──▶ EXPIRED   (역방향 자동 전환 없음)
ACTIVE|EXPIRING_SOON|NEEDS_REVIEW ──USER_MARKED_REDEEMED──▶ REDEEMED
REDEEMED ──USER_RESTORED──▶ ACTIVE (유효기간 기준 재계산: statusAfterRestore)
대부분 상태 ──USER_ARCHIVED──▶ ARCHIVED ──USER_UNARCHIVED──▶ ACTIVE
```

규칙:

- 날짜 기반 상태(EXPIRING_SOON, EXPIRED)는 저장된 의도가 아니라 **재계산 결과**
- 시스템은 EXPIRED를 임의로 ACTIVE로 되돌리지 않는다
- REDEEMED → ACTIVE는 사용자 명시적 복구로만
- EXPIRING_SOON 기본 윈도우: 7일 (`DEFAULT_EXPIRING_SOON_DAYS`)

## 시간·금액 규칙

- 서버 저장은 전부 UTC, 표시 시 사용자 타임존 변환
- "남은 일수"는 사용자 타임존의 달력일 기준 (`daysUntilExpiration`)
- 금액은 `faceValueMinor` 정수 하나로만
