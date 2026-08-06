/** Confidence score in [0, 1] attached to each extracted field. */
export type Confidence = number;

export interface FieldCandidate<T> {
  value: T;
  confidence: Confidence;
}

/**
 * Per-field recognition output. Unknown fields stay null — the pipeline never
 * substitutes guesses (e.g. today's date) for values it could not read.
 */
export interface CouponRecognitionResult {
  brand: FieldCandidate<string> | null;
  productName: FieldCandidate<string> | null;
  expiresAt: FieldCandidate<string> | null;
  amountMinor: FieldCandidate<number> | null;
  barcodeValuePresent: boolean;
  barcodeConfidence: Confidence | null;
  usageConditions: string | null;
}
