import 'package:amc_mobile/core/errors/app_exception.dart';
import 'package:amc_mobile/core/sync/pending_actions.dart';
import 'package:amc_mobile/features/coupon_detail/data/coupon_actions_api.dart';
import 'package:amc_mobile/features/coupon_detail/presentation/coupon_detail_screen.dart';
import 'package:amc_mobile/features/coupon_review/data/coupon_detail_api.dart';
import 'package:amc_mobile/shared/models/coupon_detail.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:mocktail/mocktail.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../shared/coupon_detail_test.dart' show detailJson;

class MockDetailApi extends Mock implements CouponDetailApi {}

class MockActionsApi extends Mock implements CouponActionsApi {}

Widget wrap(CouponDetailApi detailApi, CouponActionsApi actionsApi) {
  final router = GoRouter(
    initialLocation: '/coupon/c1',
    routes: [
      GoRoute(
        path: '/coupon/:id',
        builder: (context, state) =>
            CouponDetailScreen(couponId: state.pathParameters['id'] ?? ''),
      ),
      GoRoute(
        path: '/coupon/:id/barcode',
        builder: (context, state) => const Scaffold(body: Text('barcode-stub')),
      ),
      GoRoute(
        path: '/wallet',
        builder: (context, state) => const Scaffold(body: Text('wallet-stub')),
      ),
    ],
  );
  return ProviderScope(
    overrides: [
      couponDetailApiProvider.overrideWithValue(detailApi),
      couponActionsApiProvider.overrideWithValue(actionsApi),
    ],
    child: MaterialApp.router(routerConfig: router),
  );
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    SharedPreferences.setMockInitialValues(<String, Object>{});
  });

  testWidgets('shows coupon info, barcode button, and redeem action', (tester) async {
    final detailApi = MockDetailApi();
    final actionsApi = MockActionsApi();
    when(() => detailApi.fetchDetail('c1'))
        .thenAnswer((_) async => CouponDetail.fromJson(detailJson(status: 'ACTIVE')));

    await tester.pumpWidget(wrap(detailApi, actionsApi));
    await tester.pumpAndSettle();

    expect(find.text('스타벅스'), findsOneWidget);
    expect(find.text('아메리카노 Tall'), findsOneWidget);
    expect(find.text('바코드 보기'), findsOneWidget);
    expect(find.text('사용 완료'), findsOneWidget);
  });

  testWidgets('redeem updates the status to REDEEMED with an undo action', (tester) async {
    final detailApi = MockDetailApi();
    final actionsApi = MockActionsApi();
    when(() => detailApi.fetchDetail('c1'))
        .thenAnswer((_) async => CouponDetail.fromJson(detailJson(status: 'ACTIVE')));
    when(() => actionsApi.redeem('c1'))
        .thenAnswer((_) async => CouponDetail.fromJson(detailJson(status: 'REDEEMED')));

    await tester.pumpWidget(wrap(detailApi, actionsApi));
    await tester.pumpAndSettle();

    await tester.ensureVisible(find.text('사용 완료'));
    await tester.tap(find.text('사용 완료'));
    await tester.pumpAndSettle();

    verify(() => actionsApi.redeem('c1')).called(1);
    expect(find.text('사용 완료 취소'), findsOneWidget);
  });

  testWidgets('offline redeem queues the action and tells the user', (tester) async {
    final detailApi = MockDetailApi();
    final actionsApi = MockActionsApi();
    when(() => detailApi.fetchDetail('c1'))
        .thenAnswer((_) async => CouponDetail.fromJson(detailJson(status: 'ACTIVE')));
    when(() => actionsApi.redeem('c1')).thenThrow(const NetworkException());

    await tester.pumpWidget(wrap(detailApi, actionsApi));
    await tester.pumpAndSettle();

    await tester.ensureVisible(find.text('사용 완료'));
    await tester.tap(find.text('사용 완료'));
    await tester.pumpAndSettle();

    expect(find.textContaining('오프라인 상태예요'), findsOneWidget);
    final queue = SharedPrefsPendingActionQueue();
    expect((await queue.all()).single.couponId, 'c1');
  });

  testWidgets('barcode button navigates to the barcode screen', (tester) async {
    final detailApi = MockDetailApi();
    when(() => detailApi.fetchDetail('c1'))
        .thenAnswer((_) async => CouponDetail.fromJson(detailJson(status: 'ACTIVE')));

    await tester.pumpWidget(wrap(detailApi, MockActionsApi()));
    await tester.pumpAndSettle();

    await tester.tap(find.text('바코드 보기'));
    await tester.pumpAndSettle();

    expect(find.text('barcode-stub'), findsOneWidget);
  });
}
