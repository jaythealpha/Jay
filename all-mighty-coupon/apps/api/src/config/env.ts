import 'dotenv/config';
import { z } from 'zod';

/**
 * Environment validation happens once at boot; a misconfigured process fails
 * fast with a readable message instead of failing later mid-request.
 * BARCODE_ENCRYPTION_KEY is optional until the recognition pipeline (M1) needs
 * it, but when present it must be a real 32-byte hex key.
 */
const envSchema = z.object({
  NODE_ENV: z.enum(['development', 'test', 'production']).default('development'),
  API_PORT: z.coerce.number().int().min(1).max(65535).default(3001),
  DATABASE_URL: z.string().url().startsWith('postgresql'),
  REDIS_URL: z.string().url().startsWith('redis'),
  BARCODE_ENCRYPTION_KEY: z
    .string()
    .regex(/^[0-9a-fA-F]{64}$/, 'must be 64 hex characters (32 bytes)')
    .optional(),
});

export type Env = z.infer<typeof envSchema>;

let cached: Env | null = null;

export function loadEnv(): Env {
  if (cached) return cached;
  const parsed = envSchema.safeParse(process.env);
  if (!parsed.success) {
    const issues = parsed.error.issues
      .map((issue) => `  - ${issue.path.join('.')}: ${issue.message}`)
      .join('\n');
    throw new Error(`Invalid environment configuration:\n${issues}`);
  }
  cached = parsed.data;
  return cached;
}

/** Test hook: clears the memoized env so each test controls its own values. */
export function resetEnvCacheForTesting(): void {
  cached = null;
}
