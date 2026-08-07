import {
  BadRequestException,
  ConflictException,
  Injectable,
  NotFoundException,
} from '@nestjs/common';
import type { Coupon, Listing, Prisma } from '@prisma/client';
import { calculateFeeMinor, canListCoupon, LISTING_REJECTION_MESSAGES } from '@amc/domain';
import type {
  ListingDto,
  MarketCouponDto,
  MarketListResponseDto,
  OrderDto,
} from '@amc/shared-types';
import { CouponEventsService } from '../events/coupon-events.service';
import { NotificationSchedulerService } from '../notifications/notification-scheduler.service';
import { PrismaService } from '../prisma/prisma.service';
import { PaymentProvider } from './payment-provider';

const DEFAULT_LIMIT = 50;
const MAX_LIMIT = 100;

type ListingWithCoupon = Listing & { coupon: Coupon };

/**
 * C2C coupon market (Milestone 4). The coupon stays with the seller while
 * listed (wallet actions locked); ownership moves atomically when a purchase
 * completes. Payment is the Mock provider — no real money moves.
 */
@Injectable()
export class MarketService {
  constructor(
    private readonly prisma: PrismaService,
    private readonly events: CouponEventsService,
    private readonly payment: PaymentProvider,
    private readonly notificationScheduler: NotificationSchedulerService,
  ) {}

  /** Live listing lock — wallet actions consult this before mutating. */
  async findActiveListing(couponId: string): Promise<Listing | null> {
    return this.prisma.listing.findFirst({ where: { couponId, status: 'LISTED' } });
  }

  async createListing(userId: string, couponId: string, priceMinor: number): Promise<ListingDto> {
    const coupon = await this.prisma.coupon.findUnique({ where: { id: couponId } });
    if (!coupon || coupon.userId !== userId) {
      throw new NotFoundException('쿠폰을 찾을 수 없습니다.');
    }
    const eligibility = canListCoupon(
      {
        status: coupon.status,
        requiresReview: coupon.requiresReview,
        hasBarcode: coupon.encryptedBarcode !== null,
        expiresAt: coupon.expiresAt,
      },
      priceMinor,
      new Date(),
    );
    if (!eligibility.ok) {
      throw new BadRequestException(LISTING_REJECTION_MESSAGES[eligibility.reason]);
    }
    if (await this.findActiveListing(couponId)) {
      throw new ConflictException('이미 판매 중인 쿠폰입니다.');
    }

    const listing = await this.prisma.listing.create({
      data: {
        couponId,
        sellerId: userId,
        priceMinor,
        feeMinor: calculateFeeMinor(priceMinor),
      },
      include: { coupon: true },
    });
    await this.events.record(couponId, 'LISTED_FOR_SALE', { priceMinor });
    return this.toListingDto(listing, userId);
  }

  async cancelListing(userId: string, listingId: string): Promise<void> {
    const listing = await this.prisma.listing.findUnique({ where: { id: listingId } });
    if (!listing || listing.sellerId !== userId) {
      throw new NotFoundException('판매 글을 찾을 수 없습니다.');
    }
    if (listing.status !== 'LISTED') {
      throw new BadRequestException('이미 종료된 판매 글입니다.');
    }
    await this.prisma.listing.update({
      where: { id: listingId },
      data: { status: 'CANCELLED' },
    });
    await this.events.record(listing.couponId, 'LISTING_CANCELLED');
  }

  async browse(
    userId: string,
    query: { q?: string; limit?: number },
  ): Promise<MarketListResponseDto> {
    const limit = Math.min(query.limit ?? DEFAULT_LIMIT, MAX_LIMIT);
    const q = query.q?.trim();
    const where: Prisma.ListingWhereInput = {
      status: 'LISTED',
      // Expired inventory never shows, even before the sweep flips it.
      coupon: {
        expiresAt: { gt: new Date() },
        ...(q
          ? {
              OR: [
                { brandName: { contains: q, mode: 'insensitive' } },
                { productName: { contains: q, mode: 'insensitive' } },
                { category: { contains: q, mode: 'insensitive' } },
              ],
            }
          : {}),
      },
    };

    const [rows, total] = await Promise.all([
      this.prisma.listing.findMany({
        where,
        include: { coupon: true },
        // Expiration First applies to the market too: shortest runway first.
        orderBy: [{ coupon: { expiresAt: 'asc' } }, { createdAt: 'desc' }],
        take: limit,
      }),
      this.prisma.listing.count({ where }),
    ]);
    return { items: rows.map((row) => this.toListingDto(row, userId)), total };
  }

