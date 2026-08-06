import 'package:amc_mobile/shared/models/coupon_summary.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  final json = <String, dynamic>{
    'id': 'c1',
    'brandName': '스타벅스',
    'productName': '아메리카노 Tall',
    'category': '카페',
    'faceValueMinor': 4500,
    'currency': 'KRW',
    'status': 'EXPIRING_SOON',
    'expiresAt': '2026-08-09T12:00:00.000Z',
    'requiresReview': false,
    'sourceType': 'MANUAL',
    'createdAt': '2026-08-01T00:00:00.000Z',
  };

  test('fromJson parses the API payload', () {
    final coupon = CouponSummary.fromJson(json);
    expect(coupon.brandName, '스타벅스');
    expect(coupon.faceValueMinor, 4500);
    expect(coupon.expiresAt, DateTime.parse('2026-08-09T12:00:00.000Z'));
    expect(coupon.requiresReview, false);
  });

  test('null expiration and unknown fields stay null / fall back safely', () {
    final coupon = CouponSummary.fromJson(<String, dynamic>{
      'id': 'c2',
      'createdAt': '2026-08-01T00:00:00.000Z',
    });
    expect(coupon.expiresAt, isNull);
    expect(coupon.brandName, isNull);
    expect(coupon.status, 'PROCESSING');
    expect(coupon.requiresReview, true);
  });

  test('toJson -> fromJson round-trips', () {
    final original = CouponSummary.fromJson(json);
    final roundTripped = CouponSummary.fromJson(original.toJson());
    expect(roundTripped.id, original.id);
    expect(roundTripped.expiresAt, original.expiresAt);
    expect(roundTripped.faceValueMinor, original.faceValueMinor);
  });
}
