import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../features/coupon_detail/data/coupon_actions_api.dart';
import '../errors/app_exception.dart';

/// Offline redemption support (spec §2.6): marking a coupon as used must work
/// in-store without a connection. Failed redeems are queued locally and
/// replayed the next time the wallet talks to the server.
class PendingAction {
  const PendingAction({required this.type, required this.couponId});

  factory PendingAction.fromJson(Map<String, dynamic> json) => PendingAction(
        type: json['type'] as String? ?? 'REDEEM',
        couponId: json['couponId'] as String? ?? '',
      );

  final String type; // currently only REDEEM
  final String couponId;

  Map<String, dynamic> toJson() => {'type': type, 'couponId': couponId};
}

abstract interface class PendingActionQueue {
  Future<List<PendingAction>> all();
  Future<void> enqueue(PendingAction action);
  Future<void> remove(PendingAction action);
}

class SharedPrefsPendingActionQueue implements PendingActionQueue {
  static const _key = 'amc.sync.pendingActions.v1';

  Future<List<PendingAction>> _load(SharedPreferences prefs) async {
    final raw = prefs.getString(_key);
    if (raw == null) return [];
    return (jsonDecode(raw) as List<dynamic>)
        .map((e) => PendingAction.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<void> _save(SharedPreferences prefs, List<PendingAction> actions) =>
      prefs.setString(_key, jsonEncode(actions.map((a) => a.toJson()).toList()));

  @override
  Future<List<PendingAction>> all() async =>
      _load(await SharedPreferences.getInstance());

  @override
  Future<void> enqueue(PendingAction action) async {
    final prefs = await SharedPreferences.getInstance();
    final actions = await _load(prefs);
    final exists =
        actions.any((a) => a.couponId == action.couponId && a.type == action.type);
    if (!exists) {
      actions.add(action);
      await _save(prefs, actions);
    }
  }

  @override
  Future<void> remove(PendingAction action) async {
    final prefs = await SharedPreferences.getInstance();
    final actions = await _load(prefs);
    actions.removeWhere((a) => a.couponId == action.couponId && a.type == action.type);
    await _save(prefs, actions);
  }
}

final pendingActionQueueProvider =
    Provider<PendingActionQueue>((ref) => SharedPrefsPendingActionQueue());

class SyncService {
  SyncService(this._queue, this._actionsApi);

  final PendingActionQueue _queue;
  final CouponActionsApi _actionsApi;

  /// Replays queued actions. Network failures keep the action queued; a
  /// server rejection (e.g. already redeemed) drops it — the server state
  /// wins, and the coupon's event log preserves what happened.
  Future<int> trySyncPending() async {
    final actions = await _queue.all();
    var synced = 0;
    for (final action in actions) {
      try {
        if (action.type == 'REDEEM') {
          await _actionsApi.redeem(action.couponId);
        }
        await _queue.remove(action);
        synced += 1;
      } on NetworkException {
        // still offline — keep it queued for the next attempt
      } on AppException {
        await _queue.remove(action);
      }
    }
    return synced;
  }
}

final syncServiceProvider = Provider<SyncService>((ref) {
  return SyncService(ref.watch(pendingActionQueueProvider), ref.watch(couponActionsApiProvider));
});
