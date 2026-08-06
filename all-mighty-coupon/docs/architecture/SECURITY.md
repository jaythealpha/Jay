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

## 설계됨 · 미구현 (이후 마일스톤)

- 바코드 원문 AES-256-GCM 암호화 저장 및 전용 열람 API (BARCODE_VIEWED 감사
  이벤트 포함, 관리자도 기본 열람 불가)
- Private object storage + 짧은 유효기간 signed URL (ADR-0004)
- 인증/인가 (M2) — 현재 API는 인증 없음. **로컬 개발 전용이며 시드 데이터만
  다룬다. 이 상태로 외부에 배포해서는 안 된다.**
- 오류 추적 서비스 연동 시 원본 이미지·OCR 전문 전송 금지 정책 적용
