import 'package:flutter/foundation.dart';

import '../../../shared/models/coupon_summary.dart';

/// Wallet list query: status filter, text search, sort. Defaults follow the
/// Expiration First principle.
@immutable
class WalletQuery {
  const WalletQuery({this.status, this.q = '', this.sort = 'EXPIRATION_ASC'});

  final String? status;
  final String q;
  final String sort;

  WalletQuery copyWith({String? Function()? status, String? q, String? sort}) => WalletQuery(
        status: status != null ? status() : this.status,
        q: q ?? this.q,
        sort: sort ?? this.sort,
      );

  bool get isDefault => status == null && q.isEmpty && sort == 'EXPIRATION_ASC';

  @override
  bool operator ==(Object other) =>
      other is WalletQuery && other.status == status && other.q == q && other.sort == sort;

  @override
  int get hashCode => Object.hash(status, q, sort);
}

/// Client-side mirror of the server's filter/sort — used on the cached
/// snapshot when the device is offline.
List<CouponSummary> applyQueryLocally(List<CouponSummary> coupons, WalletQuery query) {
  Iterable<CouponSummary> result = coupons;
  if (query.status != null) {
    result = result.where((c) => c.status == query.status);
  }
  if (query.q.isNotEmpty) {
    final needle = query.q.toLowerCase();
    result = result.where(
      (c) =>
          (c.brandName?.toLowerCase().contains(needle) ?? false) ||
          (c.productName?.toLowerCase().contains(needle) ?? false) ||
          (c.category?.toLowerCase().contains(needle) ?? false),
    );
  }
  final list = result.toList();
  switch (query.sort) {
    case 'CREATED_DESC':
      list.sort((a, b) => b.createdAt.compareTo(a.createdAt));
    case 'VALUE_DESC':
      list.sort((a, b) => (b.faceValueMinor ?? -1).compareTo(a.faceValueMinor ?? -1));
    case 'BRAND_ASC':
      list.sort((a, b) => (a.brandName ?? '￿').compareTo(b.brandName ?? '￿'));
    case 'EXPIRATION_ASC':
    default:
      list.sort((a, b) {
        final ax = a.expiresAt;
        final bx = b.expiresAt;
        if (ax != null && bx != null) {
          final diff = ax.compareTo(bx);
          if (diff != 0) return diff;
        } else if (ax != null) {
          return -1;
        } else if (bx != null) {
          return 1;
        }
        return b.createdAt.compareTo(a.createdAt);
      });
  }
  return list;
}
