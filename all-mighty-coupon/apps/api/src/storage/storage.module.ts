import { Global, Module } from '@nestjs/common';
import { loadEnv } from '../config/env';
import { LocalStorageService } from './local-storage.service';
import { S3StorageService } from './s3-storage.service';
import { StorageService } from './storage.service';

@Global()
@Module({
  providers: [
    {
      provide: StorageService,
      useFactory: (): StorageService =>
        loadEnv().STORAGE_DRIVER === 's3' ? new S3StorageService() : new LocalStorageService(),
    },
  ],
  exports: [StorageService],
})
export class StorageModule {}
