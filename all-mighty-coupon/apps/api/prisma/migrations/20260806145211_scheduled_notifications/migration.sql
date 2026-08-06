-- CreateEnum
CREATE TYPE "ScheduledNotificationStatus" AS ENUM ('PENDING', 'SENT', 'CANCELLED');

-- CreateTable
CREATE TABLE "ScheduledNotification" (
    "id" TEXT NOT NULL,
    "couponId" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "offsetDays" INTEGER NOT NULL,
    "fireAt" TIMESTAMP(3) NOT NULL,
    "status" "ScheduledNotificationStatus" NOT NULL DEFAULT 'PENDING',
    "message" TEXT,
    "sentAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "ScheduledNotification_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "ScheduledNotification_status_fireAt_idx" ON "ScheduledNotification"("status", "fireAt");

-- CreateIndex
CREATE INDEX "ScheduledNotification_couponId_idx" ON "ScheduledNotification"("couponId");

-- CreateIndex
CREATE INDEX "ScheduledNotification_userId_status_sentAt_idx" ON "ScheduledNotification"("userId", "status", "sentAt");

-- AddForeignKey
ALTER TABLE "ScheduledNotification" ADD CONSTRAINT "ScheduledNotification_couponId_fkey" FOREIGN KEY ("couponId") REFERENCES "Coupon"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
