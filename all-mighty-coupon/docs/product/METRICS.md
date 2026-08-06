# Metrics & Analytics Events

## 북극성 지표 (설계)

**만료 전 사용률**: 등록된 쿠폰 중 만료 전에 REDEEMED 처리된 비율.
비전("Never Lose a Coupon Again")을 직접 측정한다.

보조 지표: 등록 완료율(캡처 시작 → 저장), 자동 인식 수정률(낮을수록 정확),
7일 재방문율, 만료 알림 → 앱 오픈 전환율.

## 분석 이벤트 카탈로그 (기반 설계 — 수집 파이프라인은 미구현)

Milestone 0에는 이벤트 수집 SDK가 연동되어 있지 않다. 아래는 확정된 이벤트
이름 목록이며, 서버측 `CouponEvent` 모델이 도메인 이벤트 기록 기반을 제공한다.

app_opened, onboarding_started, onboarding_completed, coupon_capture_started,
coupon_image_selected, coupon_analysis_started, coupon_analysis_completed,
coupon_analysis_failed, coupon_review_opened, coupon_review_edited,
coupon_saved, coupon_duplicate_detected, coupon_detail_opened, barcode_opened,
coupon_marked_redeemed, coupon_restored, coupon_archived, coupon_deleted,
notification_permission_requested, notification_permission_granted,
notification_permission_denied, expiration_notification_opened, search_used,
filter_used

## 이벤트에 절대 포함하지 않는 데이터

바코드 원문, 쿠폰 번호, 전체 OCR 텍스트, 원본 이미지, signed URL, 인증 토큰.
서버측 방어는 `apps/api/src/common/logging/masking.ts`가 담당한다
(키 패턴 기반 REDACT + 이메일 부분 마스킹, 테스트 포함).
