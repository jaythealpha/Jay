import 'package:amc_mobile/core/errors/app_exception.dart';
import 'package:amc_mobile/core/storage/coupon_cache.dart';
import 'package:amc_mobile/features/coupon_wallet/data/coupon_api.dart';
import 'package:amc_mobile/features/coupon_wallet/domain/coupon_repository.dart';
import 'package:amc_mobile/shared/models/coupon_summary.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

class MockCouponApi extends Mock implements CouponApi {}

class MockCouponCache extends Mock implements CouponCache {}

void main() {
  setUpAll(() {
    registerFallbackValue(<CouponSummary>[]);
    registerFallbackValue(DateTime(2026));
  });

  final coupon = CouponSummary.fromJson(<String, dynamic>{
    'id': 'c1',
    'brandName': '스타벅스',
    'status': 'ACTIVE',
    'createdAt': '2026-08-01T00:00:00.000Z',
  });

  test('network success returns live data and updates the cache', () async {
    final api = MockCouponApi();
    final cache = MockCouponCache();
    when(() => api.fetchCoupons()).thenAnswer((_) async => [coupon]);
    when(() => cache.saveCoupons(any(), any())).thenAnswer((_) async {});

    final repo = CouponRepository(api, cache);
    final result = await repo.getCoupons(now: () => DateTime.utc(2026, 8, 6));

    expect(result.fromCache, false);
    expect(result.coupons.single.id, 'c1');
    verify(() => cache.saveCoupons([coupon], DateTime.utc(2026, 8, 6))).called(1);
  });

  test('network failure falls back to the cached snapshot, marked as cached', () async {
    final api = MockCouponApi();
    final cache = MockCouponCache();
    when(() => api.fetchCoupons()).thenThrow(const NetworkException());
    when(() => cache.loadCoupons()).thenAnswer(
      (_) async => CachedCoupons(coupons: [coupon], syncedAt: DateTime.utc(2026, 8, 5)),
    );

    final result = await CouponRepository(api, cache).getCoupons();

    expect(result.fromCache, true);
    expect(result.syncedAt, DateTime.utc(2026, 8, 5));
    expect(result.coupons.single.id, 'c1');
  });

  test('network failure with an empty cache rethrows the user-facing error', () async {
    final api = MockCouponApi();
    final cache = MockCouponCache();
    when(() => api.fetchCoupons()).thenThrow(const NetworkException());
    when(() => cache.loadCoupons()).thenAnswer((_) async => null);

    expect(
      () => CouponRepository(api, cache).getCoupons(),
      throwsA(isA<NetworkException>()),
    );
  });
}
