import { Injectable, OnModuleDestroy } from '@nestjs/common';
import Redis from 'ioredis';
import { loadEnv } from '../config/env';

/**
 * Redis is health-check-only in Milestone 0; the BullMQ recognition queue
 * (Milestone 1) will reuse this connection configuration.
 */
@Injectable()
export class RedisService implements OnModuleDestroy {
  private readonly client: Redis;

  constructor() {
    this.client = new Redis(loadEnv().REDIS_URL, {
      lazyConnect: true,
      maxRetriesPerRequest: 1,
    });
  }

  async ping(): Promise<boolean> {
    try {
      if (this.client.status === 'wait' || this.client.status === 'end') {
        await this.client.connect();
      }
      return (await this.client.ping()) === 'PONG';
    } catch {
      return false;
    }
  }

  async onModuleDestroy(): Promise<void> {
    this.client.disconnect();
  }
}
