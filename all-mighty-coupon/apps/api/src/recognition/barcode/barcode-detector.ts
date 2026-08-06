import { Injectable } from '@nestjs/common';
import { readFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';

export interface DetectedBarcode {
  value: string;
  format: string;
  confidence: number;
}

export abstract class BarcodeDetectorService {
  abstract detect(imageBytes: Buffer): Promise<DetectedBarcode | null>;
}

/**
 * ZXing (WASM) barcode/QR detection. The wasm binary is loaded from
 * node_modules explicitly because the default fetch-based loading does not
 * work in Node.
 */
@Injectable()
export class ZxingBarcodeDetector extends BarcodeDetectorService {
  private prepared = false;

  private async prepare(): Promise<void> {
    if (this.prepared) return;
    const { prepareZXingModule } = await import('zxing-wasm/reader');
    // Resolve the wasm binary relative to the CJS entry (dist/cjs/reader/…);
    // resolving package.json directly is blocked by the package's exports map.
    const entry = require.resolve('zxing-wasm/reader');
    const wasmBinary = await readFile(
      join(dirname(entry), '..', '..', 'reader', 'zxing_reader.wasm'),
    );
    prepareZXingModule({
      overrides: { wasmBinary: wasmBinary.buffer.slice(0) as ArrayBuffer },
    });
    this.prepared = true;
  }

  override async detect(imageBytes: Buffer): Promise<DetectedBarcode | null> {
    await this.prepare();
    const { readBarcodes } = await import('zxing-wasm/reader');
    const arrayBuffer = imageBytes.buffer.slice(
      imageBytes.byteOffset,
      imageBytes.byteOffset + imageBytes.byteLength,
    ) as ArrayBuffer;
    const results = await readBarcodes(arrayBuffer, {
      tryHarder: true,
      maxNumberOfSymbols: 1,
    });
    const first = results[0];
    if (!first || !first.isValid || first.text.length === 0) return null;
    return { value: first.text, format: first.format, confidence: 0.99 };
  }
}
