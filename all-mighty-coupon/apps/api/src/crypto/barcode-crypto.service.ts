import { Injectable } from '@nestjs/common';
import { createCipheriv, createDecipheriv, randomBytes } from 'node:crypto';
import { loadEnv } from '../config/env';

/**
 * Barcode payloads are worth money — they are encrypted at rest with
 * AES-256-GCM (ADR-0005). Stored format: base64(iv | authTag | ciphertext).
 * The raw value never appears in logs, events, or list APIs.
 */
@Injectable()
export class BarcodeCryptoService {
  private readonly key: Buffer;

  constructor() {
    const hex = loadEnv().BARCODE_ENCRYPTION_KEY;
    if (!hex) {
      throw new Error('BARCODE_ENCRYPTION_KEY is required for the recognition pipeline');
    }
    this.key = Buffer.from(hex, 'hex');
  }

  encrypt(plaintext: string): string {
    const iv = randomBytes(12);
    const cipher = createCipheriv('aes-256-gcm', this.key, iv);
    const ciphertext = Buffer.concat([cipher.update(plaintext, 'utf8'), cipher.final()]);
    return Buffer.concat([iv, cipher.getAuthTag(), ciphertext]).toString('base64');
  }

  decrypt(payload: string): string {
    const raw = Buffer.from(payload, 'base64');
    const iv = raw.subarray(0, 12);
    const authTag = raw.subarray(12, 28);
    const ciphertext = raw.subarray(28);
    const decipher = createDecipheriv('aes-256-gcm', this.key, iv);
    decipher.setAuthTag(authTag);
    return Buffer.concat([decipher.update(ciphertext), decipher.final()]).toString('utf8');
  }
}
