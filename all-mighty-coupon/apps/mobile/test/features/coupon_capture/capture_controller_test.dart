import 'package:amc_mobile/core/errors/app_exception.dart';
import 'package:amc_mobile/features/coupon_capture/application/capture_controller.dart';
import 'package:amc_mobile/features/coupon_capture/data/coupon_upload_api.dart';
import 'package:amc_mobile/features/coupon_capture/data/image_source_picker.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

class MockUploadApi extends Mock implements CouponUploadApi {}

class FakePicker implements ImageSourcePicker {
  FakePicker(this.result);

  final PickedImage? result;
  String? lastSource;

  @override
  Future<PickedImage?> pickFromCamera() async {
    lastSource = 'camera';
    return result;
  }

  @override
  Future<PickedImage?> pickFromGallery() async {
    lastSource = 'gallery';
    return result;
  }
}

ProviderContainer containerWith(ImageSourcePicker picker, CouponUploadApi api) {
  final container = ProviderContainer(
    overrides: [
      imageSourcePickerProvider.overrideWithValue(picker),
      couponUploadApiProvider.overrideWithValue(api),
    ],
  );
  addTearDown(container.dispose);
  return container;
}

void main() {
  final image = PickedImage(bytes: [1, 2, 3], filename: 'coupon.png');

  test('gallery pick uploads with PHOTO_LIBRARY and lands on Uploaded', () async {
    final api = MockUploadApi();
    when(
      () => api.uploadImage(
        bytes: any(named: 'bytes'),
        filename: any(named: 'filename'),
        sourceType: any(named: 'sourceType'),
      ),
    ).thenAnswer((_) async => 'new-id');

    final container = containerWith(FakePicker(image), api);
    await container.read(captureControllerProvider.notifier).captureFromGallery();

    final state = container.read(captureControllerProvider);
    expect(state, isA<CaptureUploaded>());
    expect((state as CaptureUploaded).couponId, 'new-id');
    verify(
      () => api.uploadImage(
        bytes: any(named: 'bytes'),
        filename: 'coupon.png',
        sourceType: 'PHOTO_LIBRARY',
      ),
    ).called(1);
  });

  test('cancelling the picker keeps the screen idle (no upload)', () async {
    final api = MockUploadApi();
    final container = containerWith(FakePicker(null), api);

    await container.read(captureControllerProvider.notifier).captureFromCamera();

    expect(container.read(captureControllerProvider), isA<CaptureIdle>());
    verifyNever(
      () => api.uploadImage(
        bytes: any(named: 'bytes'),
        filename: any(named: 'filename'),
        sourceType: any(named: 'sourceType'),
      ),
    );
  });

  test('upload failure surfaces the user-facing message', () async {
    final api = MockUploadApi();
    when(
      () => api.uploadImage(
        bytes: any(named: 'bytes'),
        filename: any(named: 'filename'),
        sourceType: any(named: 'sourceType'),
      ),
    ).thenThrow(const NetworkException());

    final container = containerWith(FakePicker(image), api);
    await container.read(captureControllerProvider.notifier).captureFromGallery();

    final state = container.read(captureControllerProvider);
    expect(state, isA<CaptureFailed>());
    expect((state as CaptureFailed).message, '네트워크 연결을 확인해 주세요.');
  });
}
