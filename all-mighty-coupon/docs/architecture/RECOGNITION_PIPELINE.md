# Recognition Pipeline

상태: **정책·파서·해시 로직 + 테스트만 구현됨 (Milestone 0).**
이미지 업로드, 바코드 스캔, OCR 실행, 워커는 Milestone 1에서 구현한다.

## 파이프라인 설계 (독립 단계)

1. 이미지 파일 검증 → 2. 정규화 → 3. 바코드 감지 → 4. QR 감지 → 5. OCR →
2. 브랜드 후보 → 7. 상품명 → 8. 유효기간 후보 → 9. 금액 →
3. 사용처·조건 → 11. 중복 검사 → 12. 필드별 신뢰도 → 13. 검토 상태 결정 →
4. 결과 저장

비동기 실행: 업로드 → Job 생성 → BullMQ Queue → Recognition Worker →
결과 저장 → 상태 업데이트(PROCESSING → ACTIVE/NEEDS_REVIEW/INVALID) →
앱 조회. 원본 이미지는 수정·덮어쓰기 금지 (별도 NORMALIZED 에셋 생성).

## 구현된 빌딩 블록

| 단계        | 구현                                                                                         | 테스트 |
| ----------- | -------------------------------------------------------------------------------------------- | ------ |
| 날짜 추출   | `coupon-parser/dates.ts` — YYYY-MM-DD/`.`/`년월일`, 키워드·`~` 문맥 신뢰도, 불가능 날짜 거부 | ✅     |
| 금액 추출   | `coupon-parser/amounts.ts` — 원/₩/만원, 정수만, 통화 표식 없는 숫자 무시                     | ✅     |
| 브랜드 매칭 | `coupon-parser/brands.ts` — 사전+별칭, 정규화 매칭 (M1에서 DB 테이블화)                      | ✅     |
| 신뢰도 정책 | `coupon-parser/review-policy.ts`                                                             | ✅     |
| 바코드 해시 | `barcode-utils` — 정규화 SHA-256, 마스킹                                                     | ✅     |
| 상태 결정   | `domain/status-transitions.ts`                                                               | ✅     |

## 신뢰도 정책 (구현됨)

- ≥0.90 자동 적용 / 0.70–0.90 적용+확인 / <0.70 확인 필요
- **유효기간은 <0.95면 무조건 사용자 확인**
- 인식 실패 값은 null 유지 — 임의 문자열·오늘 날짜로 채우지 않음
- `requiresReview`: 유효기간 누락/저신뢰, 브랜드 미확인, 금액·상품명 모두
  누락 시 true

## OCR 공급자 경계 (설계)

```ts
interface OcrProvider {
  recognize(input: OcrInput): Promise<OcrResult>;
}
```

기기 내 OCR 우선, 실패/저신뢰 시 서버 OCR 폴백. 특정 공급자의 응답 구조가
도메인 모델에 직접 들어가지 않는다. 외부 키가 없는 동안은 Mock/Local
Provider로 구조와 테스트를 먼저 완성하고 미검증으로 보고한다.

## 중복 감지 (설계 + 해시 구현)

신호 조합: barcodeHash 일치(구현됨), 이미지 perceptual hash, 동일
사용자+브랜드+상품+유효기간, OCR 고유번호, 단시간 재등록.
자동 삭제 금지 — "이미 등록된 쿠폰과 비슷합니다" → 기존 보기 / 새로 등록 /
취소.
