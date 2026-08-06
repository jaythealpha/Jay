import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/api_client.dart';

class CouponUploadApi {
  CouponUploadApi(this._dio);

  final Dio _dio;

  /// POST /v1/coupons — returns the new coupon id; analysis runs async on the
  /// server, so callers poll the detail endpoint afterwards.
  Future<String> uploadImage({
    required List<int> bytes,
    required String filename,
    required String sourceType,
  }) async {
    try {
      final form = FormData.fromMap(<String, dynamic>{
        'image': MultipartFile.fromBytes(bytes, filename: filename),
        'sourceType': sourceType,
      });
      final response = await _dio.post<Map<String, dynamic>>('/v1/coupons', data: form);
      final id = response.data?['id'] as String?;
      if (id == null) {
        throw DioException(
          requestOptions: response.requestOptions,
          message: 'missing coupon id in upload response',
        );
      }
      return id;
    } on DioException catch (error) {
      throw mapDioError(error);
    }
  }
}

final couponUploadApiProvider = Provider<CouponUploadApi>((ref) {
  return CouponUploadApi(ref.watch(dioProvider));
});
