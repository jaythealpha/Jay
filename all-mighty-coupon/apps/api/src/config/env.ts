import 'dotenv/config';
import { z } from 'zod';

/**
 * Environment validation happens once at boot; a misconfigured process fails
 * fast with a readable message instead of failing later mid-request.
 */
const envSchema = z
  .object({
    NODE_ENV: z.enum(['development', 'test', 'production']).default('development'),
    API_PORT: z.coerce.number().int().min(1).max(65535).default(3001),
    DATABASE_URL: z.string().url().startsWith('postgresql'),
    REDIS_URL: z.string().url().startsWith('redis'),
    STORAGE_DRIVER: z.enum(['s3', 'local']).default('local'),
    S3_ENDPOINT: z.string().url().optional(),
    S3_REGION: z.string().default('us-east-1'),
    S3_ACCESS_KEY: z.string().optional(),
    S3_SECRET_KEY: z.string().optional(),
    S3_BUCKET: z.string().default('amc-coupon-assets'),
    SIGNED_URL_TTL_SECONDS: z.coerce.number().int().min(30).max(3600).default(300),
    LOCAL_STORAGE_DIR: z.string().default('.storage'),
    // Only the deterministic mock exists today; real providers (device OCR is
    // primary, server OCR fallback) register here as they land.
    OCR_PROVIDER: z.enum(['mock']).default('mock'),
    BARCODE_ENCRYPTION_KEY: z
      .string()
      .regex(/^[0-9a-fA-F]{64}$/, 'must be 64 hex characters (32 bytes)')
      .optional(),
    JWT_SECRET: z.string().min(32, 'use at least 32 characters (openssl rand -hex 32)'),
    JWT_EXPIRES_IN: z.string().default('7d'),
  })
  .superRefine((env, ctx) => {
    if (env.STORAGE_DRIVER === 's3') {
      for (const key of ['S3_ENDPOINT', 'S3_ACCESS_KEY', 'S3_SECRET_KEY'] as const) {
        if (!env[key]) {
          ctx.addIssue({
            code: z.ZodIssueCode.custom,
            path: [key],
            message: `required when STORAGE_DRIVER=s3`,
          });
        }
      }
    }
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