  /**
   * Purchase: mock-charge the buyer, then atomically transfer ownership.
   * The seller's reminders are cancelled and the buyer gets a fresh plan.
   */
  async purchase(buyerId: string, listingId: string): Promise<OrderDto> {
    const listing = await this.prisma.listing.findUnique({
      where: { id: listingId },
      include: { coupon: true },
    });
    if (!listing || listing.status !== 'LISTED') {
      throw new NotFoundException('구매 가능한 판매 글이 아닙니다.');
    }
    if (listing.sellerId === buyerId) {
      throw new BadRequestException('내가 등록한 쿠폰은 구매할 수 없습니다.');
    }
    if (listing.coupon.expiresAt !== null && listing.coupon.expiresAt.getTime() < Date.now()) {
      throw new BadRequestException('유효기간이 지난 쿠폰은 구매할 수 없습니다.');
    }

    const order = await this.prisma.order.create({
      data: {
        listingId,
        buyerId,
        sellerId: listing.sellerId,
        priceMinor: listing.priceMinor,
        feeMinor: listing.feeMinor,
      },
    });

    const charge = await this.payment.charge({
      orderId: order.id,
      buyerId,
      amountMinor: listing.priceMinor,
    });
    if (!charge.approved) {
      await this.prisma.order.update({
        where: { id: order.id },
        data: { status: 'FAILED', paymentRef: charge.paymentRef },
      });
      throw new BadRequestException('결제가 승인되지 않았습니다.');
    }

    // Atomic hand-over: listing closes and ownership moves together, guarded
    // against a concurrent purchase by the LISTED-state condition.
    const transferred = await this.prisma.$transaction(async (tx) => {
      const closed = await tx.listing.updateMany({
        where: { id: listingId, status: 'LISTED' },
        data: { status: 'SOLD' },
      });
      if (closed.count === 0) return false;
      await tx.coupon.update({
        where: { id: listing.couponId },
        data: { userId: buyerId },
      });
      await tx.order.update({
        where: { id: order.id },
        data: { status: 'COMPLETED', paymentRef: charge.paymentRef },
      });
      return true;
    });
    if (!transferred) {
      await this.prisma.order.update({
        where: { id: order.id },
        data: { status: 'FAILED', paymentRef: charge.paymentRef },
      });
      throw new ConflictException('다른 구매자가 먼저 구매했습니다.');
    }

    await this.events.record(listing.couponId, 'OWNERSHIP_TRANSFERRED', {
      orderId: order.id,
      // Internal ids only — never emails.
      fromUserId: listing.sellerId,
      toUserId: buyerId,
    });
    // Reminders follow the coupon to its new owner.
    const coupon = await this.prisma.coupon.findUnique({ where: { id: listing.couponId } });
    if (coupon) {
      await this.notificationScheduler.rescheduleFor(coupon);
    }

    const completed = await this.prisma.order.findUniqueOrThrow({
      where: { id: order.id },
      include: { listing: { include: { coupon: true } } },
    });
    return this.toOrderDto(completed.listing.coupon, completed, buyerId);
  }

  async myOrders(userId: string): Promise<{ items: OrderDto[] }> {
    const rows = await this.prisma.order.findMany({
      where: { OR: [{ buyerId: userId }, { sellerId: userId }] },
      include: { listing: { include: { coupon: true } } },
      orderBy: { createdAt: 'desc' },
      take: 100,
    });
    return {
      items: rows.map((row) => this.toOrderDto(row.listing.coupon, row, userId)),
    };
  }

  private toMarketCoupon(coupon: Coupon): MarketCouponDto {
    return {
      brandName: coupon.brandName,
      productName: coupon.productName,
      category: coupon.category,
      faceValueMinor: coupon.faceValueMinor,
      expiresAt: coupon.expiresAt ? coupon.expiresAt.toISOString() : null,
    };
  }

  private toListingDto(listing: ListingWithCoupon, viewerId: string): ListingDto {
    return {
      id: listing.id,
      priceMinor: listing.priceMinor,
      feeMinor: listing.feeMinor,
      status: listing.status,
      mine: listing.sellerId === viewerId,
      coupon: this.toMarketCoupon(listing.coupon),
      createdAt: listing.createdAt.toISOString(),
    };
  }

  private toOrderDto(
    coupon: Coupon,
    order: {
      id: string;
      buyerId: string;
      priceMinor: number;
      feeMinor: number;
      status: 'CREATED' | 'COMPLETED' | 'FAILED';
      createdAt: Date;
    },
    viewerId: string,
  ): OrderDto {
    return {
      id: order.id,
      role: order.buyerId === viewerId ? 'BUYER' : 'SELLER',
      priceMinor: order.priceMinor,
      feeMinor: order.feeMinor,
      status: order.status,
      coupon: this.toMarketCoupon(coupon),
      createdAt: order.createdAt.toISOString(),
    };
  }
}
