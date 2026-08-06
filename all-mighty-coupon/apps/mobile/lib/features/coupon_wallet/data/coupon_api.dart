import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/api_client.dart';
import '../../../shared/models/coupon_summary.dart';
import '../domain/wallet_query.dart';

class CouponApi {
  CouponApi(this._dio);

  final Dio _dio;

  Future<List<CouponSummary>> fetchCoupons({WalletQuery query = const WalletQuery()}) async {
    try {
      final response = await _dio.get<Map<String, dynamic>>(
        '/v1/coupons',
        queryParameters: {
          if (query.status != null) 'status': query.status,
          if (query.q.isNotEmpty) 'q': query.q,
          if (query.sort != 'EXPIRATION_ASC') 'sort': query.sort,
        },
      );
      final items = response.data?['items'] as List<dynamic>? ?? <dynamic>[];
      return items
          .map((item) => CouponSummary.fromJson(item as Map<String, dynamic>))
          .toList();
    } on DioException catch (error) {
      throw mapDioError(error);
    }
  }
}

final couponApiProvider = Provider<CouponApi>((ref) {
  return CouponApi(ref.watch(dioProvider));
});
