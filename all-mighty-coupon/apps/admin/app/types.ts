// Mirrors @amc/shared-types HealthResponseDto. The admin app intentionally
// avoids workspace TS-source imports until its build is wired to consume
// built packages (tracked for Milestone 1).
export interface HealthResponseDto {
  status: 'ok' | 'degraded';
  components: {
    database: 'up' | 'down';
    redis: 'up' | 'down';
  };
  checkedAt: string;
}
