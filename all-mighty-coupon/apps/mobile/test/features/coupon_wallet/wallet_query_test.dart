import 'package:amc_mobile/features/coupon_wallet/domain/wallet_query.dart';
import 'package:amc_mobile/shared/models/coupon_summary.dart';
import 'package:flutter_test/flutter_test.dart';

CouponSummary coupon(
  String id, {
  String? brand,
  String? product,
  String status = 'ACTIVE',
  DateTime? expiresAt,
  int? value,
  DateTime? createdAt,
}) {
  return CouponSummary.fromJson(<String, dynamic>{
    'id': id,
    'brandName': brand,
    'productName': product,
    'faceValueMinor': value,
    'status': status,
    'expiresAt': expiresAt?.toIso8601String(),
    'createdAt': (createdAt ?? DateTime.utc(2026, 8, 1)).toIso8601String(),
  });
}

void main() {
  final list = [
    coupon('a', brand: '스타벅스', status: 'ACTIVE', expiresAt: DateTime.utc(2026, 12, 31), value: 4500),
    coupon('b', brand: '이마트', status: 'REDEEMED', expiresAt: DateTime.utc(2026, 9, 1), value: 30000),
    coupon('c', brand: 'GS25', product: '수박바', status: 'ACTIVE', value: 1500),
  ];

  test('filters by status', () {
    final result = applyQueryLocally(list, const WalletQuery(status: 'REDEEMED'));
    expect(result.map((c) => c.id), ['b']);
  });

  test('searches brand and product case-insensitively', () {
    expect(applyQueryLocally(list, const WalletQuery(q: 'gs25')).single.id, 'c');
    expect(applyQueryLocally(list, const WalletQuery(q: '수박')).single.id, 'c');
  });

  test('default sort is expiration-first with undated coupons last', () {
    final result = applyQueryLocally(list, const WalletQuery());
    expect(result.map((c) => c.id), ['b', 'a', 'c']);
  });

  test('VALUE_DESC sorts by amount', () {
    final result = applyQueryLocally(list, const WalletQuery(sort: 'VALUE_DESC'));
    expect(result.first.id, 'b');
    expect(result.last.id, 'c');
  });
}
