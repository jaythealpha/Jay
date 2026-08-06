import 'package:amc_mobile/features/coupon_detail/data/coupon_actions_api.dart';
import 'package:amc_mobile/features/expiration_alerts/data/notifications_api.dart';
import 'package:amc_mobile/features/expiration_alerts/presentation/notifications_screen.dart';
import 'package:amc_mobile/shared/models/coupon_detail.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:mocktail/mocktail.dart';

import '../../shared/coupon_detail_test.dart' show detailJson;

class MockNotificationsApi extends Mock implements NotificationsApi {}

class MockActionsApi extends Mock implements CouponActionsApi {}

ExpirationNotification item(String id, String couponId, String message) =>
    ExpirationNotification.fromJson(<String, dynamic>{
      'id': id,
      'couponId': couponId,
      'message': message,
      'sentAt': '2026-08-06T09:00:00.000Z',
    });

Widget wrap(NotificationsApi api, CouponActionsApi actions) {
  final router = GoRouter(
    initialLocation: '/notifications',
    routes: [
      GoRoute(
        path: '/notifications',
        builder: (context, state) => const NotificationsScreen(),
      ),
      GoRoute(
        path: '/coupon/:id',
        builder: (context, state) => Scaffold(body: Text('detail-${state.pathParameters['id']}')),
      ),
    ],
  );
  return ProviderScope(
    overrides: [
      notificationsApiProvider.overrideWithValue(api),
      couponActionsApiProvider.overrideWithValue(actions),
    ],
    child: MaterialApp.router(routerConfig: router),
  );
}

void main() {
  testWidgets('shows reminder messages with all three actions', (tester) async {
    final api = MockNotificationsApi();
    when(() => api.fetchFeed()).thenAnswer(
      (_) async => [item('n1', 'c1', '스타벅스 아메리카노 쿠폰이 3일 뒤 만료됩니다.')],
    );

    await tester.pumpWidget(wrap(api, MockActionsApi()));
    await tester.pumpAndSettle();

    expect(find.text('스타벅스 아메리카노 쿠폰이 3일 뒤 만료됩니다.'), findsOneWidget);
    expect(find.text('쿠폰 보기'), findsOneWidget);
    expect(find.text('사용 완료'), findsOneWidget);
    expect(find.text('하루 뒤 다시 알림'), findsOneWidget);
  });

  testWidgets('쿠폰 보기 deep-links to the coupon detail', (tester) async {
    final api = MockNotificationsApi();
    when(() => api.fetchFeed()).thenAnswer(
      (_) async => [item('n1', 'c1', '테스트 알림')],
    );

    await tester.pumpWidget(wrap(api, MockActionsApi()));
    await tester.pumpAndSettle();

    await tester.tap(find.text('쿠폰 보기'));
    await tester.pumpAndSettle();

    expect(find.text('detail-c1'), findsOneWidget);
  });

  testWidgets('사용 완료 calls redeem; 하루 뒤 다시 알림 calls snooze', (tester) async {
    final api = MockNotificationsApi();
    final actions = MockActionsApi();
    when(() => api.fetchFeed()).thenAnswer(
      (_) async => [item('n1', 'c1', '테스트 알림')],
    );
    when(() => actions.redeem('c1'))
        .thenAnswer((_) async => CouponDetail.fromJson(detailJson(status: 'REDEEMED')));
    when(() => api.snooze('n1')).thenAnswer((_) async {});

    await tester.pumpWidget(wrap(api, actions));
    await tester.pumpAndSettle();

    await tester.tap(find.text('사용 완료'));
    await tester.pumpAndSettle();
    verify(() => actions.redeem('c1')).called(1);
    expect(find.text('사용 완료로 처리했어요.'), findsOneWidget);

    await tester.tap(find.text('하루 뒤 다시 알림'));
    await tester.pumpAndSettle();
    verify(() => api.snooze('n1')).called(1);
  });

  testWidgets('empty feed shows a friendly message', (tester) async {
    final api = MockNotificationsApi();
    when(() => api.fetchFeed()).thenAnswer((_) async => []);

    await tester.pumpWidget(wrap(api, MockActionsApi()));
    await tester.pumpAndSettle();

    expect(find.text('아직 도착한 만료 알림이 없어요.'), findsOneWidget);
  });
}
