import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import 'coupon_actions_api.dart';

/// Offline barcode display (spec §2.6/§15): once revealed, the barcode is
/// kept in the platform secure storage — never SharedPreferences — so it can
/// be shown at the till without a connection.
abstract interface class BarcodeVault {
  Future<RevealedBarcode?> read(String couponId);
  Future<void> write(String couponId, RevealedBarcode barcode);
  Future<void> clear(String couponId);
}

class SecureBarcodeVault implements BarcodeVault {
  final FlutterSecureStorage _storage = const FlutterSecureStorage();

  String _key(String couponId) => 'amc.barcode.$couponId';

  @override
  Future<RevealedBarcode?> read(String couponId) async {
    final raw = await _storage.read(key: _key(couponId));
    if (raw == null) return null;
    final json = jsonDecode(raw) as Map<String, dynamic>;
    return RevealedBarcode(
      value: json['value'] as String? ?? '',
      format: json['format'] as String?,
    );
  }

  @override
  Future<void> write(String couponId, RevealedBarcode barcode) => _storage.write(
        key: _key(couponId),
        value: jsonEncode({'value': barcode.value, 'format': barcode.format}),
      );

  @override
  Future<void> clear(String couponId) => _storage.delete(key: _key(couponId));
}

final barcodeVaultProvider = Provider<BarcodeVault>((ref) => SecureBarcodeVault());
