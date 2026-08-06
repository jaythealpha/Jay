/**
 * Push channel boundary. The dispatcher hands over fully rendered messages;
 * senders never see coupon internals beyond what the notification carries.
 */
export interface PushMessage {
  /** FCM registration tokens for one user's devices. */
  tokens: string[];
  title: string;
  body: string;
  /** Deep-link payload — the app opens /coupon/:couponId. */
  data: { couponId: string; notificationId: string };
}

export interface PushResult {
  successCount: number;
  /** Tokens the provider reported as permanently invalid — prune these. */
  invalidTokens: string[];
}

export abstract class PushSender {
  abstract readonly channelName: string;
  abstract send(message: PushMessage): Promise<PushResult>;
}
