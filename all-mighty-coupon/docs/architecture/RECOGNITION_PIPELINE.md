# Recognition Pipeline

상태: **Milestone 1 구현 완료.** 업로드 → BullMQ 큐 → 워커 → ZXing 바코드
판독 → OCR(Mock Provider) → 필드 추출 → 신뢰도/중복/상태 결정까지 실제 동작
(통합 테스트 5종으로 검증). 실제 OCR 엔진 연동만 미구현.

## 파이프라인 설계 (독립 단계)

1. 이미지 파일 검증 → 2. 정규화 → 3. 바코드 감지 → 4. QR 감지 → 5. OCR →
2. 브랜드 후보 → 7. 상품명 → 8. 유효기간 후보 → 9. 금액 →
3. 사용처·조건 → 11. 중복 검사 → 12. 필드별 신뢰도 → 13. 검토 상태 결정 →
4. 결과 저장

비동기 실행(구현됨): `POST /v1/coupons` → Job 생성 → BullMQ Queue(재시도 3회,
지수 백오프) → RecognitionProcessor(현재 API 프로세스에 코호스팅) → 결과 저장
→ 상태 업데이트(PROCESSING → ACTIVE/NEEDS_REVIEW/INVALID) → 앱 폴링 조회.
원본 이미지는 수정·덮어쓰기 금지 — NORMALIZED/THUMBNAIL 에셋을 따로 생성한다.
파이프라인 실패 시 쿠폰은 NEEDS_REVIEW로 전환되어 사용자가 직접 입력할 수
있다(PROCESSING에 고착되지 않음).

구현 위치: `apps/api/src/recognition/` (image/ barcode/ ocr/ + service,
queue, processor). 바코드 감지는 ZXing WASM으로 실제 판독하며 감지 시
AES-256-GCM 암호화 저장 + SHA-256 해시 기반 중복 의심 표시까지 수행한다.

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

**기기 내 OCR 우선 구조 구현됨**: 앱이 ML Kit(한국어)로 인식한 텍스트를
`deviceOcrText`로 업로드에 실어 보내면 파이프라인이 이를 우선 사용하고
(provider='device'), 없을 때만 서버 OcrProvider로 폴백한다. 원문 텍스트는
파싱 후 recognitionData에서 폐기된다. 서버 측 인터페이스와 Mock Provider도
구현됨(`recognition/ocr/`). MockOcrProvider는
업로드 파일 꼬리의 `AMC-MOCK-OCR:` 마커 텍스트를 읽거나(테스트·랩 용도),
마커가 없으면 `[MOCK OCR SAMPLE]` 표시가 붙은 고정 텍스트를 반환한다 — mock
결과가 실제 인식처럼 보이지 않게 하기 위함이다. **실제 OCR 엔진은 미연동·
미검증.** 방향: 기기 내 OCR(ML Kit) 우선, 실패/저신뢰 시 서버 OCR 폴백.
특정 공급자의 응답 구조는 도메인 모델에 직접 들어가지 않는다.

## 중복 감지 (설계 + 해시 구현)

구현됨: 동일 사용자 + barcodeHash 일치 → `recognition.duplicateSuspects`로
상세 응답에 노출, 모바일 검토 화면이 "이미 등록된 쿠폰과 비슷해요" 안내를
표시. 자동 삭제는 하지 않는다 (통합 테스트로 검증).
추가 신호(미구현): 이미지 perceptual hash, 브랜드+상품+유효기간 조합,
OCR 고유번호, 단시간 재등록.

## 정확도 측정 (구현됨)

`packages/coupon-parser/src/accuracy/` — 한국어 기프티콘 OCR 텍스트 16종
데이터셋 + 필드별 정확도 측정. `npm run accuracy`로 리포트 출력, vitest가
90% 회귀 하한선을 강제한다. 현재 브랜드/유효기간/금액 각 16/16 (100%).
**주의: 합성 텍스트 기준 파서 정확도이며, 실제 이미지 OCR 종단 정확도가
아니다.** 실제 OCR 연동 시 익명화된 실측 샘플로 데이터셋을 확장한다.
