import sharp from 'sharp';
import { ImageProcessor, UnsupportedImageError } from './image-processor';

describe('ImageProcessor', () => {
  const processor = new ImageProcessor();

  async function testPng(width = 800, height = 600): Promise<Buffer> {
    return sharp({ create: { width, height, channels: 3, background: '#ffffff' } })
      .png()
      .toBuffer();
  }

  it('produces normalized and thumbnail JPEGs within size caps', async () => {
    const result = await processor.process(await testPng(2400, 1200));
    const normalizedMeta = await sharp(result.normalized).metadata();
    const thumbMeta = await sharp(result.thumbnail).metadata();
    expect(normalizedMeta.format).toBe('jpeg');
    expect(Math.max(normalizedMeta.width ?? 0, normalizedMeta.height ?? 0)).toBeLessThanOrEqual(
      1600,
    );
    expect(Math.max(thumbMeta.width ?? 0, thumbMeta.height ?? 0)).toBeLessThanOrEqual(400);
    expect(result.sourceFormat).toBe('png');
    expect(result.width).toBe(2400);
  });

  it('rejects non-image bytes as a typed error', async () => {
    await expect(processor.process(Buffer.from('definitely not an image'))).rejects.toThrow(
      UnsupportedImageError,
    );
  });

  it('rejects images below the minimum useful size', async () => {
    await expect(processor.process(await testPng(32, 32))).rejects.toThrow(UnsupportedImageError);
  });
});
