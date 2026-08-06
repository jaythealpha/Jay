import { createHash } from 'node:crypto';

/**
 * Barcode values are sensitive (spec §17): raw values are encrypted at rest
 * and NEVER logged. Everything that needs comparison (duplicate detection)
 * works on this normalized hash instead of the raw value.
 */

/** OCR/scan noise tolerance: strip whitespace and unify case before hashing. */
export function normalizeBarcodeValue(raw: string): string {
  return raw.replace(/[\s-]/g, '').toUpperCase();
}

export function hashBarcode(raw: string): string {
  return createHash('sha256').update(normalizeBarcodeValue(raw), 'utf8').digest('hex');
}

/**
 * Display/logging-safe representation: keeps only the last 4 characters.
 * This is the ONLY form of a barcode allowed in logs or events.
 */
export function maskBarcode(raw: string): string {
  const normalized = normalizeBarcodeValue(raw);
  if (normalized.length <= 4) return '****';
  return `****${normalized.slice(-4)}`;
}
