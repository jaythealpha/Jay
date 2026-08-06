import { Injectable } from '@nestjs/common';
import sharp, { type Metadata } from 'sharp';

export class UnsupportedImageError extends Error {
  constructor(detail: string) {
    super(detail);
    this.name = 'UnsupportedImageError';
  }
}

export interface ProcessedImages {
  /** EXIF-rotated, capped at 1600px, JPEG — input for barcode/OCR stages. */
  normalized: Buffer;
  thumbnail: Buffer;
  width: number;
  height: number;
  sourceFormat: string;
}

const SUPPORTED_FORMATS = new Set(['jpeg', 'png', 'webp']);
const MAX_DIMENSION = 1600;
const THUMBNAIL_DIMENSION = 400;
const MIN_DIMENSION = 64;

/**
 * Stage 1–2 of the pipeline: validate + normalize. The ORIGINAL asset is
 * never modified — normalization always produces new derived buffers.
 */
@Injectable()
export class ImageProcessor {
  async process(original: Buffer): Promise<ProcessedImages> {
    let metadata: Metadata;
    try {
      metadata = await sharp(original).metadata();
    } catch {
      throw new UnsupportedImageError('not a decodable image');
    }

    const format = metadata.format ?? 'unknown';
    if (!SUPPORTED_FORMATS.has(format)) {
      throw new UnsupportedImageError(`unsupported format: ${format}`);
    }
    const width = metadata.width ?? 0;
    const height = metadata.height ?? 0;
    if (width < MIN_DIMENSION || height < MIN_DIMENSION) {
      throw new UnsupportedImageError(`image too small: ${width}x${height}`);
    }

    const base = sharp(original).rotate(); // honor EXIF orientation
    const [normalized, thumbnail] = await Promise.all([
      base
        .clone()
        .resize({
          width: MAX_DIMENSION,
          height: MAX_DIMENSION,
          fit: 'inside',
          withoutEnlargement: true,
        })
        .jpeg({ quality: 90 })
        .toBuffer(),
      base
        .clone()
        .resize({
          width: THUMBNAIL_DIMENSION,
          height: THUMBNAIL_DIMENSION,
          fit: 'inside',
          withoutEnlargement: true,
        })
        .jpeg({ quality: 80 })
        .toBuffer(),
    ]);

    return { normalized, thumbnail, width, height, sourceFormat: format };
  }
}
