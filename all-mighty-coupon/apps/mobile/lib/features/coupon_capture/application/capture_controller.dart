import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/errors/app_exception.dart';
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

/// Three-Second Capture: pick → upload → hand off to the review screen while
/// the server analyzes asynchronously.
class CaptureController extends Notifier<CaptureState> {
  @override
  CaptureState build() => const CaptureIdle();

  Future<void> captureFromGallery() =>
      _run(() => ref.read(imageSourcePickerProvider).pickFromGallery(), 'PHOTO_LIBRARY');

  Future<void> captureFromCamera() =>
      _run(() => ref.read(imageSourcePickerProvider).pickFromCamera(), 'CAMERA');

  void reset() => state = const CaptureIdle();

  Future<void> _run(Future<PickedImage?> Function() pick, String sourceType) async {
    try {
      final picked = await pick();
      if (picked == null) return; // user cancelled — stay idle
      state = const CaptureUploading();
      final id = await ref.read(couponUploadApiProvider).uploadImage(
            bytes: picked.bytes,
            filename: picked.filename,
            sourceType: sourceType,
          );
      state = CaptureUploaded(id);
    } on AppException catch (error) {
      state = CaptureFailed(error.userMessage);
    }
  }
}

final captureControllerProvider =
    NotifierProvider<CaptureController, CaptureState>(CaptureController.new);
