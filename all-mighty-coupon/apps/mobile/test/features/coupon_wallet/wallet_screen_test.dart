import 'dart:async';

import 'package:amc_mobile/core/errors/app_exception.dart';
import 'package:amc_mobile/core/sync/pending_actions.dart';
import 'package:amc_mobile/features/coupon_wallet/domain/coupon_repository.dart';
import 'package:amc_mobile/features/coupon_wallet/domain/wallet_query.dart';
import 'package:amc_mobile/features/coupon_wallet/presentation/wallet_screen.dart';
import 'package:amc_mobile/shared/models/coupon_summary.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

class MockCouponRepository extends Mock implements CouponRepository {}

class FakeSyncService implements SyncService {
  int calls = 0;

  @override
  Future<int> trySyncPending() async {
    calls += 1;
    return 0;
  }
}

Widget wrap(CouponRepository repository, {SyncService? sync}) {
  return ProviderScope(
    overrides: [
      couponRepositoryProvider.overrideWithValue(repository),
      syncServiceProvider.overrideWithValue(sync ?? FakeSyncService()),
    ],
    child: const MaterialApp(home: WalletScreen()),
  );
}

CouponSummary coupon(String id, String brand) {
  return CouponSummary.fromJson(<String, dynamic>{
    'id': id,
    'brandName': brand,
    'productName': '테스트 상품',
    'faceValueMinor': 4500,
    'status': 'EXPIRING_SOON',
    'expiresAt': DateTime.now().add(const Duration(days: 3)).toUtc().toIso8601String(),
    'createdAt': '2026-08-01T00:00:00.000Z',
  });
}

void main() {
  setUpAll(() {
    registerFallbackValue(const WalletQuery());
  });

  testWidgets('shows a loading indicator while fetching', (tester) async {
    final repo = MockCouponRepository();
    final gate = Completer<CouponListResult>();
    when(() => repo.getCoupons(query: any(named: 'query'))).thenAnswer((_) => gate.future);

    await tester.pumpWidget(wrap(repo));
    await tester.pump();

    expect(find.byType(CircularProgressIndicator), findsOneWidget);

    gate.complete(const CouponListResult(coupons: [], fromCache: false));
    await tester.pumpAndSettle();
  });

  testWidgets('renders coupon cards and runs pending sync first', (tester) async {
    final repo = MockCouponRepository();
    final sync = FakeSyncService();
    when(() => repo.getCoupons(query: any(named: 'query'))).thenAnswer(
      (_) async => CouponListResult(
        coupons: [coupon('c1', '스타벅스'), coupon('c2', '이마트')],
        fromCache: false,
      ),
    );

    await tester.pumpWidget(wrap(repo, sync: sync));
    await tester.pumpAndSettle();

    expect(find.text('스타벅스'), findsOneWidget);
    expect(find.text('이마트'), findsOneWidget);
    expect(sync.calls, 1);
  });

  testWidgets('status filter chips re-query the repository', (tester) async {
    final repo = MockCouponRepository();
    final captured = <WalletQuery>[];
    when(() => repo.getCoupons(query: any(named: 'query'))).thenAnswer((invocation) async {
      captured.add(invocation.namedArguments[#query] as WalletQuery);
      return const CouponListResult(coupons: [], fromCache: false);
    });

    await tester.pumpWidget(wrap(repo));
    await tester.pumpAndSettle();

    await tester.tap(find.text('사용 완료'));
    await tester.pumpAndSettle();

    expect(captured.last.status, 'REDEEMED');
    expect(find.text('조건에 맞는 쿠폰이 없어요.'), findsOneWidget);
  });

  testWidgets('search submits a text query', (tester) async {
    final repo = MockCouponRepository();
    final captured = <WalletQuery>[];
    when(() => repo.getCoupons(query: any(named: 'query'))).thenAnswer((invocation) async {
      captured.add(invocation.namedArguments[#query] as WalletQuery);
      return const CouponListResult(coupons: [], fromCache: false);
    });

    await tester.pumpWidget(wrap(repo));
    await tester.pumpAndSettle();

    await tester.enterText(find.byType(TextField), '스타벅스');
    await tester.testTextInput.receiveAction(TextInputAction.search);
    await tester.pumpAndSettle();

    expect(captured.last.q, '스타벅스');
  });

  testWidgets('shows the offline banner for cached data', (tester) async {
    final repo = MockCouponRepository();
    when(() => repo.getCoupons(query: any(named: 'query'))).thenAnswer(
      (_) async => CouponListResult(
        coupons: [coupon('c1', '스타벅스')],
        fromCache: true,
        syncedAt: DateTime.utc(2026, 8, 5, 12),
      ),
    );

    await tester.pumpWidget(wrap(repo));
    await tester.pumpAndSettle();

    expect(find.textContaining('오프라인'), findsOneWidget);
  });

  testWidgets('shows the user-facing error and a retry button on failure', (tester) async {
    final repo = MockCouponRepository();
    when(() => repo.getCoupons(query: any(named: 'query')))
        .thenThrow(const NetworkException());

    await tester.pumpWidget(wrap(repo));
    await tester.pumpAndSettle();

    expect(find.text('네트워크 연결을 확인해 주세요.'), findsOneWidget);
    expect(find.text('다시 시도'), findsOneWidget);

    when(() => repo.getCoupons(query: any(named: 'query'))).thenAnswer(
      (_) async =>
          CouponListResult(coupons: [coupon('c1', '스타벅스')], fromCache: false),
    );
    await tester.tap(find.text('다시 시도'));
    await tester.pumpAndSettle();
    expect(find.text('스타벅스'), findsOneWidget);
  });
}
