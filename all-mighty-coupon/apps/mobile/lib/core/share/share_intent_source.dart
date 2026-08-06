import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:receive_sharing_intent/receive_sharing_intent.dart';

/// Three-Second Capture via the OS share sheet: 쿠폰 화면 → 공유 → 앱 →
/// 자동 등록. Emits local file paths of images shared into the app.
abstract interface class ShareIntentSource {
  /// Image shared while the app was closed (cold start), if any.
  Future<String?> initialSharedImagePath();

  /// Images shared while the app is running.
  Stream<String> sharedImagePaths();
}

/// receive_sharing_intent implementation. Android is wired via the manifest
/// intent-filter; the iOS share extension target is NOT configured yet
/// (needs an Xcode-managed extension) — documented as unimplemented.
class ReceiveSharingIntentSource implements ShareIntentSource {
  @override
  Future<String?> initialSharedImagePath() async {
    final media = await ReceiveSharingIntent.instance.getInitialMedia();
    final image = media.where((f) => f.type == SharedMediaType.image).firstOrNull;
    if (image != null) {
      await ReceiveSharingIntent.instance.reset();
    }
    return image?.path;
  }

  @override
  Stream<String> sharedImagePaths() {
    return ReceiveSharingIntent.instance
        .getMediaStream()
        .expand((files) => files)
        .where((f) => f.type == SharedMediaType.image)
        .map((f) => f.path);
  }
}

final shareIntentSourceProvider =
    Provider<ShareIntentSource>((ref) => ReceiveSharingIntentSource());
