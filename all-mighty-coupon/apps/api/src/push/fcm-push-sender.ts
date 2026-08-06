import { Injectable, Logger } from '@nestjs/common';
import { PushMessage, PushResult, PushSender } from './push-sender';

/**
 * Firebase Cloud Messaging sender. Requires FIREBASE_SERVICE_ACCOUNT_JSON
 * (base64-encoded service account) — the module factory only selects this
 * sender when credentials are configured. UNVERIFIED against a live Firebase
 * project in this repository; verified paths are covered by NoopPushSender.
 */
@Injectable()
export class FcmPushSender extends PushSender {
  override readonly channelName = 'fcm';
  private readonly logger = new Logger(FcmPushSender.name);
  private app: import('firebase-admin/app').App | null = null;

  constructor(private readonly serviceAccountBase64: string) {
    super();
  }

  private async getApp(): Promise<import('firebase-admin/app').App> {
    if (this.app) return this.app;
    const { initializeApp, cert, getApps } = await import('firebase-admin/app');
    const existing = getApps();
    if (existing.length > 0 && existing[0]) {
      this.app = existing[0];
      return this.app;
    }
    const credentials = JSON.parse(
      Buffer.from(this.serviceAccountBase64, 'base64').toString('utf8'),
    ) as Record<string, string>;
    this.app = initializeApp({ credential: cert(credentials) });
    return this.app;
  }

  override async send(message: PushMessage): Promise<PushResult> {
    if (message.tokens.length === 0) return { successCount: 0, invalidTokens: [] };

    const { getMessaging } = await import('firebase-admin/messaging');
    const messaging = getMessaging(await this.getApp());
    const response = await messaging.sendEachForMulticast({
      tokens: message.tokens,
      notification: { title: message.title, body: message.body },
      data: message.data,
    });

    const invalidTokens: string[] = [];
    response.responses.forEach((result, index) => {
      const code = result.error?.code;
      if (
        code === 'messaging/registration-token-not-registered' ||
        code === 'messaging/invalid-registration-token'
      ) {
        const token = message.tokens[index];
        if (token) invalidTokens.push(token);
      }
    });

    this.logger.log(
      `FCM push: ${response.successCount}/${message.tokens.length} delivered` +
        (invalidTokens.length > 0 ? `, ${invalidTokens.length} tokens pruned` : ''),
    );
    return { successCount: response.successCount, invalidTokens };
  }
}
