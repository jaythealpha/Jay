import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../domain/coupon_repository.dart';

/// Wallet list state: AsyncValue drives the loading / data / error UI.
final couponListProvider =
    AsyncNotifierProvider<CouponListController, CouponListResult>(
  CouponListController.new,
);

class CouponListController extends AsyncNotifier<CouponListResult> {
  @override
  Future<CouponListResult> build() {
    return ref.watch(couponRepositoryProvider).getCoupons();
  }

  Future<void> refresh() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(
      () => ref.read(couponRepositoryProvider).getCoupons(),
    );
  }
}
