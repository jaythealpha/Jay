import { Global, Module } from '@nestjs/common';
import { CouponEventsService } from './coupon-events.service';

@Global()
@Module({
  providers: [CouponEventsService],
  exports: [CouponEventsService],
})
export class CouponEventsModule {}
