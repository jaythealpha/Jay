import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/api_client.dart';

@immutable
class ExpirationNotification {
  const ExpirationNotification({
    required this.id,
    required this.couponId,
    required this.message,
    required this.sentAt,
  });

  factory ExpirationNotification.fromJson(Map<String, dynamic> json) => ExpirationNotification(
        id: json['id'] as String? ?? '',
        couponId: json['couponId'] as String? ?? '',
        message: json['message'] as String? ?? '',
        sentAt: DateTime.tryParse(json['sentAt'] as String? ?? '') ?? DateTime.now(),
      );

  final String id;
  final String couponId;
  final String message;
  final DateTime sentAt;
}

class NotificationsApi {
  NotificationsApi(this._dio);

  final Dio _dio;

  Future<List<ExpirationNotification>> fetchFeed() async {
    try {
      final response = await _dio.get<Map<String, dynamic>>('/v1/notifications');
      return (response.data?['items'] as List<dynamic>? ?? const [])
          .map((e) => ExpirationNotification.fromJson(e as Map<String, dynamic>))
          .toList();
    } on DioException catch (error) {
      throw mapDioError(error);
    }
  }

  /// "하루 뒤 다시 알림" — server plans a fresh reminder 24h out.
  Future<void> snooze(String id) async {
    try {
      await _dio.post<void>('/v1/notifications/$id/snooze');
    } on DioException catch (error) {
      throw mapDioError(error);
    }
  }
}

final notificationsApiProvider =
    Provider<NotificationsApi>((ref) => NotificationsApi(ref.watch(dioProvider)));

final notificationFeedProvider = FutureProvider<List<ExpirationNotification>>((ref) {
  return ref.watch(notificationsApiProvider).fetchFeed();
});
