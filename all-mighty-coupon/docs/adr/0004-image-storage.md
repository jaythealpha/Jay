# ADR-0004: 이미지 스토리지 — S3 호환 Private Object Storage

- 상태: 채택됨 · **구현됨 (Milestone 1)**
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

## 현재 상태 (M1 구현 완료)

`StorageService` 추상 뒤에 두 드라이버:

- `S3StorageService` — MinIO(도커)로 실검증: private bucket 자동 생성,
  업로드, 300초 signed URL 발급·다운로드 확인
- `LocalStorageService` — 키 없는 환경(CI 등)용 파일시스템 폴백

`STORAGE_DRIVER` env로 선택. ORIGINAL은 불변, NORMALIZED/THUMBNAIL은 파생
에셋으로 별도 저장. 프로덕션 클라우드 버킷 전환은 env 변경만으로 가능하나
실 클라우드 검증은 미실시.
