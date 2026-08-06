import { hashPassword, verifyPassword } from './password';

describe('password hashing', () => {
  it('verifies a correct password and rejects a wrong one', () => {
    const stored = hashPassword('correct horse battery staple');
    expect(verifyPassword('correct horse battery staple', stored)).toBe(true);
    expect(verifyPassword('wrong password', stored)).toBe(false);
  });

  it('salts every hash (same password, different digests)', () => {
    expect(hashPassword('same')).not.toBe(hashPassword('same'));
  });

  it('never stores the plaintext and rejects malformed stored values', () => {
    const stored = hashPassword('secret-password');
    expect(stored).not.toContain('secret-password');
    expect(verifyPassword('secret-password', 'plaintext-not-a-hash')).toBe(false);
    expect(verifyPassword('secret-password', '')).toBe(false);
  });
});
