import { describe, expect, it } from 'vitest';
import { hashBarcode, maskBarcode, normalizeBarcodeValue } from './index';

describe('normalizeBarcodeValue', () => {
  it('strips whitespace/hyphens and upcases', () => {
    expect(normalizeBarcodeValue('8801 2345-6789 0abc')).toBe('8801234567890ABC');
  });
});

describe('hashBarcode', () => {
  it('is deterministic and format-insensitive', () => {
    expect(hashBarcode('8801-2345-6789')).toBe(hashBarcode('880123456789'));
  });

  it('differs for different values and never contains the raw value', () => {
    const hash = hashBarcode('880123456789');
    expect(hash).not.toBe(hashBarcode('880123456780'));
    expect(hash).toMatch(/^[0-9a-f]{64}$/);
    expect(hash).not.toContain('880123456789');
  });
});

describe('maskBarcode', () => {
  it('exposes only the last 4 characters', () => {
    expect(maskBarcode('880123456789')).toBe('****6789');
  });

  it('fully masks short values', () => {
    expect(maskBarcode('123')).toBe('****');
  });
});
