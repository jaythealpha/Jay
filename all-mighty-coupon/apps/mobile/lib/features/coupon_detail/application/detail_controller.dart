import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/errors/app_exception.dart';
import '../../../core/sync/pending_actions.dart';
import '../../../shared/models/coupon_detail.dart';
import '../../coupon_review/data/coupon_detail_api.dart';
import '../data/coupon_actions_api.dart';

/// Outcome of a redeem attempt: done online, or queued for later sync.
enum RedeemOutcome { redeemed, queuedOffline }

class DetailController extends AsyncNotifier<CouponDetail> {
  DetailController(this.couponId);

  final String couponId;

  @override
  Future<CouponDetail> build() {
    return ref.watch(couponDetailApiProvider).fetchDetail(couponId);
  }

  Future<RedeemOutcome> redeem() async {
    final actions = ref.read(couponActionsApiProvider);
    try {
      final detail = await actions.redeem(couponId);
      state = AsyncData(detail);
      return RedeemOutcome.redeemed;
    } on NetworkException {
      // In-store with no signal: queue the action, replayed on next sync.
      await ref
          .read(pendingActionQueueProvider)
          .enqueue(PendingAction(type: 'REDEEM', couponId: couponId));
      return RedeemOutcome.queuedOffline;
    }
  }

  Future<void> restore() async {
    state = AsyncData(await ref.read(couponActionsApiProvider).restore(couponId));
  }

  Future<void> archive() async {
    state = AsyncData(await ref.read(couponActionsApiProvider).archive(couponId));
  }

  Future<void> unarchive() async {
    state = AsyncData(await ref.read(couponActionsApiProvider).unarchive(couponId));
  }

  Future<void> delete() => ref.read(couponActionsApiProvider).delete(couponId);
}

final detailControllerProvider =
    AsyncNotifierProvider.family<DetailController, CouponDetail, String>(DetailController.new);
