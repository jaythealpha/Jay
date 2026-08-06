import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/sync/pending_actions.dart';
import '../domain/coupon_repository.dart';
import '../domain/wallet_query.dart';

/// Current wallet filter/search/sort selection.
final walletQueryProvider = NotifierProvider<WalletQueryController, WalletQuery>(
  WalletQueryController.new,
);

class WalletQueryController extends Notifier<WalletQuery> {
  @override
  WalletQuery build() => const WalletQuery();

  void setStatus(String? status) => state = state.copyWith(status: () => status);

  void setSearch(String q) => state = state.copyWith(q: q);

  void setSort(String sort) => state = state.copyWith(sort: sort);
}

/// Wallet list state: AsyncValue drives the loading / data / error UI.
/// Before each fetch, queued offline actions are pushed to the server so the
/// list reflects them (기본 동기화).
final couponListProvider =
    AsyncNotifierProvider<CouponListController, CouponListResult>(
  CouponListController.new,
);

class CouponListController extends AsyncNotifier<CouponListResult> {
  @override
  Future<CouponListResult> build() async {
    final query = ref.watch(walletQueryProvider);
    await ref.read(syncServiceProvider).trySyncPending();
    return ref.watch(couponRepositoryProvider).getCoupons(query: query);
  }

  Future<void> refresh() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(() async {
      await ref.read(syncServiceProvider).trySyncPending();
      return ref
          .read(couponRepositoryProvider)
          .getCoupons(query: ref.read(walletQueryProvider));
    });
  }
}
