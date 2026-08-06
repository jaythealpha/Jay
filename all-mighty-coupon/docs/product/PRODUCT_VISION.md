# Product Vision

> **"Never Lose a Coupon Again."**

쿠폰 이미지를 단순히 저장하는 앱이 아니다. 사용자가 보유한 쿠폰을
**빠르게 등록**하고, **정확히 인식**하고, **쉽게 찾고**, **유효기간이 지나기
전에 실제로 사용**하도록 돕는 개인 쿠폰 지갑이다.

## 핵심 원칙

| 원칙                           | 의미                                                                      | 구현 위치                                        |
| ------------------------------ | ------------------------------------------------------------------------- | ------------------------------------------------ |
| Three-Second Capture           | 발견 → 최대 3번의 행동 안에 등록 (공유 시트 / 앱 내 등록)                 | M1에서 구현 예정                                 |
| Confirm, Do Not Type           | 시스템이 먼저 추출, 사용자는 확인·수정만                                  | `packages/coupon-parser` (정책 구현), UI는 M1    |
| Expiration First               | 기본 정렬은 항상 유효기간 빠른 순                                         | `packages/domain/sorting`, API `GET /v1/coupons` |
| Trust Over Automation          | 불확실한 값은 확정하지 않음 — 필드별 신뢰도, 유효기간 <0.95는 사용자 확인 | `packages/coupon-parser/review-policy`           |
| Original Image Is Ground Truth | 원본 이미지는 항상 보존, 추출 정보와 분리 저장                            | `CouponAsset` 모델 (ORIGINAL 타입), 업로드는 M1  |
| Offline First for Redemption   | 매장에서 통신이 나빠도 쿠폰·바코드 열람 가능                              | `apps/mobile` CouponCache + 오프라인 폴백        |

## 하지 않는 것 (현 단계)

거래소, 결제, 에스크로, 정산, 쿠폰 판매, 발행사 API 연동, 위치 기반 알림,
광고, 기업용 발행. Milestone 4 이전에는 거래 기능을 만들지 않는다.
