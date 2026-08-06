import 'package:go_router/go_router.dart';

import '../features/coupon_capture/presentation/capture_screen.dart';
import '../features/coupon_review/presentation/review_screen.dart';
import '../features/coupon_wallet/presentation/wallet_screen.dart';
import '../features/home/presentation/home_screen.dart';

final appRouter = GoRouter(
  routes: [
    GoRoute(
      path: '/',
      builder: (context, state) => const HomeScreen(),
      routes: [
        GoRoute(
          path: 'wallet',
          builder: (context, state) => const WalletScreen(),
        ),
        GoRoute(
          path: 'capture',
          builder: (context, state) => const CaptureScreen(),
        ),
        GoRoute(
          path: 'review/:id',
          builder: (context, state) =>
              ReviewScreen(couponId: state.pathParameters['id'] ?? ''),
        ),
      ],
    ),
  ],
);
