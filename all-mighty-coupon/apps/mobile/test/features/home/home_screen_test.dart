import 'package:amc_mobile/features/home/data/health_api.dart';
import 'package:amc_mobile/features/home/data/home_api.dart';
import 'package:amc_mobile/features/home/presentation/home_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:mocktail/mocktail.dart';

class MockHomeApi extends Mock implements HomeApi {}

class MockHealthApi extends Mock implements HealthApi {}

Map<String, dynamic> coupon(String id, String brand, {String? expiresAt, int? value}) =>
    <String, dynamic>{
      'id': id,
      'brandName': brand,
      'productName': '$brand 상품',
      'faceValueMinor': value,
      'status': 'EXPIRING_SOON',
      'expiresAt': expiresAt,
      'createdAt': '2026-08-01T00:00:00.000Z',
    };

HomeSummary summaryFixture() => HomeSummary.fromJson(<String, dynamic>{
      'expiringSoon': [
        coupon('c1', '스타벅스',
            expiresAt: DateTime.now().add(const Duration(days: 2)).toUtc().toIso8601String()),
      ],
      'useThisWeek': [
        coupon('c2', '이마트',
            expiresAt: DateTime.now().add(const Duration(days: 6)).toUtc().toIso8601String(),
            value: 30000),
      ],
      'recent': [coupon('c3', '교촌치킨')],
      'counts': {'active': 3, 'expiringSoon': 1, 'redeemed': 2, 'needsReview': 1, 'total': 7},
      'totalValueMinor': 57000,
    });

Widget wrap(HomeApi homeApi, HealthApi healthApi) {
  final router = GoRouter(
    initialLocation: '/',
    routes: [
      GoRoute(path: '/', builder: (context, state) => const HomeScreen()),
      GoRoute(
        path: '/coupon/:id',
        builder: (context, state) => Scaffold(body: Text('detail-${state.pathParameters['id']}')),
      ),
      GoRoute(
        path: '/notifications',
        builder: (context, state) => const Scaffold(body: Text('notifications-stub')),
      ),
      GoRoute(path: '/capture', builder: (context, state) => const Scaffold(body: Text('capture-stub'))),
      GoRoute(path: '/wallet', builder: (context, state) => const Scaffold(body: Text('wallet-stub'))),
    ],
  );
  return ProviderScope(
    overrides: [
      homeApiProvider.overrideWithValue(homeApi),
      healthApiProvider.overrideWithValue(healthApi),
    ],
    child: MaterialApp.router(routerConfig: router),
  );
}

void main() {
  setUp(() {
    registerFallbackValue(Uri());
  });

  MockHealthApi healthyApi() {
    final api = MockHealthApi();
    when(() => api.fetchHealth()).thenAnswer(
      (_) async => HealthStatus.fromJson(<String, dynamic>{
        'status': 'ok',
        'components': {'database': 'up', 'redis': 'up'},
        'checkedAt': '2026-08-06T00:00:00.000Z',
      }),
    );
    return api;
  }

  testWidgets('renders action-first sections and the summary', (tester) async {
    tester.view.physicalSize = const Size(1080, 2800);
    tester.view.devicePixelRatio = 2.0;
    addTearDown(tester.view.reset);

    final homeApi = MockHomeApi();
    when(() => homeApi.fetchSummary()).thenAnswer((_) async => summaryFixture());

    await tester.pumpWidget(wrap(homeApi, healthyApi()));
    await tester.pumpAndSettle();

    expect(find.text('곧 만료돼요 ⏰'), findsOneWidget);
    expect(find.text('스타벅스'), findsOneWidget);
    expect(find.text('D-2'), findsOneWidget);
    expect(find.text('이번 주 사용하세요'), findsOneWidget);
    expect(find.text('최근 등록'), findsOneWidget);
    expect(find.text('내 쿠폰 요약'), findsOneWidget);
    expect(find.text('총 7개 쿠폰'), findsOneWidget);
    expect(find.text('57,000원'), findsOneWidget);
    expect(find.text('서버 연결됨'), findsOneWidget);
  });

  testWidgets('tapping an expiring coupon deep-links to its detail', (tester) async {
    tester.view.physicalSize = const Size(1080, 2800);
    tester.view.devicePixelRatio = 2.0;
    addTearDown(tester.view.reset);

    final homeApi = MockHomeApi();
    when(() => homeApi.fetchSummary()).thenAnswer((_) async => summaryFixture());

    await tester.pumpWidget(wrap(homeApi, healthyApi()));
    await tester.pumpAndSettle();

    await tester.tap(find.text('스타벅스'));
    await tester.pumpAndSettle();

    expect(find.text('detail-c1'), findsOneWidget);
  });

  testWidgets('shows the error state with retry when home fails', (tester) async {
    final homeApi = MockHomeApi();
    when(() => homeApi.fetchSummary()).thenThrow(Exception('down'));

    await tester.pumpWidget(wrap(homeApi, healthyApi()));
    await tester.pumpAndSettle();

    expect(find.text('홈 정보를 불러오지 못했어요.'), findsOneWidget);
    expect(find.text('다시 시도'), findsOneWidget);
  });
}
