import 'package:go_router/go_router.dart';

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
      ],
    ),
  ],
);
