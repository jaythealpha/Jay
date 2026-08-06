import 'package:amc_mobile/core/errors/app_exception.dart';
import 'package:amc_mobile/features/coupon_detail/application/barcode_controller.dart';
import 'package:amc_mobile/features/coupon_detail/data/barcode_vault.dart';
import 'package:amc_mobile/features/coupon_detail/data/coupon_actions_api.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

class MockActionsApi extends Mock implements CouponActionsApi {}

class InMemoryBarcodeVault implements BarcodeVault {
  final Map<String, RevealedBarcode> store = {};

  @override
  Future<RevealedBarcode?> read(String couponId) async => store[couponId];

  @override
  Future<void> write(String couponId, RevealedBarcode barcode) async =>
      store[couponId] = barcode;

  @override
  Future<void> clear(String couponId) async => store.remove(couponId);
}

ProviderContainer containerWith(CouponActionsApi api, BarcodeVault vault) {
  final container = ProviderContainer(
    // v3 retries failing providers with backoff by default — disabled so the
    // error-path test can observe the failure deterministically.
    retry: (retryCount, error) => null,
    overrides: [
      couponActionsApiProvider.overrideWithValue(api),
      barcodeVaultProvider.overrideWithValue(vault),
    ],
  );
  addTearDown(container.dispose);
  return container;
}

void main() {
  test('online reveal serves the server value and fills the offline vault', () async {
    final api = MockActionsApi();
    final vault = InMemoryBarcodeVault();
    when(() => api.revealBarcode('c1')).thenAnswer(
      (_) async => const RevealedBarcode(value: '880123456789', format: 'Code128'),
    );

    final view = await containerWith(api, vault).read(barcodeControllerProvider('c1').future);

    expect(view.fromVault, false);
    expect(view.barcode.value, '880123456789');
    expect(vault.store['c1']?.value, '880123456789');
  });

  test('offline falls back to the secure vault, labeled as such', () async {
    final api = MockActionsApi();
    final vault = InMemoryBarcodeVault()
      ..store['c1'] = const RevealedBarcode(value: 'CACHED-999', format: 'QRCode');
    when(() => api.revealBarcode('c1')).thenThrow(const NetworkException());

    final view = await containerWith(api, vault).read(barcodeControllerProvider('c1').future);

    expect(view.fromVault, true);
    expect(view.barcode.value, 'CACHED-999');
  });

  test('offline with an empty vault surfaces the network error', () async {
    final api = MockActionsApi();
    when(() => api.revealBarcode('c1')).thenThrow(const NetworkException());

    final container = containerWith(api, InMemoryBarcodeVault());
    // Keep the provider alive while its future settles (v3 auto-dispose).
    final sub = container.listen(barcodeControllerProvider('c1').future, (_, _) {});
    await expectLater(sub.read(), throwsA(isA<NetworkException>()));
    sub.close();
  });
}
