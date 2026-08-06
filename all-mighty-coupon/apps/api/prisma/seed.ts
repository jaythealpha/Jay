import { PrismaClient } from '@prisma/client';
import { hashBarcode } from '@amc/barcode-utils';
import { hashPassword } from '../src/auth/password';

/**
 * Development seed: one demo user with a handful of sample coupons so the
 * mobile app has real API data to render. Every coupon is tagged with
 * recognitionData.sampleData=true so sample rows are never mistaken for real
 * user data. Raw barcode values are NOT stored — only the duplicate-check
 * hash; encryption of real payloads arrives with the recognition pipeline.
 */
const prisma = new PrismaClient();

const DAY = 86_400_000;

async function main(): Promise<void> {
  // Dev-only demo credentials: demo@allmightycoupon.local / demo-password-1234
  const user = await prisma.user.upsert({
    where: { email: 'demo@allmightycoupon.local' },
    update: { passwordHash: hashPassword('demo-password-1234') },
    create: {
      email: 'demo@allmightycoupon.local',
      passwordHash: hashPassword('demo-password-1234'),
    },
  });

  const existing = await prisma.coupon.count({ where: { userId: user.id } });
  if (existing > 0) {
    console.log(`Seed skipped: demo user already has ${existing} coupons.`);
    return;
  }

  const now = Date.now();
  const samples = [
    {
      brandName: '스타벅스',
      productName: '아이스 카페 아메리카노 Tall',
      category: '카페',
      faceValueMinor: 4500,
      currency: 'KRW',
      status: 'EXPIRING_SOON' as const,
      expiresAt: new Date(now + 3 * DAY),
      barcodeHash: hashBarcode('SAMPLE-STARBUCKS-0001'),
      requiresReview: false,
    },
    {
      brandName: '배스킨라빈스',
      productName: '파인트 아이스크림',
      category: '디저트',
      faceValueMinor: 9800,
      currency: 'KRW',
      status: 'ACTIVE' as const,
      expiresAt: new Date(now + 45 * DAY),
      barcodeHash: hashBarcode('SAMPLE-BR-0002'),
      requiresReview: false,
    },
    {
      brandName: '이마트',
      productName: '모바일 금액권',
      category: '마트',
      faceValueMinor: 30000,
      currency: 'KRW',
      status: 'ACTIVE' as const,
      expiresAt: new Date(now + 120 * DAY),
      barcodeHash: hashBarcode('SAMPLE-EMART-0003'),
      requiresReview: false,
    },
    {
      brandName: '투썸플레이스',
      productName: '스트로베리 초콜릿 생크림',
      category: '카페',
      faceValueMinor: 37000,
      currency: 'KRW',
      status: 'NEEDS_REVIEW' as const,
      expiresAt: new Date(now + 20 * DAY),
      barcodeHash: hashBarcode('SAMPLE-TWOSOME-0004'),
      requiresReview: true,
    },
    {
      brandName: '교촌치킨',
      productName: '허니콤보',
      category: '치킨',
      faceValueMinor: 23000,
      currency: 'KRW',
      status: 'EXPIRED' as const,
      expiresAt: new Date(now - 10 * DAY),
      barcodeHash: hashBarcode('SAMPLE-KYOCHON-0005'),
      requiresReview: false,
    },
  ];

  for (const sample of samples) {
    const coupon = await prisma.coupon.create({
      data: {
        ...sample,
        userId: user.id,
        sourceType: 'MANUAL',
        recognitionData: { sampleData: true, seededAt: new Date(now).toISOString() },
      },
    });
    await prisma.couponEvent.create({
      data: {
        couponId: coupon.id,
        type: 'COUPON_CREATED',
        metadata: { sampleData: true, source: 'prisma-seed' },
      },
    });
  }

  console.log(`Seeded ${samples.length} sample coupons for demo user.`);
}

main()
  .catch((error) => {
    console.error('Seed failed:', error);
    process.exitCode = 1;
  })
  .finally(() => prisma.$disconnect());
