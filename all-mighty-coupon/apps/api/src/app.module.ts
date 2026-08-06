import { BullModule } from '@nestjs/bullmq';
import { Module } from '@nestjs/common';
import { APP_FILTER, APP_INTERCEPTOR } from '@nestjs/core';
import { AuthModule } from './auth/auth.module';
import { GlobalExceptionFilter } from './common/filters/http-exception.filter';
import { LoggingInterceptor } from './common/logging/logging.interceptor';
import { loadEnv } from './config/env';
import { CouponEventsModule } from './events/coupon-events.module';
import { CouponsModule } from './coupons/coupons.module';
import { HealthModule } from './health/health.module';
import { HomeModule } from './home/home.module';
import { MaintenanceModule } from './maintenance/maintenance.module';
import { NotificationsModule } from './notifications/notifications.module';
import { PrismaModule } from './prisma/prisma.module';
import { RedisModule } from './redis/redis.module';
import { StorageModule } from './storage/storage.module';

function redisConnection(): { host: string; port: number } {
  const url = new URL(loadEnv().REDIS_URL);
  return { host: url.hostname, port: Number(url.port || 6379) };
}

@Module({
  imports: [
    BullModule.forRoot({ connection: redisConnection() }),
    AuthModule,
    PrismaModule,
    RedisModule,
    StorageModule,
    CouponEventsModule,
    NotificationsModule,
    MaintenanceModule,
    HealthModule,
    HomeModule,
    CouponsModule,
  ],
  providers: [
    { provide: APP_FILTER, useClass: GlobalExceptionFilter },
    { provide: APP_INTERCEPTOR, useClass: LoggingInterceptor },
  ],
})
export class AppModule {}
