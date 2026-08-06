// Mirrors API DTOs. The admin app intentionally avoids workspace TS-source
// imports until its build is wired to consume built packages.
export interface HealthResponseDto {
  status: 'ok' | 'degraded';
  components: {
    database: 'up' | 'down';
    redis: 'up' | 'down';
  };
  checkedAt: string;
}

export interface AdminStatsDto {
  users: number;
  pushDevices: number;
  couponsByStatus: Record<string, number>;
  notifications: { pending: number; sent: number; cancelled: number };
  recentEvents: Array<{ type: string; couponId: string; createdAt: string }>;
  generatedAt: string;
}
