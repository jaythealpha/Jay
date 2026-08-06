import { Module } from '@nestjs/common';
import { BarcodeCryptoService } from './barcode-crypto.service';

@Module({
  providers: [BarcodeCryptoService],
  exports: [BarcodeCryptoService],
})
export class CryptoModule {}
