import { BullModule } from '@nestjs/bullmq';
import { Module } from '@nestjs/common';
import { CryptoModule } from '../crypto/crypto.module';
import { BarcodeDetectorService, ZxingBarcodeDetector } from './barcode/barcode-detector';
import { ImageProcessor } from './image/image-processor';
import { MockOcrProvider } from './ocr/mock-ocr.provider';
import { OcrProvider } from './ocr/ocr-provider';
import { RECOGNITION_QUEUE, RecognitionQueueService } from './recognition.queue';
import { RecognitionProcessor } from './recognition.processor';
import { RecognitionService } from './recognition.service';

@Module({
  imports: [BullModule.registerQueue({ name: RECOGNITION_QUEUE }), CryptoModule],
  providers: [
    ImageProcessor,
    { provide: BarcodeDetectorService, useClass: ZxingBarcodeDetector },
    // OCR_PROVIDER currently only supports 'mock' (see config/env.ts); real
    // providers get registered in this factory as they are integrated.
    { provide: OcrProvider, useClass: MockOcrProvider },
    RecognitionService,
    RecognitionQueueService,
    RecognitionProcessor,
  ],
  exports: [RecognitionQueueService],
})
export class RecognitionModule {}
