import { Module } from '@nestjs/common';
import { CryptoModule } from '../crypto/crypto.module';
import { RecognitionModule } from '../recognition/recognition.module';
import { CouponsController } from './coupons.controller';
import { CouponsService } from './coupons.service';

@Module({
  imports: [RecognitionModule, CryptoModule],
  controllers: [CouponsController],
  providers: [CouponsService],
})
export class CouponsModule {}
