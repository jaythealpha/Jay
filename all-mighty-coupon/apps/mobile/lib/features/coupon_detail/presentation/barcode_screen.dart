import 'package:barcode_widget/barcode_widget.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/theme/app_theme.dart';
import '../../../core/errors/app_exception.dart';
import '../application/barcode_controller.dart';

/// In-store display (spec §15): white background, maximum contrast, enlarged
/// code, works offline via the secure vault. Screen-brightness boost is a
/// platform integration slot (M2 note: needs on-device verification).
class BarcodeScreen extends ConsumerWidget {
  const BarcodeScreen({super.key, required this.couponId});

  final String couponId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(barcodeControllerProvider(couponId));

    return Scaffold(
      backgroundColor: Colors.white,
      appBar: AppBar(title: const Text('바코드'), backgroundColor: Colors.white),
      body: state.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(Icons.qr_code_2_outlined, size: 48, color: AmcColors.textSecondary),
                const SizedBox(height: 12),
                Text(
                  error is AppException
                      ? error.userMessage
                      : '바코드를 불러오지 못했어요.',
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 16),
                SizedBox(
                  height: 48,
                  child: FilledButton(
                    onPressed: () => ref.invalidate(barcodeControllerProvider(couponId)),
                    child: const Text('다시 시도'),
                  ),
                ),
              ],
            ),
          ),
        ),
        data: (view) => _BarcodeBody(view: view),
      ),
    );
  }
}

class _BarcodeBody extends StatelessWidget {
  const _BarcodeBody({required this.view});

  final BarcodeView view;

  static Barcode? _barcodeFor(String? format) => switch (format) {
        'Code128' => Barcode.code128(),
        'Code39' => Barcode.code39(),
        'Code93' => Barcode.code93(),
        'EAN-13' || 'EAN13' => Barcode.ean13(),
        'EAN-8' || 'EAN8' => Barcode.ean8(),
        'UPC-A' || 'UPCA' => Barcode.upcA(),
        'ITF' => Barcode.itf(),
        'QRCode' || 'QR_CODE' => Barcode.qrCode(),
        'DataMatrix' => Barcode.dataMatrix(),
        'Aztec' => Barcode.aztec(),
        'PDF417' => Barcode.pdf417(),
        _ => null,
      };

  @override
  Widget build(BuildContext context) {
    final barcode = _barcodeFor(view.barcode.format);
    final isSquare = view.barcode.format == 'QRCode' ||
        view.barcode.format == 'DataMatrix' ||
        view.barcode.format == 'Aztec';

    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            if (view.fromVault)
              Container(
                margin: const EdgeInsets.only(bottom: 16),
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                decoration: BoxDecoration(
                  color: AmcColors.primaryLight,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Text(
                  '오프라인 — 기기에 안전하게 저장된 바코드입니다',
                  style: TextStyle(fontSize: 12, color: AmcColors.textSecondary),
                ),
              ),
            if (barcode != null)
              BarcodeWidget(
                barcode: barcode,
                data: view.barcode.value,
                width: isSquare ? 260 : 320,
                height: isSquare ? 260 : 140,
                color: Colors.black,
                backgroundColor: Colors.white,
                errorBuilder: (context, error) => _FallbackValue(value: view.barcode.value),
              )
            else
              _FallbackValue(value: view.barcode.value),
            const SizedBox(height: 20),
            Text(
              view.barcode.value,
              textAlign: TextAlign.center,
              style: const TextStyle(
                fontSize: 18,
                letterSpacing: 2,
                fontWeight: FontWeight.w600,
                color: Colors.black,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              '매장 직원에게 이 화면을 보여주세요',
              style: TextStyle(color: Colors.grey.shade600),
            ),
          ],
        ),
      ),
    );
  }
}

class _FallbackValue extends StatelessWidget {
  const _FallbackValue({required this.value});

  final String value;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        border: Border.all(color: Colors.black, width: 2),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(
        value,
        textAlign: TextAlign.center,
        style: const TextStyle(fontSize: 24, fontWeight: FontWeight.bold, color: Colors.black),
      ),
    );
  }
}
