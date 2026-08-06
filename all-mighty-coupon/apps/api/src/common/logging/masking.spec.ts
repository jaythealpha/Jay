import { MASK, maskEmail, maskSensitive } from './masking';

describe('maskEmail', () => {
  it('keeps at most two local characters and the domain', () => {
    expect(maskEmail('demo-user@example.com')).toBe('de***@example.com');
    expect(maskEmail('a@example.com')).toBe('a***@example.com');
  });

  it('fully masks malformed values', () => {
    expect(maskEmail('not-an-email')).toBe(MASK);
  });
});

describe('maskSensitive', () => {
  it('redacts barcode and token values at any nesting depth', () => {
    const masked = maskSensitive({
      coupon: { barcodeValue: '880123456789', couponNumber: 'ABC-123' },
      auth: { accessToken: 'jwt-value', Authorization: 'Bearer x' },
    }) as Record<string, Record<string, unknown>>;
    expect(masked.coupon?.barcodeValue).toBe(MASK);
    expect(masked.coupon?.couponNumber).toBe(MASK);
    expect(masked.auth?.accessToken).toBe(MASK);
    expect(masked.auth?.Authorization).toBe(MASK);
  });

  it('keeps the duplicate-detection hash visible (it is not sensitive)', () => {
    const masked = maskSensitive({ barcodeHash: 'abc123' }) as Record<string, unknown>;
    expect(masked.barcodeHash).toBe('abc123');
  });

  it('masks emails while keeping other fields intact', () => {
    const masked = maskSensitive({ email: 'demo-user@example.com', status: 'ACTIVE' }) as Record<
      string,
      unknown
    >;
    expect(masked.email).toBe('de***@example.com');
    expect(masked.status).toBe('ACTIVE');
  });

  it('never leaves a raw sensitive value in the output', () => {
    const raw = { nested: [{ barcode: 'SECRET-999' }] };
    expect(JSON.stringify(maskSensitive(raw))).not.toContain('SECRET-999');
  });
});
