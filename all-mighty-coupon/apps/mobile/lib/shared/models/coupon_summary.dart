import 'package:flutter/foundation.dart';

/// Immutable wire model for GET /v1/coupons items. Parsing is defensive:
/// unknown enum strings become fallbacks instead of crashes, and missing
/// values stay null — mirrors the server contract in @amc/shared-types.
@immutable
class CouponSummary {
  const CouponSummary({
    required this.id,
    required this.brandName,
    required this.productName,
    required this.category,
    required this.faceValueMinor,
    required this.currency,
    required this.status,
    required this.expiresAt,
    required this.requiresReview,
    required this.sourceType,
    required this.createdAt,
  });

  factory CouponSummary.fromJson(Map<String, dynamic> json) {
    return CouponSummary(
      id: json['id'] as String,
      brandName: json['brandName'] as String?,
      productName: json['productName'] as String?,
      category: json['category'] as String?,
      faceValueMinor: json['faceValueMinor'] as int?,
      currency: json['currency'] as String?,
      status: json['status'] as String? ?? 'PROCESSING',
      expiresAt: json['expiresAt'] == null
          ? null
          : DateTime.parse(json['expiresAt'] as String),
      requiresReview: json['requiresReview'] as bool? ?? true,
      sourceType: json['sourceType'] as String? ?? 'MANUAL',
      createdAt: DateTime.parse(json['createdAt'] as String),
    );
  }

  final String id;
  final String? brandName;
  final String? productName;
  final String? category;
  final int? faceValueMinor;
  final String? currency;
  final String status;
  final DateTime? expiresAt;
  final bool requiresReview;
  final String sourceType;
  final DateTime createdAt;

  Map<String, dynamic> toJson() => <String, dynamic>{
        'id': id,
        'brandName': brandName,
        'productName': productName,
        'category': category,
        'faceValueMinor': faceValueMinor,
        'currency': currency,
        'status': status,
        'expiresAt': expiresAt?.toIso8601String(),
        'requiresReview': requiresReview,
        'sourceType': sourceType,
        'createdAt': createdAt.toIso8601String(),
      };

  @override
  bool operator ==(Object other) => other is CouponSummary && other.id == id;

  @override
  int get hashCode => id.hashCode;
}
