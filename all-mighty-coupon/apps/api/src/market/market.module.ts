import { Module } from '@nestjs/common';
import { MarketController } from './market.controller';
import { MarketService } from './market.service';
import { MockPaymentProvider } from './mock-payment.provider';
import { PaymentProvider } from './payment-provider';

@Module({
  controllers: [MarketController],
  providers: [
    MarketService,
    // Real PG integration replaces this binding behind the same boundary —
    // and only with explicit approval (project rule: no external paid
    // services without sign-off).
    { provide: PaymentProvider, useClass: MockPaymentProvider },
  ],
  exports: [MarketService],
})
export class MarketModule {}
