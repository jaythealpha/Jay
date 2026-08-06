import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../core/auth/auth_controller.dart';
import '../features/auth/presentation/login_screen.dart';
import '../features/coupon_capture/presentation/capture_screen.dart';
import '../features/coupon_detail/presentation/barcode_screen.dart';
import '../features/coupon_detail/presentation/coupon_detail_screen.dart';
import '../features/coupon_review/presentation/review_screen.dart';
import '../features/coupon_wallet/presentation/wallet_screen.dart';
import '../features/home/presentation/home_screen.dart';

/// Auth-aware router: unauthenticated users land on /login, everything else
/// requires a session. Rebuilt through Riverpod when the auth state changes.
final routerProvider = Provider<GoRouter>((ref) {
  final authState = ref.watch(authControllerProvider);

  return GoRouter(
    initialLocation: '/',
    redirect: (context, state) {
      final loggingIn = state.matchedLocation == '/login';
      switch (authState) {
        case AuthUnknown():
          return state.matchedLocation == '/splash' ? null : '/splash';
        case Unauthenticated():
          return loggingIn ? null : '/login';
        case Authenticated():
          return loggingIn || state.matchedLocation == '/splash' ? '/' : null;
      }
    },
    routes: [
      GoRoute(
        path: '/splash',
        builder: (context, state) =>
            const Scaffold(body: Center(child: CircularProgressIndicator())),
      ),
      GoRoute(path: '/login', builder: (context, state) => const LoginScreen()),
      GoRoute(
        path: '/',
        builder: (context, state) => const HomeScreen(),
        routes: [
          GoRoute(path: 'wallet', builder: (context, state) => const WalletScreen()),
          GoRoute(path: 'capture', builder: (context, state) => const CaptureScreen()),
          GoRoute(
            path: 'review/:id',
            builder: (context, state) =>
                ReviewScreen(couponId: state.pathParameters['id'] ?? ''),
          ),
          GoRoute(
            path: 'coupon/:id',
            builder: (context, state) =>
                CouponDetailScreen(couponId: state.pathParameters['id'] ?? ''),
            routes: [
              GoRoute(
                path: 'barcode',
                builder: (context, state) =>
                    BarcodeScreen(couponId: state.pathParameters['id'] ?? ''),
              ),
            ],
          ),
        ],
      ),
    ],
  );
});
