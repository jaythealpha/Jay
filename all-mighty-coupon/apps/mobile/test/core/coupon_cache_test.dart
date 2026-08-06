import 'package:amc_mobile/core/storage/coupon_cache.dart';
import 'package:amc_mobile/shared/models/coupon_summary.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  final coupon = CouponSummary.fromJson(<String, dynamic>{
    'id': 'c1',
    'brandName': '스타벅스',
    'productName': '아메리카노',
    'status': 'ACTIVE',
    'expiresAt': '2026-12-31T00:00:00.000Z',
    'createdAt': '2026-08-01T00:00:00.000Z',
    'requiresReview': false,
    'sourceType': 'MANUAL',
  });

  setUp(() {
    SharedPreferences.setMockInitialValues(<String, Object>{});
  });

  test('save then load round-trips coupons and sync time', () async {
    final cache = SharedPrefsCouponCache();
    final syncedAt = DateTime.utc(2026, 8, 6, 12);

    await cache.saveCoupons([coupon], syncedAt);
    final loaded = await cache.loadCoupons();

    expect(loaded, isNotNull);
    expect(loaded!.coupons.single.id, 'c1');
    expect(loaded.coupons.single.brandName, '스타벅스');
    expect(loaded.syncedAt, syncedAt);
  });

  test('load returns null before anything was cached', () async {
    expect(await SharedPrefsCouponCache().loadCoupons(), isNull);
  });

  test('clear removes the snapshot', () async {
    final cache = SharedPrefsCouponCache();
    await cache.saveCoupons([coupon], DateTime.utc(2026));
    await cache.clear();
    expect(await cache.loadCoupons(), isNull);
  });
}
