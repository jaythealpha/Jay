import 'package:amc_mobile/core/errors/app_exception.dart';
import 'package:amc_mobile/core/storage/coupon_cache.dart';
import 'package:amc_mobile/features/coupon_wallet/data/coupon_api.dart';
import 'package:amc_mobile/features/coupon_wallet/domain/coupon_repository.dart';
import 'package:amc_mobile/features/coupon_wallet/domain/wallet_query.dart';
import 'package:amc_mobile/shared/models/coupon_summary.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

class MockCouponApi extends Mock implements CouponApi {}

class MockCouponCache extends Mock implements CouponCache {}

CouponSummary coupon(String id, {String? brand, String status = 'ACTIVE'}) {
  return CouponSummary.fromJson(<String, dynamic>{
    'id': id,
    'brandName': brand ?? '스타벅스',
    'status': status,
    'createdAt': '2026-08-01T00:00:00.000Z',
  });
}

void main() {
  setUpAll(() {
    registerFallbackValue(<CouponSummary>[]);
    registerFallbackValue(DateTime(2026));
    registerFallbackValue(const WalletQuery());
  });

  test('network success returns live data and updates the cache (default query)', () async {
    final api = MockCouponApi();
    final cache = MockCouponCache();
    when(() => api.fetchCoupons(query: any(named: 'query')))
        .thenAnswer((_) async => [coupon('c1')]);
    when(() => cache.saveCoupons(any(), any())).thenAnswer((_) async {});

    final repo = CouponRepository(api, cache);
    final result = await repo.getCoupons(now: () => DateTime.utc(2026, 8, 6));

    expect(result.fromCache, false);
    expect(result.coupons.single.id, 'c1');
    verify(() => cache.saveCoupons(any(), DateTime.utc(2026, 8, 6))).called(1);
  });

  test('filtered queries do not overwrite the full-list cache', () async {
    final api = MockCouponApi();
    final cache = MockCouponCache();
    when(() => api.fetchCoupons(query: any(named: 'query')))
        .thenAnswer((_) async => [coupon('c1')]);

    await CouponRepository(api, cache)
        .getCoupons(query: const WalletQuery(status: 'REDEEMED'));

    verifyNever(() => cache.saveCoupons(any(), any()));
  });

  test('offline: cached snapshot is served with local filtering applied', () async {
    final api = MockCouponApi();
    final cache = MockCouponCache();
    when(() => api.fetchCoupons(query: any(named: 'query')))
        .thenThrow(const NetworkException());
    when(() => cache.loadCoupons()).thenAnswer(
      (_) async => CachedCoupons(
        coupons: [
          coupon('c1', brand: '스타벅스', status: 'ACTIVE'),
          coupon('c2', brand: '이마트', status: 'REDEEMED'),
        ],
        syncedAt: DateTime.utc(2026, 8, 5),
      ),
    );

    final result = await CouponRepository(api, cache)
        .getCoupons(query: const WalletQuery(status: 'REDEEMED'));

    expect(result.fromCache, true);
    expect(result.coupons.single.id, 'c2');
  });

  test('network failure with an empty cache rethrows the user-facing error', () async {
    final api = MockCouponApi();
    final cache = MockCouponCache();
    when(() => api.fetchCoupons(query: any(named: 'query')))
        .thenThrow(const NetworkException());
    when(() => cache.loadCoupons()).thenAnswer((_) async => null);

    expect(
      () => CouponRepository(api, cache).getCoupons(),
      throwsA(isA<NetworkException>()),
    );
  });

  test('session expiry is never masked as offline data', () async {
    final api = MockCouponApi();
    final cache = MockCouponCache();
    when(() => api.fetchCoupons(query: any(named: 'query')))
        .thenThrow(const SessionExpiredException());

    expect(
      () => CouponRepository(api, cache).getCoupons(),
      throwsA(isA<SessionExpiredException>()),
    );
    verifyNever(() => cache.loadCoupons());
  });
}
