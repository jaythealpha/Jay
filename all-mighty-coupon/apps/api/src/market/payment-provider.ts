/**
 * Payment boundary (Milestone 4). NO real payment gateway is integrated —
 * per the project rules, external paid services are never signed up for or
 * charged without explicit approval. The Mock provider approves instantly
 * and stamps a MOCK- reference so simulated payments can never be mistaken
 * for settled money.
 */
export interface ChargeRequest {
  orderId: string;
  buyerId: string;
  amountMinor: number;
}

export interface ChargeResult {
  approved: boolean;
  /** Provider transaction reference; MOCK- prefixed for the mock provider. */
  paymentRef: string;
}

export abstract class PaymentProvider {
  abstract readonly providerName: string;
  abstract charge(request: ChargeRequest): Promise<ChargeResult>;
}
