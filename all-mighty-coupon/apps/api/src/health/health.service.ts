import { Injectable } from '@nestjs/common';
import type { HealthComponentStatus, HealthResponseDto } from '@amc/shared-types';
import { PrismaService } from '../prisma/prisma.service';
import { RedisService } from '../redis/redis.service';

@Injectable()
export class HealthService {
  constructor(
    private readonly prisma: PrismaService,
    private readonly redis: RedisService,
  ) {}

  async check(): Promise<HealthResponseDto> {
    const [database, redis] = await Promise.all([this.checkDatabase(), this.checkRedis()]);
    return {
      status: database === 'up' && redis === 'up' ? 'ok' : 'degraded',
      components: { database, redis },
      checkedAt: new Date().toISOString(),
    };
  }

  private async checkDatabase(): Promise<HealthComponentStatus> {
    try {
      await this.prisma.$queryRaw`SELECT 1`;
      return 'up';
    } catch {
      return 'down';
    }
  }

  private async checkRedis(): Promise<HealthComponentStatus> {
    return (await this.redis.ping()) ? 'up' : 'down';
  }
}
