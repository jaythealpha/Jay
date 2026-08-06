import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../shared/models/coupon_summary.dart';

/// Offline-first foundation (spec §2.6): the last successful coupon list is
/// kept locally so the wallet still opens without a network connection.
/// Milestone 0 uses a JSON snapshot in SharedPreferences; a structured Drift
/// database replaces it when sync arrives (Milestone 2, see ADR-0003).
abstract interface class CouponCache {
  Future<void> saveCoupons(List<CouponSummary> coupons, DateTime syncedAt);

  /// Returns null when nothing was cached yet.
  Future<CachedCoupons?> loadCoupons();

  Future<void> clear();
}

class CachedCoupons {
  const CachedCoupons({required this.coupons, required this.syncedAt});

  final List<CouponSummary> coupons;
  final DateTime syncedAt;
}

class SharedPrefsCouponCache implements CouponCache {
  static const _couponsKey = 'amc.cache.coupons.v1';
  static const _syncedAtKey = 'amc.cache.coupons.syncedAt.v1';

  @override
  Future<void> saveCoupons(List<CouponSummary> coupons, DateTime syncedAt) async {
    final prefs = await SharedPreferences.getInstance();
    final payload = jsonEncode(coupons.map((c) => c.toJson()).toList());
    await prefs.setString(_couponsKey, payload);
    await prefs.setString(_syncedAtKey, syncedAt.toUtc().toIso8601String());
  }

  @override
  Future<CachedCoupons?> loadCoupons() async {
    final prefs = await SharedPreferences.getInstance();
    final payload = prefs.getString(_couponsKey);
    final syncedAtRaw = prefs.getString(_syncedAtKey);
    if (payload == null || syncedAtRaw == null) return null;
    final decoded = jsonDecode(payload) as List<dynamic>;
    return CachedCoupons(
      coupons: decoded
          .map((item) => CouponSummary.fromJson(item as Map<String, dynamic>))
          .toList(),
      syncedAt: DateTime.parse(syncedAtRaw),
    );
  }

  @override
  Future<void> clear() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_couponsKey);
    await prefs.remove(_syncedAtKey);
  }
}

final couponCacheProvider = Provider<CouponCache>((ref) => SharedPrefsCouponCache());
