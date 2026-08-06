/**
 * Recognition-accuracy dataset: OCR-like text samples with ground truth.
 * Sources are hand-written to imitate real Korean gifticon OCR output,
 * including noisy variants. Extend this set as real (anonymized) OCR samples
 * are collected in the capture lab — accuracy numbers are only as honest as
 * this dataset is representative.
 */
export interface DatasetSample {
  id: string;
  text: string;
  expected: {
    brand: string | null;
    /** ISO date (YYYY-MM-DD) or null when the text truly has no expiration. */
    expiresAt: string | null;
    amountMinor: number | null;
  };
}

export const DATASET: DatasetSample[] = [
  {
    id: 'starbucks-standard',
    text: '스타벅스\n아이스 카페 아메리카노 Tall\n유효기간 2026.12.31 까지\n금액 4,500원\n주문번호 1234-5678',
    expected: { brand: '스타벅스', expiresAt: '2026-12-31', amountMinor: 4500 },
  },
  {
    id: 'starbucks-english-alias',
    text: 'STARBUCKS COFFEE\nIced Americano Tall\nvalid until 2026-11-30\n₩4,500',
    expected: { brand: '스타벅스', expiresAt: '2026-11-30', amountMinor: 4500 },
  },
  {
    id: 'baskin-korean-date',
    text: '배스킨라빈스\n파인트 아이스크림\n2027년 3월 31일 까지 사용 가능\n금액 9,800원',
    expected: { brand: '배스킨라빈스', expiresAt: '2027-03-31', amountMinor: 9800 },
  },
  {
    id: 'baskin-ocr-typo-alias',
    text: '베스킨라빈스\n싱글레귤러 교환권\n사용기한 2026.09.15\n3,900원',
    expected: { brand: '배스킨라빈스', expiresAt: '2026-09-15', amountMinor: 3900 },
  },
  {
    id: 'emart-manwon-unit',
    text: '이마트 모바일 금액권\n3만원 금액권\n유효기간 2027-01-31',
    expected: { brand: '이마트', expiresAt: '2027-01-31', amountMinor: 30000 },
  },
  {
    id: 'twosome-range-notation',
    text: 'A TWOSOME PLACE\n스트로베리 초콜릿 생크림\n사용기간 2026.01.01 ~ 2026.06.30\n37,000원',
    expected: { brand: '투썸플레이스', expiresAt: '2026-06-30', amountMinor: 37000 },
  },
  {
    id: 'kyochon-issue-and-expiry',
    text: '교촌치킨 허니콤보\n발행일 2026.01.02\n유효기간 2026.12.31\n결제금액 23,000원',
    expected: { brand: '교촌치킨', expiresAt: '2026-12-31', amountMinor: 23000 },
  },
  {
    id: 'gs25-compact',
    text: 'GS25 모바일상품권 5,000원권 만료 2026.10.01',
    expected: { brand: 'GS25', expiresAt: '2026-10-01', amountMinor: 5000 },
  },
  {
    id: 'oliveyoung-spaced-alias',
    text: 'OLIVE YOUNG 기프트카드\n10,000원\n유효기간: 2027.05.20',
    expected: { brand: '올리브영', expiresAt: '2027-05-20', amountMinor: 10000 },
  },
  {
    id: 'paris-noisy-ocr',
    text: '파리바게트\n촉촉한 우유 생크림 케이크\n유 효 기 간 2026.08.31 까지\n28,000 원',
    expected: { brand: '파리바게뜨', expiresAt: '2026-08-31', amountMinor: 28000 },
  },
  {
    id: 'bare-date-no-keyword',
    text: 'CU 편의점 상품권\n2026.09.30\n5,000원',
    expected: { brand: 'CU', expiresAt: '2026-09-30', amountMinor: 5000 },
  },
  {
    id: 'no-expiration-at-all',
    text: '스타벅스 텀블러 교환권\n리유저블 텀블러',
    expected: { brand: '스타벅스', expiresAt: null, amountMinor: null },
  },
  {
    id: 'unknown-brand',
    text: '동네 반찬가게 쿠폰\n5,000원 할인\n유효기간 2026.12.25',
    expected: { brand: null, expiresAt: '2026-12-25', amountMinor: 5000 },
  },
  {
    id: 'barcode-digits-not-amount',
    text: '교촌치킨\n허니콤보 교환권\n8801234567890\n유효기간 2026.11.11',
    expected: { brand: '교촌치킨', expiresAt: '2026-11-11', amountMinor: null },
  },
  {
    id: 'balance-vs-facevalue',
    text: '이마트 금액권\n결제금액 30,000원 (잔액 12,500원)\n유효기간 2027.02.28 까지',
    expected: { brand: '이마트', expiresAt: '2027-02-28', amountMinor: 30000 },
  },
  {
    id: 'not-a-coupon',
    text: '오늘 점심 뭐 먹지\n회의는 오후 3시',
    expected: { brand: null, expiresAt: null, amountMinor: null },
  },
];
