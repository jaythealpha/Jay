import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/errors/app_exception.dart';
import '../data/barcode_vault.dart';
import '../data/coupon_actions_api.dart';

class BarcodeView {
  const BarcodeView({required this.barcode, required this.fromVault});

  final RevealedBarcode barcode;

  /// True when served from the offline vault instead of the audited server
  /// endpoint — the UI labels it.
  final bool fromVault;
}

/// Server-first (audited reveal) with secure-vault fallback for offline use.
class BarcodeController extends AsyncNotifier<BarcodeView> {
  BarcodeController(this.couponId);

  final String couponId;

  @override
  Future<BarcodeView> build() async {
    final vault = ref.watch(barcodeVaultProvider);
    try {
      final barcode = await ref.watch(couponActionsApiProvider).revealBarcode(couponId);
      await vault.write(couponId, barcode);
      return BarcodeView(barcode: barcode, fromVault: false);
    } on NetworkException {
      final cached = await vault.read(couponId);
      if (cached == null) rethrow;
      return BarcodeView(barcode: cached, fromVault: true);
    }
  }
}

final barcodeControllerProvider =
    AsyncNotifierProvider.family<BarcodeController, BarcodeView, String>(BarcodeController.new);
