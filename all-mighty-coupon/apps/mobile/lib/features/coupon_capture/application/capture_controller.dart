import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/errors/app_exception.dart';
import '../../../core/ocr/device_ocr.dart';
import '../data/coupon_upload_api.dart';
import '../data/image_source_picker.dart';

@immutable
sealed class CaptureState {
  const CaptureState();
}

class CaptureIdle extends CaptureState {
  const CaptureIdle();
}

class CaptureUploading extends CaptureState {
  const CaptureUploading();
}

class CaptureUploaded extends CaptureState {
  const CaptureUploaded(this.couponId);

  final String couponId;
}

class CaptureFailed extends CaptureState {
  const CaptureFailed(this.message);

  final String message;
}

/// Three-Second Capture: pick (or receive via share sheet) → on-device OCR
/// best-effort → upload → hand off to the review screen while the server
/// analyzes asynchronously.
class CaptureController extends Notifier<CaptureState> {
  @override
  CaptureState build() => const CaptureIdle();

  Future<void> captureFromGallery() =>
      _run(() => ref.read(imageSourcePickerProvider).pickFromGallery(), 'PHOTO_LIBRARY');

  Future<void> captureFromCamera() =>
      _run(() => ref.read(imageSourcePickerProvider).pickFromCamera(), 'CAMERA');

  /// Entry point for OS share-sheet images (공유 → All Mighty Coupon).
  Future<void> captureFromSharedFile(String path) => _run(() async {
        final bytes = await File(path).readAsBytes();
        final filename = path.split('/').last;
        return PickedImage(bytes: bytes, filename: filename, path: path);
      }, 'SHARE_EXTENSION');

  void reset() => state = const CaptureIdle();

  Future<void> _run(Future<PickedImage?> Function() pick, String sourceType) async {
    try {
      final picked = await pick();
      if (picked == null) return; // user cancelled — stay idle
      state = const CaptureUploading();

      // Device OCR first (spec §10) — a failure here must never block upload.
      String? deviceOcrText;
      if (picked.path != null) {
        deviceOcrText = await ref.read(deviceOcrProvider).recognizeText(picked.path!);
      }

      final id = await ref.read(couponUploadApiProvider).uploadImage(
            bytes: picked.bytes,
            filename: picked.filename,
            sourceType: sourceType,
            deviceOcrText: deviceOcrText,
          );
      state = CaptureUploaded(id);
    } on AppException catch (error) {
      state = CaptureFailed(error.userMessage);
    } catch (_) {
      state = const CaptureFailed('이미지를 읽지 못했어요. 다른 이미지로 시도해 주세요.');
    }
  }
}

final captureControllerProvider =
    NotifierProvider<CaptureController, CaptureState>(CaptureController.new);
