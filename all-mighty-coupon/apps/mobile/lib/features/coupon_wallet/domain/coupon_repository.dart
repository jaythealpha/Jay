import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/errors/app_exception.dart';
import '../../../core/storage/coupon_cache.dart';
import '../../../shared/models/coupon_summary.dart';
import '../data/coupon_api.dart';
import 'wallet_query.dart';

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

/// Network-first with offline fallback. The cache always stores the latest
/// UNFILTERED list; offline, filters and sort are applied locally so search
/// still works in-store (Offline First for Redemption).
class CouponRepository {
  CouponRepository(this._api, this._cache);

  final CouponApi _api;
  final CouponCache _cache;

  Future<CouponListResult> getCoupons({
    WalletQuery query = const WalletQuery(),
    DateTime Function() now = DateTime.now,
  }) async {
    try {
      final coupons = await _api.fetchCoupons(query: query);
      if (query.isDefault) {
        await _cache.saveCoupons(coupons, now());
      }
      return CouponListResult(coupons: coupons, fromCache: false);
    } on SessionExpiredException {
      rethrow; // never mask an auth problem as offline data
    } on AppException {
      final cached = await _cache.loadCoupons();
      if (cached == null) rethrow;
      return CouponListResult(
        coupons: applyQueryLocally(cached.coupons, query),
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
