import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_mlkit_text_recognition/google_mlkit_text_recognition.dart';

/// On-device OCR boundary (spec §10: 기기 내 OCR 우선). The recognized text
/// rides along with the upload; the server parses it and falls back to its
/// own OCR provider when this returns null.
abstract interface class DeviceOcr {
  /// Returns null when OCR is unavailable or fails — never throws upward,
  /// because capture must succeed even without on-device recognition.
  Future<String?> recognizeText(String imagePath);
}

/// Google ML Kit implementation. Runs only on real Android/iOS devices —
/// on-device behavior is UNVERIFIED in CI (no emulator); tests use fakes.
class MlkitDeviceOcr implements DeviceOcr {
  @override
  Future<String?> recognizeText(String imagePath) async {
    if (kIsWeb) return null;
    final recognizer = TextRecognizer(script: TextRecognitionScript.korean);
    try {
      final result = await recognizer.processImage(InputImage.fromFilePath(imagePath));
      final text = result.text.trim();
      return text.isEmpty ? null : text;
    } catch (_) {
      // Missing ML Kit runtime (simulator, unsupported device) — fall back to
      // server-side OCR silently.
      return null;
    } finally {
      await recognizer.close();
    }
  }
}

final deviceOcrProvider = Provider<DeviceOcr>((ref) => MlkitDeviceOcr());
