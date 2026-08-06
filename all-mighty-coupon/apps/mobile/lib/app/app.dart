import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/auth/auth_controller.dart';
import '../core/share/share_intent_source.dart';
import '../features/coupon_capture/application/capture_controller.dart';
import 'router.dart';
import 'theme/app_theme.dart';

class AmcApp extends ConsumerStatefulWidget {
  const AmcApp({super.key});

  @override
  ConsumerState<AmcApp> createState() => _AmcAppState();
}

class _AmcAppState extends ConsumerState<AmcApp> {
  StreamSubscription<String>? _shareSubscription;

  @override
  void initState() {
    super.initState();
    _bindShareIntents();
  }

  /// 공유 → All Mighty Coupon → 자동 등록 (Three-Second Capture). Shared
  /// images upload immediately; navigation to the review screen happens via
  /// the app-level CaptureUploaded listener below.
  void _bindShareIntents() {
    final source = ref.read(shareIntentSourceProvider);
    unawaited(
      source.initialSharedImagePath().then((path) {
        if (path != null) _handleSharedImage(path);
      }).catchError((_) => null),
    );
    _shareSubscription = source.sharedImagePaths().listen(
          _handleSharedImage,
          onError: (Object _) {},
        );
  }

  void _handleSharedImage(String path) {
    // Shared coupons need a session; unauthenticated shares land on /login
    // via the router redirect and are simply dropped.
    if (ref.read(authControllerProvider) is! Authenticated) return;
    unawaited(ref.read(captureControllerProvider.notifier).captureFromSharedFile(path));
  }

  @override
  void dispose() {
    unawaited(_shareSubscription?.cancel());
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final router = ref.watch(routerProvider);
    // Global capture hand-off: whichever path produced the upload (capture
    // screen or share sheet), the review screen opens next.
    ref.listen<CaptureState>(captureControllerProvider, (previous, next) {
      if (next is CaptureUploaded) {
        ref.read(captureControllerProvider.notifier).reset();
        router.go('/review/${next.couponId}');
      }
    });

    return MaterialApp.router(
      title: 'All Mighty Coupon',
      theme: buildAppTheme(),
      routerConfig: router,
      debugShowCheckedModeBanner: false,
    );
  }
}
