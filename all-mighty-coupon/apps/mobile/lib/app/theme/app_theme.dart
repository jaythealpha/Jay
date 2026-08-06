import 'package:flutter/material.dart';

/// Mirrors packages/design-tokens (kept in sync manually until token codegen).
/// Status colors are always shown together with an icon + text label —
/// color alone never carries meaning.
abstract final class AmcColors {
  static const primary = Color(0xFF1B5E4A);
  static const primaryLight = Color(0xFFE4F2ED);
  static const textPrimary = Color(0xFF1A1D1C);
  static const textSecondary = Color(0xFF5A6360);
  static const surface = Color(0xFFFFFFFF);
  static const background = Color(0xFFF6F8F7);
  static const border = Color(0xFFDCE3E0);
  static const statusActive = Color(0xFF1B5E4A);
  static const statusExpiringSoon = Color(0xFFB45309);
  static const statusExpired = Color(0xFF8A8F8D);
  static const statusRedeemed = Color(0xFF4B5563);
  static const statusNeedsReview = Color(0xFF1D4ED8);
  static const danger = Color(0xFFB3261E);
}

ThemeData buildAppTheme() {
  return ThemeData(
    useMaterial3: true,
    colorScheme: ColorScheme.fromSeed(
      seedColor: AmcColors.primary,
      surface: AmcColors.surface,
    ),
    scaffoldBackgroundColor: AmcColors.background,
    appBarTheme: const AppBarTheme(
      backgroundColor: AmcColors.background,
      foregroundColor: AmcColors.textPrimary,
      elevation: 0,
    ),
  );
}
