# ADR-0004: 이미지 스토리지 — S3 호환 Private Object Storage

- 상태: 채택됨 (설계만 — Milestone 1에서 구현)
- 날짜: 2026-08-06

## 결정

쿠폰 이미지는 S3 호환 private bucket에 저장한다. DB에는 `CouponAsset.storageKey`
만 저장하고, 클라이언트 접근은 짧은 유효기간의 signed URL로만 한다.
로컬 개발은 MinIO(도커)로 동일 API를 사용한다.

## 근거

- 원본 이미지는 Ground Truth이자 민감 정보다 — 공개 URL 금지, 원본 불변 유지.
- 에셋 타입 분리(ORIGINAL/NORMALIZED/THUMBNAIL/BARCODE_CROP)는 이미
  데이터 모델에 반영되어 있다(M0). 원본은 절대 덮어쓰지 않고 파생본을 만든다.
- S3 API 호환을 유지하면 로컬(MinIO)→클라우드 전환이 설정 변경으로 끝난다.

## 현재 상태 (M0)

`CouponAsset` 모델과 storageKey 필드만 존재. 실제 버킷 연동·업로드·signed URL
발급은 미구현이며, 외부 계정 없이 검증할 수 없으므로 M1에서 MinIO 기반으로
구현·검증한다.
