import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/api_client.dart';
import '../../../shared/models/coupon_detail.dart';

class CouponDetailApi {
  CouponDetailApi(this._dio);

  final Dio _dio;

  Future<CouponDetail> fetchDetail(String id) async {
    try {
      final response = await _dio.get<Map<String, dynamic>>('/v1/coupons/$id');
      return CouponDetail.fromJson(response.data ?? const {});
    } on DioException catch (error) {
      throw mapDioError(error);
    }
  }

  Future<CouponDetail> patch(String id, Map<String, Object?> fields) async {
    try {
      final response = await _dio.patch<Map<String, dynamic>>('/v1/coupons/$id', data: fields);
      return CouponDetail.fromJson(response.data ?? const {});
    } on DioException catch (error) {
      throw mapDioError(error);
    }
  }

  Future<CouponDetail> confirm(String id) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>('/v1/coupons/$id/confirm');
      return CouponDetail.fromJson(response.data ?? const {});
    } on DioException catch (error) {
      throw mapDioError(error);
    }
  }
}

final couponDetailApiProvider = Provider<CouponDetailApi>((ref) {
  return CouponDetailApi(ref.watch(dioProvider));
});
