export interface OcrInput {
  /** Normalized JPEG — what a real OCR engine should consume. */
  normalized: Buffer;
  /** Untouched upload, used by the mock provider's embedded-text protocol. */
  original: Buffer;
}

export interface OcrResult {
  text: string;
  /** Provider-level confidence in [0,1] for the whole text block. */
  confidence: number;
}

/**
 * OCR boundary (spec §10): provider responses never leak into the domain —
 * the pipeline only sees {text, confidence}. On-device OCR is the primary
 * path in the mobile app; this server-side provider is the fallback and the
 * recognition-lab harness.
 */
export abstract class OcrProvider {
  abstract readonly providerName: string;
  abstract recognize(input: OcrInput): Promise<OcrResult>;
}
