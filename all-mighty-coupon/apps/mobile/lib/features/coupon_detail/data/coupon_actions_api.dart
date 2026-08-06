import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/api_client.dart';
import '../../../shared/models/coupon_detail.dart';

class RevealedBarcode {
  const RevealedBarcode({required this.value, required this.format});

  final String value;
  final String? format;
}

class CouponActionsApi {
  CouponActionsApi(this._dio);

  final Dio _dio;

  Future<CouponDetail> _action(String id, String action) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>('/v1/coupons/$id/$action');
      return CouponDetail.fromJson(response.data ?? const {});
    } on DioException catch (error) {
      throw mapDioError(error);
    }
  }

  Future<CouponDetail> redeem(String id) => _action(id, 'redeem');

  Future<CouponDetail> restore(String id) => _action(id, 'restore');

  Future<CouponDetail> archive(String id) => _action(id, 'archive');

  Future<CouponDetail> unarchive(String id) => _action(id, 'unarchive');

  Future<void> delete(String id) async {
    try {
      await _dio.delete<void>('/v1/coupons/$id');
    } on DioException catch (error) {
      throw mapDioError(error);
    }
  }

  /// Server reveal is audit-logged (BARCODE_VIEWED). Callers cache the value
  /// in the device secure vault for offline display.
  Future<RevealedBarcode> revealBarcode(String id) async {
    try {
      final response = await _dio.get<Map<String, dynamic>>('/v1/coupons/$id/barcode');
      return RevealedBarcode(
        value: response.data?['value'] as String? ?? '',
        format: response.data?['format'] as String?,
      );
    } on DioException catch (error) {
      throw mapDioError(error);
    }
  }
}

final couponActionsApiProvider =
    Provider<CouponActionsApi>((ref) => CouponActionsApi(ref.watch(dioProvider)));
