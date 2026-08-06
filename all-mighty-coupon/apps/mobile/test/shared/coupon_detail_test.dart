import 'package:amc_mobile/shared/models/coupon_detail.dart';
import 'package:flutter_test/flutter_test.dart';

Map<String, dynamic> detailJson({
  String status = 'NEEDS_REVIEW',
  Map<String, dynamic>? recognition,
}) {
  return <String, dynamic>{
    'id': 'c1',
    'brandName': '스타벅스',
    'productName': '아메리카노 Tall',
    'faceValueMinor': 4500,
    'status': status,
    'expiresAt': '2026-12-31T00:00:00.000Z',
    'requiresReview': true,
    'sourceType': 'PHOTO_LIBRARY',
    'createdAt': '2026-08-01T00:00:00.000Z',
    'usageLocationText': null,
    'usageConditions': null,
    'barcodeType': 'Code128',
    'hasBarcode': true,
    'recognition': recognition ??
        <String, dynamic>{
          'confidences': <String, dynamic>{
            'brand': 0.95,
            'productName': 0.75,
            'expiresAt': 0.7,
            'amountMinor': 0.9,
            'barcode': 0.99,
          },
          'duplicateSuspects': <String>['older-coupon'],
          'error': null,
        },
    'assets': <Map<String, dynamic>>[
      <String, dynamic>{'type': 'ORIGINAL', 'url': 'https://signed/original', 'mimeType': 'image/png'},
      <String, dynamic>{'type': 'THUMBNAIL', 'url': 'https://signed/thumb', 'mimeType': 'image/jpeg'},
    ],
  };
}

void main() {
  test('parses recognition confidences, duplicates, and assets', () {
    final detail = CouponDetail.fromJson(detailJson());
    expect(detail.summary.brandName, '스타벅스');
    expect(detail.hasBarcode, true);
    expect(detail.confidences?.brand, 0.95);
    expect(detail.confidences?.expiresAt, 0.7);
    expect(detail.duplicateSuspects, ['older-coupon']);
    expect(detail.assets, hasLength(2));
    expect(detail.isProcessing, false);
  });

  test('handles missing recognition block (still PROCESSING)', () {
    final json = detailJson(status: 'PROCESSING')..['recognition'] = null;
    final detail = CouponDetail.fromJson(json);
    expect(detail.isProcessing, true);
    expect(detail.confidences, isNull);
    expect(detail.duplicateSuspects, isEmpty);
  });
}
