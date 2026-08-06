import 'package:amc_mobile/core/errors/app_exception.dart';
import 'package:amc_mobile/core/sync/pending_actions.dart';
import 'package:amc_mobile/features/coupon_detail/data/coupon_actions_api.dart';
import 'package:amc_mobile/shared/models/coupon_detail.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../shared/coupon_detail_test.dart' show detailJson;

class MockActionsApi extends Mock implements CouponActionsApi {}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    SharedPreferences.setMockInitialValues(<String, Object>{});
  });

  test('queue is deduplicated and survives round-trips', () async {
    final queue = SharedPrefsPendingActionQueue();
    await queue.enqueue(const PendingAction(type: 'REDEEM', couponId: 'c1'));
    await queue.enqueue(const PendingAction(type: 'REDEEM', couponId: 'c1'));
    await queue.enqueue(const PendingAction(type: 'REDEEM', couponId: 'c2'));

    expect((await queue.all()).map((a) => a.couponId), ['c1', 'c2']);
  });

  test('sync replays queued redeems and removes them on success', () async {
    final queue = SharedPrefsPendingActionQueue();
    await queue.enqueue(const PendingAction(type: 'REDEEM', couponId: 'c1'));

    final api = MockActionsApi();
    when(() => api.redeem('c1'))
        .thenAnswer((_) async => CouponDetail.fromJson(detailJson(status: 'REDEEMED')));

    final synced = await SyncService(queue, api).trySyncPending();

    expect(synced, 1);
    expect(await queue.all(), isEmpty);
  });

  test('still-offline actions stay queued', () async {
    final queue = SharedPrefsPendingActionQueue();
    await queue.enqueue(const PendingAction(type: 'REDEEM', couponId: 'c1'));

    final api = MockActionsApi();
    when(() => api.redeem('c1')).thenThrow(const NetworkException());

    final synced = await SyncService(queue, api).trySyncPending();

    expect(synced, 0);
    expect((await queue.all()).single.couponId, 'c1');
  });

  test('server rejection drops the action (server state wins)', () async {
    final queue = SharedPrefsPendingActionQueue();
    await queue.enqueue(const PendingAction(type: 'REDEEM', couponId: 'c1'));

    final api = MockActionsApi();
    when(() => api.redeem('c1')).thenThrow(const ServerException());

    final synced = await SyncService(queue, api).trySyncPending();

    expect(synced, 0);
    expect(await queue.all(), isEmpty);
  });
}
