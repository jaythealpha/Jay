import { Module } from '@nestjs/common';
import { RecognitionModule } from '../recognition/recognition.module';
import { CouponsController } from './coupons.controller';
import { CouponsService } from './coupons.service';

@Module({
  imports: [RecognitionModule],
  controllers: [CouponsController],
  providers: [CouponsService],
})
export class CouponsModule {}
