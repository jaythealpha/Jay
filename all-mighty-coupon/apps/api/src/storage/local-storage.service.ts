import { Injectable } from '@nestjs/common';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { dirname, join, normalize } from 'node:path';
import { loadEnv } from '../config/env';
import { PutObjectInput, StorageService } from './storage.service';

/**
 * Keyless fallback driver: stores objects under LOCAL_STORAGE_DIR. "Signed
 * URLs" are plain file:// URIs — good enough for local development and
 * hermetic tests, never for production (ADR-0004).
 */
@Injectable()
export class LocalStorageService extends StorageService {
  private readonly baseDir: string;

  constructor() {
    super();
    this.baseDir = loadEnv().LOCAL_STORAGE_DIR;
  }

  private resolve(key: string): string {
    const path = normalize(join(this.baseDir, key));
    if (!path.startsWith(normalize(this.baseDir))) {
      throw new Error(`Invalid storage key: ${key}`);
    }
    return path;
  }

  override async ensureReady(): Promise<void> {
    await mkdir(this.baseDir, { recursive: true });
  }

  override async putObject({ key, body }: PutObjectInput): Promise<void> {
    const path = this.resolve(key);
    await mkdir(dirname(path), { recursive: true });
    await writeFile(path, body);
  }

  override async getObject(key: string): Promise<Buffer> {
    return readFile(this.resolve(key));
  }

  override async getSignedUrl(key: string): Promise<string> {
    return `file://${this.resolve(key)}`;
  }
}
