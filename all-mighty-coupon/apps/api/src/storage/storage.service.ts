/**
 * Object-storage boundary (ADR-0004). Coupon images live in a PRIVATE bucket;
 * clients only ever receive short-lived signed URLs. Two implementations:
 * S3-compatible (MinIO in dev) and a filesystem fallback for keyless setups.
 */
export interface PutObjectInput {
  key: string;
  body: Buffer;
  contentType: string;
}

export abstract class StorageService {
  abstract putObject(input: PutObjectInput): Promise<void>;
  abstract getObject(key: string): Promise<Buffer>;
  abstract deleteObject(key: string): Promise<void>;
  /** Short-lived read URL; TTL comes from SIGNED_URL_TTL_SECONDS. */
  abstract getSignedUrl(key: string): Promise<string>;
  /** Idempotent bucket/directory bootstrap for dev environments. */
  abstract ensureReady(): Promise<void>;
}
