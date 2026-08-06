/**
 * Common error envelope for every API error response.
 * `message` is always safe to show to users; internal details never leak here.
 */
export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    requestId?: string;
    details?: Record<string, unknown>;
  };
}

export type HealthComponentStatus = 'up' | 'down';

export interface HealthResponseDto {
  status: 'ok' | 'degraded';
  components: {
    database: HealthComponentStatus;
    redis: HealthComponentStatus;
  };
  /** ISO-8601 UTC timestamp of the check. */
  checkedAt: string;
}
