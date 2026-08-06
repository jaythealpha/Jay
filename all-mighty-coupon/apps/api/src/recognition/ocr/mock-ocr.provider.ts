import { Injectable } from '@nestjs/common';
import { OcrInput, OcrProvider, OcrResult } from './ocr-provider';

/**
 * Deterministic OCR stand-in for development and tests (no external service,
 * spec §10: build the structure with a mock first, report real OCR as
 * unverified).
 *
 * Protocol: if the uploaded file carries a trailing `AMC-MOCK-OCR:<utf8>`
 * marker (PNG/JPEG decoders ignore trailing bytes), that text is returned —
 * this lets tests and the recognition lab drive any OCR outcome. Without a
 * marker it returns a fixed sample coupon text, clearly tagged as mock.
 */
export const MOCK_OCR_MARKER = 'AMC-MOCK-OCR:';

export const DEFAULT_MOCK_TEXT = [
  '[MOCK OCR SAMPLE]',
  '스타벅스',
  '아이스 카페 아메리카노 Tall',
  '유효기간 2026.12.31 까지',
  '금액 4,500원',
].join('\n');

@Injectable()
export class MockOcrProvider extends OcrProvider {
  override readonly providerName = 'mock';

  override async recognize(input: OcrInput): Promise<OcrResult> {
    const raw = input.original.toString('utf8');
    const markerIndex = raw.lastIndexOf(MOCK_OCR_MARKER);
    if (markerIndex >= 0) {
      return { text: raw.slice(markerIndex + MOCK_OCR_MARKER.length), confidence: 0.99 };
    }
    return { text: DEFAULT_MOCK_TEXT, confidence: 0.99 };
  }
}
