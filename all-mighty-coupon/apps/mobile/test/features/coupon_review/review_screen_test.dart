import 'package:amc_mobile/features/coupon_review/data/coupon_detail_api.dart';
import 'package:amc_mobile/features/coupon_review/presentation/review_screen.dart';
import 'package:amc_mobile/shared/models/coupon_detail.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:mocktail/mocktail.dart';

import '../../shared/coupon_detail_test.dart' show detailJson;

class MockDetailApi extends Mock implements CouponDetailApi {}

Widget wrap(CouponDetailApi api) {
  final router = GoRouter(
    initialLocation: '/review/c1',
    routes: [
      GoRoute(
        path: '/review/:id',
        builder: (context, state) =>
            ReviewScreen(couponId: state.pathParameters['id'] ?? ''),
      ),
      GoRoute(
        path: '/wallet',
        builder: (context, state) => const Scaffold(body: Text('wallet-stub')),
      ),
    ],
  );
  return ProviderScope(
    overrides: [couponDetailApiProvider.overrideWithValue(api)],
    child: MaterialApp.router(routerConfig: router),
  );
}

void main() {
  testWidgets('shows analyzing state while PROCESSING, then the review form', (tester) async {
    final api = MockDetailApi();
    var calls = 0;
    when(() => api.fetchDetail('c1')).thenAnswer((_) async {
      calls += 1;
      return CouponDetail.fromJson(
        calls == 1 ? (detailJson(status: 'PROCESSING')..['recognition'] = null) : detailJson(),
      );
    });

    await tester.pumpWidget(wrap(api));
    await tester.pump();
    expect(find.text('쿠폰을 분석하고 있어요...'), findsOneWidget);

    // Poll interval is 1s — advance time until the second fetch resolves.
    await tester.pump(const Duration(seconds: 1));
    await tester.pumpAndSettle();

    expect(find.text('인식 결과 확인'), findsOneWidget);
    expect(find.widgetWithText(TextField, '스타벅스'), findsOneWidget);
    expect(calls, greaterThanOrEqualTo(2));
  });

  testWidgets('shows confidence labels and the confirm button for NEEDS_REVIEW', (tester) async {
    final api = MockDetailApi();
    when(() => api.fetchDetail('c1'))
        .thenAnswer((_) async => CouponDetail.fromJson(detailJson()));

    await tester.pumpWidget(wrap(api));
    await tester.pumpAndSettle();

    expect(find.text('자동 인식'), findsWidgets); // brand 0.95, amount 0.9, ...
    expect(find.text('확인 권장'), findsWidgets); // product 0.75, expiry 0.7
    expect(find.text('저장하고 확정'), findsOneWidget);
    expect(find.textContaining('이미 등록된 쿠폰과 비슷해요'), findsOneWidget);
    expect(find.textContaining('바코드를 인식했어요'), findsOneWidget);
  });

  testWidgets('confirm flow patches edits, confirms, and navigates to the wallet', (tester) async {
    tester.view.physicalSize = const Size(1080, 2400);
    tester.view.devicePixelRatio = 2.0;
    addTearDown(tester.view.reset);
    final api = MockDetailApi();
    when(() => api.fetchDetail('c1'))
        .thenAnswer((_) async => CouponDetail.fromJson(detailJson()));
    when(() => api.patch('c1', any())).thenAnswer(
      (invocation) async => CouponDetail.fromJson(detailJson()),
    );
    when(() => api.confirm('c1')).thenAnswer(
      (_) async => CouponDetail.fromJson(detailJson(status: 'ACTIVE')),
    );

    await tester.pumpWidget(wrap(api));
    await tester.pumpAndSettle();

    await tester.enterText(find.widgetWithText(TextField, '아메리카노 Tall'), '아메리카노 Grande');
    await tester.ensureVisible(find.text('저장하고 확정'));
    await tester.tap(find.text('저장하고 확정'));
    await tester.pumpAndSettle();

    verify(() => api.patch('c1', {'productName': '아메리카노 Grande'})).called(1);
    verify(() => api.confirm('c1')).called(1);
    expect(find.text('wallet-stub'), findsOneWidget);
  });
}
