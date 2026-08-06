import { Injectable, Logger } from '@nestjs/common';
import { PushMessage, PushResult, PushSender } from './push-sender';

/**
 * Credential-less fallback: the in-app feed remains the delivery channel and
 * this sender only logs that a push WOULD have gone out (token counts only —
 * never token values, spec §17). Selected when FIREBASE_SERVICE_ACCOUNT_JSON
 * is not configured.
 */
@Injectable()
export class NoopPushSender extends PushSender {
  override readonly channelName = 'noop';
  private readonly logger = new Logger(NoopPushSender.name);

  /** Test hook: records of would-be sends (message content, no tokens). */
  readonly delivered: Array<{ title: string; body: string; tokenCount: number }> = [];

  override async send(message: PushMessage): Promise<PushResult> {
    this.delivered.push({
      title: message.title,
      body: message.body,
      tokenCount: message.tokens.length,
    });
    this.logger.log(
      `push skipped (no FCM credentials): "${message.body}" → ${message.tokens.length} device(s)`,
    );
    return { successCount: 0, invalidTokens: [] };
  }
}
