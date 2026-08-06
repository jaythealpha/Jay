import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/api_client.dart';
import '../../../shared/models/coupon_summary.dart';

@immutable
class HomeCounts {
  const HomeCounts({
    required this.active,
    required this.expiringSoon,
    required this.redeemed,
    required this.needsReview,
    required this.total,
  });

  factory HomeCounts.fromJson(Map<String, dynamic> json) => HomeCounts(
        active: json['active'] as int? ?? 0,
        expiringSoon: json['expiringSoon'] as int? ?? 0,
        redeemed: json['redeemed'] as int? ?? 0,
        needsReview: json['needsReview'] as int? ?? 0,
        total: json['total'] as int? ?? 0,
      );

  final int active;
  final int expiringSoon;
  final int redeemed;
  final int needsReview;
  final int total;
}

@immutable
class HomeSummary {
  const HomeSummary({
    required this.expiringSoon,
    required this.useThisWeek,
    required this.recent,
    required this.counts,
    required this.totalValueMinor,
  });

  factory HomeSummary.fromJson(Map<String, dynamic> json) {
    List<CouponSummary> parseList(String key) =>
        (json[key] as List<dynamic>? ?? const [])
            .map((e) => CouponSummary.fromJson(e as Map<String, dynamic>))
            .toList();
    return HomeSummary(
      expiringSoon: parseList('expiringSoon'),
      useThisWeek: parseList('useThisWeek'),
      recent: parseList('recent'),
      counts: HomeCounts.fromJson(json['counts'] as Map<String, dynamic>? ?? const {}),
      totalValueMinor: json['totalValueMinor'] as int? ?? 0,
    );
  }

  final List<CouponSummary> expiringSoon;
  final List<CouponSummary> useThisWeek;
  final List<CouponSummary> recent;
  final HomeCounts counts;
  final int totalValueMinor;
}

class HomeApi {
  HomeApi(this._dio);

  final Dio _dio;

  Future<HomeSummary> fetchSummary() async {
    try {
      final response = await _dio.get<Map<String, dynamic>>('/v1/home');
      return HomeSummary.fromJson(response.data ?? const {});
    } on DioException catch (error) {
      throw mapDioError(error);
    }
  }
}

final homeApiProvider = Provider<HomeApi>((ref) => HomeApi(ref.watch(dioProvider)));

final homeSummaryProvider = FutureProvider<HomeSummary>((ref) {
  return ref.watch(homeApiProvider).fetchSummary();
});
