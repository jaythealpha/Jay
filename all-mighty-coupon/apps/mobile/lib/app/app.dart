import 'package:flutter/material.dart';

import 'router.dart';
import 'theme/app_theme.dart';

class AmcApp extends StatelessWidget {
  const AmcApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      title: 'All Mighty Coupon',
      theme: buildAppTheme(),
      routerConfig: appRouter,
      debugShowCheckedModeBanner: false,
    );
  }
}
