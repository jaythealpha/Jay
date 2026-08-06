import { Processor, WorkerHost } from '@nestjs/bullmq';
import { Job } from 'bullmq';
import { RECOGNITION_QUEUE, RecognitionJobData } from './recognition.queue';
import { RecognitionService } from './recognition.service';

/**
 * Worker side of the pipeline. Co-hosted in the API process for Milestone 1
 * (single deployable, spec architecture: Modular Monolith); can move to a
 * dedicated worker entrypoint without code changes when load requires it.
 */
@Processor(RECOGNITION_QUEUE)
export class RecognitionProcessor extends WorkerHost {
  constructor(private readonly recognitionService: RecognitionService) {
    super();
  }

  override async process(job: Job): Promise<void> {
    const data = job.data as RecognitionJobData;
    await this.recognitionService.process(data.couponId);
  }
}
