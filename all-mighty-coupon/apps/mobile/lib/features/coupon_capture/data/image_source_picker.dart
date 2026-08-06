import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';

/// Picked image payload, decoupled from the image_picker plugin types so the
/// application layer (and tests) never touch platform channels.
class PickedImage {
  const PickedImage({required this.bytes, required this.filename});

  final List<int> bytes;
  final String filename;
}

abstract interface class ImageSourcePicker {
  /// Returns null when the user cancels the picker.
  Future<PickedImage?> pickFromGallery();
  Future<PickedImage?> pickFromCamera();
}

class ImagePickerSourcePicker implements ImageSourcePicker {
  final ImagePicker _picker = ImagePicker();

  Future<PickedImage?> _pick(ImageSource source) async {
    final file = await _picker.pickImage(source: source, maxWidth: 2400, imageQuality: 92);
    if (file == null) return null;
    return PickedImage(bytes: await file.readAsBytes(), filename: file.name);
  }

  @override
  Future<PickedImage?> pickFromGallery() => _pick(ImageSource.gallery);

  @override
  Future<PickedImage?> pickFromCamera() => _pick(ImageSource.camera);
}

final imageSourcePickerProvider = Provider<ImageSourcePicker>((ref) => ImagePickerSourcePicker());
