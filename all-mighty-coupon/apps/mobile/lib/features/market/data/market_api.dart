import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/api_client.dart';

/// Market wire models (M4). Seller identity never crosses the wire.
@immutable
class MarketCoupon {
  const MarketCoupon({
    required this.brandName,
    required this.productName,
    required this.faceValueMinor,
    required this.expiresAt,
  });

  factory MarketCoupon.fromJson(Map<String, dynamic> json) => MarketCoupon(
        brandName: json['brandName'] as String?,
        productName: json['productName'] as String?,
        faceValueMinor: json['faceValueMinor'] as int?,
        expiresAt: json['expiresAt'] == null
            ? null
            : DateTime.parse(json['expiresAt'] as String),
      );

  final String? brandName;
  final String? productName;
  final int? faceValueMinor;
  final DateTime? expiresAt;
}

@immutable
class MarketListing {
  const MarketListing({
    required this.id,
    required this.priceMinor,
    required this.feeMinor,
    required this.mine,
    required this.coupon,
  });

  factory MarketListing.fromJson(Map<String, dynamic> json) => MarketListing(
        id: json['id'] as String? ?? '',
        priceMinor: json['priceMinor'] as int? ?? 0,
        feeMinor: json['feeMinor'] as int? ?? 0,
        mine: json['mine'] as bool? ?? false,
        coupon: MarketCoupon.fromJson(json['coupon'] as Map<String, dynamic>? ?? const {}),
      );

  final String id;
  final int priceMinor;
  final int feeMinor;
  final bool mine;
  final MarketCoupon coupon;
}

class MarketApi {
  MarketApi(this._dio);

  final Dio _dio;

  Future<List<MarketListing>> browse({String q = ''}) async {
    try {
      final response = await _dio.get<Map<String, dynamic>>(
        '/v1/market/listings',
        queryParameters: {if (q.isNotEmpty) 'q': q},
      );
      return (response.data?['items'] as List<dynamic>? ?? const [])
          .map((e) => MarketListing.fromJson(e as Map<String, dynamic>))
          .toList();
    } on DioException catch (error) {
      throw mapDioError(error);
    }
  }

  Future<void> createListing(String couponId, int priceMinor) async {
    try {
      await _dio.post<void>(
        '/v1/market/listings',
        data: {'couponId': couponId, 'priceMinor': priceMinor},
      );
    } on DioException catch (error) {
      throw _marketError(error);
    }
  }

  Future<void> cancelListing(String listingId) async {
    try {
      await _dio.delete<void>('/v1/market/listings/$listingId');
    } on DioException catch (error) {
      throw _marketError(error);
    }
  }

  Future<void> purchase(String listingId) async {
    try {
      await _dio.post<void>('/v1/market/listings/$listingId/purchase');
    } on DioException catch (error) {
      throw _marketError(error);
    }
  }

  /// Market errors carry domain reasons (eligibility, sold-out) the user
  /// must see verbatim — surface the server message when present.
  Exception _marketError(DioException error) {
    final data = error.response?.data;
    final message = data is Map<String, dynamic>
        ? ((data['error'] as Map<String, dynamic>?)?['message'] as String?)
        : null;
    if (message != null) return MarketException(message);
    return mapDioError(error);
  }
}

class MarketException implements Exception {
  const MarketException(this.userMessage);

  final String userMessage;
}

final marketApiProvider = Provider<MarketApi>((ref) => MarketApi(ref.watch(dioProvider)));

final marketListingsProvider =
    FutureProvider.family<List<MarketListing>, String>((ref, q) {
  return ref.watch(marketApiProvider).browse(q: q);
});
