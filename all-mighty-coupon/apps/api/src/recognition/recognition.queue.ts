import { InjectQueue } from '@nestjs/bullmq';
import { Injectable } from '@nestjs/common';
import { Queue } from 'bullmq';

export const RECOGNITION_QUEUE = 'coupon-recognition';

export interface RecognitionJobData {
  couponId: string;
}

/**
 * Producer side of the async pipeline: the upload request only enqueues —
 * analysis never runs synchronously inside an API request (spec §7).
 */
@Injectable()
export class RecognitionQueueService {
  constructor(@InjectQueue(RECOGNITION_QUEUE) private readonly queue: Queue) {}

  async enqueue(couponId: string): Promise<void> {
    await this.queue.add('process', { couponId } satisfies RecognitionJobData, {
      attempts: 3,
      backoff: { type: 'exponential', delay: 2000 },
      removeOnComplete: 100,
      removeOnFail: 500,
    });
  }
}
