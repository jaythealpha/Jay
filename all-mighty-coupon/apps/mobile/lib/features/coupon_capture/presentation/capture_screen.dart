import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/theme/app_theme.dart';
import '../application/capture_controller.dart';

class CaptureScreen extends ConsumerWidget {
  const CaptureScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    ref.listen<CaptureState>(captureControllerProvider, (previous, next) {
      if (next is CaptureUploaded) {
        ref.read(captureControllerProvider.notifier).reset();
        context.go('/review/${next.couponId}');
      }
    });
    final state = ref.watch(captureControllerProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('쿠폰 등록')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: switch (state) {
          CaptureUploading() => const Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  CircularProgressIndicator(),
                  SizedBox(height: 16),
                  Text('이미지를 업로드하고 있어요...'),
                ],
              ),
            ),
          CaptureFailed(:final message) => Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const Icon(Icons.error_outline, size: 48, color: AmcColors.danger),
                  const SizedBox(height: 12),
                  Text(message, textAlign: TextAlign.center),
                  const SizedBox(height: 16),
                  SizedBox(
                    height: 48,
                    child: FilledButton(
                      onPressed: () => ref.read(captureControllerProvider.notifier).reset(),
                      child: const Text('다시 시도'),
                    ),
                  ),
                ],
              ),
            ),
          _ => Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const Text(
                  '쿠폰 이미지를 선택하면 브랜드·상품·유효기간·금액을 자동으로 인식해요.',
                  style: TextStyle(color: AmcColors.textSecondary),
                ),
                const SizedBox(height: 24),
                SizedBox(
                  height: 56,
                  child: FilledButton.icon(
                    onPressed: () =>
                        ref.read(captureControllerProvider.notifier).captureFromCamera(),
                    icon: const Icon(Icons.photo_camera_outlined),
                    label: const Text('카메라로 촬영'),
                  ),
                ),
                const SizedBox(height: 12),
                SizedBox(
                  height: 56,
                  child: OutlinedButton.icon(
                    onPressed: () =>
                        ref.read(captureControllerProvider.notifier).captureFromGallery(),
                    icon: const Icon(Icons.photo_library_outlined),
                    label: const Text('사진첩에서 선택'),
                  ),
                ),
              ],
            ),
        },
      ),
    );
  }
}
