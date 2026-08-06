import 'dart:io';

import 'package:amc_mobile/features/coupon_wallet/data/coupon_api.dart';
import 'package:amc_mobile/features/home/data/health_api.dart';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

/// Manual smoke test against a LIVE local API (not part of the normal suite).
/// Run with the stack up (docker compose + API):
///   flutter test test/manual/api_smoke_test.dart --dart-define=API_SMOKE=true
const _enabled = bool.fromEnvironment('API_SMOKE');

void main() {
  setUpAll(() {
    // flutter_test blocks real sockets by default; this suite exists to talk
    // to the real dev server, so restore normal HTTP.
    HttpOverrides.global = null;
  });

  final dio = Dio(BaseOptions(baseUrl: 'http://localhost:3001'));

  test(
    'GET /health parses through the app HealthApi',
    () async {
      final health = await HealthApi(dio).fetchHealth();
      expect(health.overall, 'ok');
      expect(health.database, 'up');
      expect(health.redis, 'up');
    },
    skip: !_enabled,
  );

  test(
    'GET /v1/coupons parses seeded coupons through the app CouponApi',
    () async {
      final coupons = await CouponApi(dio).fetchCoupons();
      expect(coupons, isNotEmpty);
      expect(coupons.first.id, isNotEmpty);
      // Expiration First ordering: first item has the earliest expiration.
      final dated = coupons.where((c) => c.expiresAt != null).toList();
      for (var i = 1; i < dated.length; i++) {
        expect(
          dated[i - 1].expiresAt!.isBefore(dated[i].expiresAt!) ||
              dated[i - 1].expiresAt!.isAtSameMomentAs(dated[i].expiresAt!),
          isTrue,
        );
      }
    },
    skip: !_enabled,
  );
}
