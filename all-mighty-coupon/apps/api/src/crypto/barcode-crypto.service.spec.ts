import { BarcodeCryptoService } from './barcode-crypto.service';

describe('BarcodeCryptoService', () => {
  beforeAll(() => {
    process.env.BARCODE_ENCRYPTION_KEY =
      'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';
  });

  it('round-trips a barcode value', () => {
    const service = new BarcodeCryptoService();
    const encrypted = service.encrypt('8801234567890');
    expect(service.decrypt(encrypted)).toBe('8801234567890');
  });

  it('never stores the plaintext and randomizes the IV', () => {
    const service = new BarcodeCryptoService();
    const a = service.encrypt('8801234567890');
    const b = service.encrypt('8801234567890');
    expect(a).not.toContain('8801234567890');
    expect(a).not.toBe(b);
  });

  it('rejects tampered payloads', () => {
    const service = new BarcodeCryptoService();
    const encrypted = service.encrypt('8801234567890');
    const tampered = Buffer.from(encrypted, 'base64');
    const lastIndex = tampered.length - 1;
    tampered[lastIndex] = (tampered[lastIndex] ?? 0) ^ 0xff;
    expect(() => service.decrypt(tampered.toString('base64'))).toThrow();
  });
});
