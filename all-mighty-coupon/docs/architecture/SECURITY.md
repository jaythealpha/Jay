# Security & Privacy

## 민감 정보 목록

바코드 원문, 쿠폰 번호, 원본 이미지, 사용자 이메일, 인증 토큰,
기기 푸시 토큰. (위치 정보는 수집하지 않는다 — 앱은 위치 권한 없이 완전 동작.)

## 구현된 방어 (Milestone 0)

- **로그 마스킹**: `apps/api/src/common/logging/masking.ts` —
  barcode/couponNumber/token/password/secret 등 키 패턴 REDACT,
  이메일은 앞 2자+도메인만 노출. 단위 테스트로 검증.
- **요청 로깅**: method/path/status/duration/requestId만 기록.
  바디·쿼리 값은 기록하지 않는다 (검색어·쿠폰번호 유출 방지).
- **API 응답 경계**: `coupon.mapper.ts`가 wire DTO를 강제 —
  `encryptedBarcode`·`barcodeHash`·`recognitionData`는 목록 응답에 절대
  포함되지 않음 (단위 + e2e 테스트로 검증).
- **중복 검사**: 원문 대신 `@amc/barcode-utils`의 정규화 SHA-256 해시.
  마스킹 헬퍼는 마지막 4자만 노출.
- **오류 응답**: 스택트레이스·내부 코드 미노출, 공통 envelope + requestId.
- **환경변수**: zod 부팅 검증. `.env` 커밋 금지(.gitignore), `.env.example`만
  커밋. `BARCODE_ENCRYPTION_KEY`는 설정 시 64-hex 강제.
- **시드 데이터**: 바코드 원문 미저장(해시만), `sampleData: true` 표시.

## Milestone 1에서 추가 구현된 방어

- **바코드 원문 AES-256-GCM 암호화 저장** (`crypto/barcode-crypto.service.ts`,
  키는 `BARCODE_ENCRYPTION_KEY` 64-hex env, IV 랜덤, 변조 시 복호화 실패 —
  단위 테스트 3종). 이벤트에는 마스킹된 값(`****1234`)만 기록.
- **Private object storage + signed URL**: MinIO(S3 호환) private bucket,
  300초 만료 signed URL. 키 없는 환경용 파일시스템 폴백 드라이버 포함.
- 파이프라인 이벤트(BARCODE_DETECTED, OCR_COMPLETED 등)에 바코드 원문·OCR
  전문 미포함 — 통합 테스트가 이벤트 직렬화에 원문 부재를 검증.
- 상세 API도 `hasBarcode`/`barcodeType`만 노출, 원문·해시 미노출.

## Milestone 2에서 추가 구현된 방어

- **인증/인가**: 이메일+비밀번호(scrypt, salt별 해시, 타이밍 안전 비교) +
  JWT(HS256, `JWT_SECRET` ≥32자 강제). 전역 가드 — `@Public()` 표시된
  health/auth 외 전 라우트 보호. 로그인 실패는 단일 일반 메시지
  (계정 존재 여부 비노출), 타인 쿠폰 접근은 404.
- **바코드 전용 열람 API**: `GET /v1/coupons/:id/barcode` — 소유자만,
  열람마다 `BARCODE_VIEWED` 감사 이벤트(마스킹 값만 기록). 목록/상세에는
  여전히 원문 미노출.
- 모바일: 토큰과 오프라인 바코드는 **플랫폼 보안 저장소**
  (flutter_secure_storage)에만 저장 — SharedPreferences 금지.
- 세션 만료(401) 시 토큰 자동 폐기 + 로그인 화면 복귀. 오프라인 폴백이
  인증 오류를 가리지 않도록 SessionExpired는 캐시 폴백에서 제외.

## 설계됨 · 미구현 (이후 마일스톤)

- Refresh token / 토큰 회전, 비밀번호 재설정 플로우
- 관리자 권한 분리(관리자도 바코드 원문 기본 열람 불가 정책의 관리자 측 구현)
- 오류 추적 서비스 연동 시 원본 이미지·OCR 전문 전송 금지 정책 적용
- 프로덕션 배포 전 rate limiting, 계정 잠금 정책
