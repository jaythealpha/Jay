import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/errors/app_exception.dart';
import '../../../core/storage/coupon_cache.dart';
import '../../../shared/models/coupon_summary.dart';
import '../data/coupon_api.dart';

class CouponListResult {
  const CouponListResult({
    required this.coupons,
    required this.fromCache,
    this.syncedAt,
  });

  final List<CouponSummary> coupons;

  /// True when the network failed and the list came from the local cache —
  /// the UI labels it so cached data is never mistaken for live data.
  final bool fromCache;
  final DateTime? syncedAt;
}

/// Network-first with offline fallback: a fresh fetch updates the cache; a
/// network failure serves the last snapshot instead of an error screen.
class CouponRepository {
  CouponRepository(this._api, this._cache);

  final CouponApi _api;
  final CouponCache _cache;

  Future<CouponListResult> getCoupons({DateTime Function() now = DateTime.now}) async {
    try {
      final coupons = await _api.fetchCoupons();
      await _cache.saveCoupons(coupons, now());
      return CouponListResult(coupons: coupons, fromCache: false);
    } on AppException {
      final cached = await _cache.loadCoupons();
      if (cached == null) rethrow;
      return CouponListResult(
        coupons: cached.coupons,
        fromCache: true,
        syncedAt: cached.syncedAt,
      );
    }
  }
}

final couponRepositoryProvider = Provider<CouponRepository>((ref) {
  return CouponRepository(
    ref.watch(couponApiProvider),
    ref.watch(couponCacheProvider),
  );
});
