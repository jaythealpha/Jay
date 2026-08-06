import 'reflect-metadata';
import { Logger } from '@nestjs/common';
import { NestFactory } from '@nestjs/core';
import { DocumentBuilder, SwaggerModule } from '@nestjs/swagger';
import { AppModule } from './app.module';
import { loadEnv } from './config/env';

async function bootstrap(): Promise<void> {
  const env = loadEnv();
  const app = await NestFactory.create(AppModule);

  const openApiConfig = new DocumentBuilder()
    .setTitle('All Mighty Coupon API')
    .setDescription('Personal coupon wallet API — Milestone 0')
    .setVersion('0.1.0')
    .build();
  SwaggerModule.setup('docs', app, SwaggerModule.createDocument(app, openApiConfig));

  await app.listen(env.API_PORT);
  new Logger('Bootstrap').log(`API listening on port ${env.API_PORT} (${env.NODE_ENV})`);
}

void bootstrap();
