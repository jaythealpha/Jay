import 'package:flutter/foundation.dart';

import 'coupon_summary.dart';

/// Per-field recognition confidences as returned by GET /v1/coupons/:id.
@immutable
class RecognitionConfidences {
  const RecognitionConfidences({
    required this.brand,
    required this.productName,
    required this.expiresAt,
    required this.amountMinor,
    required this.barcode,
  });

  factory RecognitionConfidences.fromJson(Map<String, dynamic> json) {
    double? asDouble(Object? value) => value is num ? value.toDouble() : null;
    return RecognitionConfidences(
      brand: asDouble(json['brand']),
      productName: asDouble(json['productName']),
      expiresAt: asDouble(json['expiresAt']),
      amountMinor: asDouble(json['amountMinor']),
      barcode: asDouble(json['barcode']),
    );
  }

  final double? brand;
  final double? productName;
  final double? expiresAt;
  final double? amountMinor;
  final double? barcode;
}

@immutable
class CouponAssetRef {
  const CouponAssetRef({required this.type, required this.url, required this.mimeType});

  factory CouponAssetRef.fromJson(Map<String, dynamic> json) => CouponAssetRef(
        type: json['type'] as String? ?? 'ORIGINAL',
        url: json['url'] as String? ?? '',
        mimeType: json['mimeType'] as String? ?? 'image/jpeg',
      );

  final String type;

  /// Short-lived signed URL — display immediately, never persist.
  final String url;
  final String mimeType;
}

@immutable
class CouponDetail {
  const CouponDetail({
    required this.summary,
    required this.usageLocationText,
    required this.usageConditions,
    required this.barcodeType,
    required this.hasBarcode,
    required this.confidences,
    required this.duplicateSuspects,
    required this.recognitionError,
    required this.assets,
  });

  factory CouponDetail.fromJson(Map<String, dynamic> json) {
    final recognition = json['recognition'] as Map<String, dynamic>?;
    return CouponDetail(
      summary: CouponSummary.fromJson(json),
      usageLocationText: json['usageLocationText'] as String?,
      usageConditions: json['usageConditions'] as String?,
      barcodeType: json['barcodeType'] as String?,
      hasBarcode: json['hasBarcode'] as bool? ?? false,
      confidences: recognition == null
          ? null
          : RecognitionConfidences.fromJson(
              recognition['confidences'] as Map<String, dynamic>? ?? const {},
            ),
      duplicateSuspects: (recognition?['duplicateSuspects'] as List<dynamic>? ?? const [])
          .map((e) => e as String)
          .toList(),
      recognitionError: recognition?['error'] as String?,
      assets: (json['assets'] as List<dynamic>? ?? const [])
          .map((e) => CouponAssetRef.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
  }

  final CouponSummary summary;
  final String? usageLocationText;
  final String? usageConditions;
  final String? barcodeType;
  final bool hasBarcode;
  final RecognitionConfidences? confidences;
  final List<String> duplicateSuspects;
  final String? recognitionError;
  final List<CouponAssetRef> assets;

  bool get isProcessing => summary.status == 'PROCESSING';
}
