import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../network/api_client.dart';

/// Server-side device registration for expiration pushes. The FCM token
/// itself comes from a PushTokenSource; without Firebase configuration the
/// NoopPushTokenSource keeps push registration silently off and the in-app
/// feed remains the delivery channel.
class DevicesApi {
  DevicesApi(this._dio);

  final Dio _dio;

  Future<void> register(String token, String platform) async {
    try {
      await _dio.post<void>('/v1/devices', data: {'token': token, 'platform': platform});
    } on DioException catch (error) {
      throw mapDioError(error);
    }
  }

  Future<void> unregister(String token) async {
    try {
      await _dio.delete<void>('/v1/devices', data: {'token': token});
    } on DioException catch (error) {
      throw mapDioError(error);
    }
  }
}

final devicesApiProvider = Provider<DevicesApi>((ref) => DevicesApi(ref.watch(dioProvider)));

/// Boundary for the platform push token (FCM registration token).
abstract interface class PushTokenSource {
  /// Null when push is unavailable (no Firebase config, permission denied).
  Future<String?> currentToken();
}

/// Placeholder until firebase_messaging is wired with a real Firebase project
/// (google-services.json / GoogleService-Info.plist). Push registration is a
/// documented no-op without it — UNIMPLEMENTED, not silently fake.
class NoopPushTokenSource implements PushTokenSource {
  @override
  Future<String?> currentToken() async => null;
}

final pushTokenSourceProvider = Provider<PushTokenSource>((ref) => NoopPushTokenSource());

/// Call after login: registers this device when a push token exists.
Future<void> registerDeviceForPush(Ref ref, {required String platform}) async {
  final token = await ref.read(pushTokenSourceProvider).currentToken();
  if (token == null) return;
  await ref.read(devicesApiProvider).register(token, platform);
}
