import { Global, Module } from '@nestjs/common';
import { loadEnv } from '../config/env';
import { DevicesController } from './devices.controller';
import { FcmPushSender } from './fcm-push-sender';
import { NoopPushSender } from './noop-push-sender';
import { PushSender } from './push-sender';

@Global()
@Module({
  controllers: [DevicesController],
  providers: [
    {
      provide: PushSender,
      useFactory: (): PushSender => {
        const credentials = loadEnv().FIREBASE_SERVICE_ACCOUNT_JSON;
        return credentials ? new FcmPushSender(credentials) : new NoopPushSender();
      },
    },
  ],
  exports: [PushSender],
})
export class PushModule {}
