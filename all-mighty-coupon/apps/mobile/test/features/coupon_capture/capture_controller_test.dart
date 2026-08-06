import 'package:amc_mobile/core/errors/app_exception.dart';
import 'package:amc_mobile/core/ocr/device_ocr.dart';
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

class FakeDeviceOcr implements DeviceOcr {
  FakeDeviceOcr(this.text);

  final String? text;
  final List<String> requestedPaths = [];

  @override
  Future<String?> recognizeText(String imagePath) async {
    requestedPaths.add(imagePath);
    return text;
  }
}

ProviderContainer containerWith(
  ImageSourcePicker picker,
  CouponUploadApi api, {
  DeviceOcr? deviceOcr,
}) {
  final container = ProviderContainer(
    overrides: [
      imageSourcePickerProvider.overrideWithValue(picker),
      couponUploadApiProvider.overrideWithValue(api),
      deviceOcrProvider.overrideWithValue(deviceOcr ?? FakeDeviceOcr(null)),
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
        deviceOcrText: any(named: 'deviceOcrText'),
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
        deviceOcrText: any(named: 'deviceOcrText'),
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
        deviceOcrText: any(named: 'deviceOcrText'),
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
        deviceOcrText: any(named: 'deviceOcrText'),
      ),
    ).thenThrow(const NetworkException());

    final container = containerWith(FakePicker(image), api);
    await container.read(captureControllerProvider.notifier).captureFromGallery();

    final state = container.read(captureControllerProvider);
    expect(state, isA<CaptureFailed>());
    expect((state as CaptureFailed).message, '네트워크 연결을 확인해 주세요.');
  });

  test('runs on-device OCR when a file path exists and sends the text along', () async {
    final api = MockUploadApi();
    when(
      () => api.uploadImage(
        bytes: any(named: 'bytes'),
        filename: any(named: 'filename'),
        sourceType: any(named: 'sourceType'),
        deviceOcrText: any(named: 'deviceOcrText'),
      ),
    ).thenAnswer((_) async => 'new-id');
    final ocr = FakeDeviceOcr('스타벅스 아메리카노 유효기간 2027.01.31');
    final withPath = PickedImage(bytes: [1], filename: 'c.png', path: '/tmp/c.png');

    final container = containerWith(FakePicker(withPath), api, deviceOcr: ocr);
    await container.read(captureControllerProvider.notifier).captureFromGallery();

    expect(ocr.requestedPaths, ['/tmp/c.png']);
    verify(
      () => api.uploadImage(
        bytes: any(named: 'bytes'),
        filename: 'c.png',
        sourceType: 'PHOTO_LIBRARY',
        deviceOcrText: '스타벅스 아메리카노 유효기간 2027.01.31',
      ),
    ).called(1);
  });
}
