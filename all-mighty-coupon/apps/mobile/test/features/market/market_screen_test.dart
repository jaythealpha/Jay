import 'package:amc_mobile/features/market/data/market_api.dart';
import 'package:amc_mobile/features/market/presentation/market_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

class MockMarketApi extends Mock implements MarketApi {}

MarketListing listing(String id, String brand, int price, {bool mine = false}) =>
    MarketListing.fromJson(<String, dynamic>{
      'id': id,
      'priceMinor': price,
      'feeMinor': 200,
      'mine': mine,
      'coupon': <String, dynamic>{
        'brandName': brand,
        'productName': '$brand 상품권',
        'faceValueMinor': price + 1000,
        'expiresAt':
            DateTime.now().add(const Duration(days: 10)).toUtc().toIso8601String(),
      },
    });

Widget wrap(MarketApi api) {
  return ProviderScope(
    overrides: [marketApiProvider.overrideWithValue(api)],
    child: const MaterialApp(home: MarketScreen()),
  );
}

void main() {
  testWidgets('shows the mock-payment banner and listings with buy buttons', (tester) async {
    final api = MockMarketApi();
    when(() => api.browse(q: any(named: 'q'))).thenAnswer(
      (_) async => [listing('l1', '스타벅스', 4000), listing('l2', '이마트', 25000, mine: true)],
    );

    await tester.pumpWidget(wrap(api));
    await tester.pumpAndSettle();

    expect(find.textContaining('모의(MOCK)'), findsOneWidget);
    expect(find.text('스타벅스'), findsOneWidget);
    expect(find.text('4,000원'), findsOneWidget);
    expect(find.text('구매'), findsOneWidget); // only for the foreign listing
    expect(find.text('판매 취소'), findsOneWidget); // for my own listing
  });

  testWidgets('purchase asks for confirmation and calls the API', (tester) async {
    final api = MockMarketApi();
    when(() => api.browse(q: any(named: 'q')))
        .thenAnswer((_) async => [listing('l1', '스타벅스', 4000)]);
    when(() => api.purchase('l1')).thenAnswer((_) async {});

    await tester.pumpWidget(wrap(api));
    await tester.pumpAndSettle();

    await tester.tap(find.text('구매'));
    await tester.pumpAndSettle();
    expect(find.text('쿠폰을 구매할까요?'), findsOneWidget);

    await tester.tap(find.text('구매').last);
    await tester.pumpAndSettle();

    verify(() => api.purchase('l1')).called(1);
    expect(find.text('구매 완료! 쿠폰함에서 확인하세요.'), findsOneWidget);
  });

  testWidgets('surfaces server-side market errors verbatim', (tester) async {
    final api = MockMarketApi();
    when(() => api.browse(q: any(named: 'q')))
        .thenAnswer((_) async => [listing('l1', '스타벅스', 4000)]);
    when(() => api.purchase('l1'))
        .thenThrow(const MarketException('다른 구매자가 먼저 구매했습니다.'));

    await tester.pumpWidget(wrap(api));
    await tester.pumpAndSettle();

    await tester.tap(find.text('구매'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('구매').last);
    await tester.pumpAndSettle();

    expect(find.text('다른 구매자가 먼저 구매했습니다.'), findsOneWidget);
  });

  testWidgets('empty market shows a friendly message', (tester) async {
    final api = MockMarketApi();
    when(() => api.browse(q: any(named: 'q'))).thenAnswer((_) async => []);

    await tester.pumpWidget(wrap(api));
    await tester.pumpAndSettle();

    expect(find.text('판매 중인 쿠폰이 없어요.'), findsOneWidget);
  });
}
