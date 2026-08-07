import { Injectable, Logger } from '@nestjs/common';
import { randomUUID } from 'node:crypto';
import { ChargeRequest, ChargeResult, PaymentProvider } from './payment-provider';

@Injectable()
export class MockPaymentProvider extends PaymentProvider {
  override readonly providerName = 'mock';
  private readonly logger = new Logger(MockPaymentProvider.name);

  override async charge(request: ChargeRequest): Promise<ChargeResult> {
    // Amounts only — no card data exists in this system at all.
    this.logger.log(`MOCK charge approved: order=${request.orderId} amount=${request.amountMinor}`);
    return { approved: true, paymentRef: `MOCK-${randomUUID()}` };
  }
}
