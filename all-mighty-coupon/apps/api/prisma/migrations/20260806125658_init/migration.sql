-- CreateEnum
CREATE TYPE "CouponStatus" AS ENUM ('PROCESSING', 'NEEDS_REVIEW', 'ACTIVE', 'EXPIRING_SOON', 'EXPIRED', 'REDEEMED', 'ARCHIVED', 'INVALID');

-- CreateEnum
CREATE TYPE "CouponSourceType" AS ENUM ('CAMERA', 'PHOTO_LIBRARY', 'SHARE_EXTENSION', 'FILE_UPLOAD', 'MANUAL');

-- CreateEnum
CREATE TYPE "CouponAssetType" AS ENUM ('ORIGINAL', 'NORMALIZED', 'THUMBNAIL', 'BARCODE_CROP');

-- CreateEnum
CREATE TYPE "CouponEventType" AS ENUM ('COUPON_CREATED', 'IMAGE_UPLOADED', 'BARCODE_DETECTED', 'OCR_COMPLETED', 'COUPON_PARSED', 'USER_CONFIRMED', 'USER_EDITED', 'STATUS_CHANGED', 'NOTIFICATION_SCHEDULED', 'NOTIFICATION_SENT', 'BARCODE_VIEWED', 'MARKED_REDEEMED', 'RESTORED_TO_ACTIVE', 'ARCHIVED', 'DELETED');

-- CreateTable
CREATE TABLE "User" (
    "id" TEXT NOT NULL,
    "email" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "User_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Coupon" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "brandName" TEXT,
    "productName" TEXT,
    "category" TEXT,
    "faceValueMinor" INTEGER,
    "currency" TEXT,
    "status" "CouponStatus" NOT NULL DEFAULT 'PROCESSING',
    "issuedAt" TIMESTAMP(3),
    "expiresAt" TIMESTAMP(3),
    "usageLocationText" TEXT,
    "usageConditions" TEXT,
    "barcodeType" TEXT,
    "encryptedBarcode" TEXT,
    "barcodeHash" TEXT,
    "sourceType" "CouponSourceType" NOT NULL,
    "requiresReview" BOOLEAN NOT NULL DEFAULT true,
    "recognitionData" JSONB,
    "redeemedAt" TIMESTAMP(3),
    "archivedAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "Coupon_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "CouponAsset" (
    "id" TEXT NOT NULL,
    "couponId" TEXT NOT NULL,
    "type" "CouponAssetType" NOT NULL,
    "storageKey" TEXT NOT NULL,
    "mimeType" TEXT NOT NULL,
    "width" INTEGER,
    "height" INTEGER,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "CouponAsset_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "CouponEvent" (
    "id" TEXT NOT NULL,
    "couponId" TEXT NOT NULL,
    "type" "CouponEventType" NOT NULL,
    "metadata" JSONB,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "CouponEvent_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "User_email_key" ON "User"("email");

-- CreateIndex
CREATE INDEX "Coupon_userId_idx" ON "Coupon"("userId");

-- CreateIndex
CREATE INDEX "Coupon_expiresAt_idx" ON "Coupon"("expiresAt");

-- CreateIndex
CREATE INDEX "Coupon_status_idx" ON "Coupon"("status");

-- CreateIndex
CREATE INDEX "Coupon_barcodeHash_idx" ON "Coupon"("barcodeHash");

-- CreateIndex
CREATE INDEX "CouponAsset_couponId_idx" ON "CouponAsset"("couponId");

-- CreateIndex
CREATE INDEX "CouponEvent_couponId_createdAt_idx" ON "CouponEvent"("couponId", "createdAt");

-- AddForeignKey
ALTER TABLE "Coupon" ADD CONSTRAINT "Coupon_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "CouponAsset" ADD CONSTRAINT "CouponAsset_couponId_fkey" FOREIGN KEY ("couponId") REFERENCES "Coupon"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "CouponEvent" ADD CONSTRAINT "CouponEvent_couponId_fkey" FOREIGN KEY ("couponId") REFERENCES "Coupon"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
