import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/api_client.dart';

class HealthStatus {
  const HealthStatus({
    required this.overall,
    required this.database,
    required this.redis,
    required this.checkedAt,
  });

  factory HealthStatus.fromJson(Map<String, dynamic> json) {
    final components = json['components'] as Map<String, dynamic>? ?? {};
    return HealthStatus(
      overall: json['status'] as String? ?? 'unknown',
      database: components['database'] as String? ?? 'unknown',
      redis: components['redis'] as String? ?? 'unknown',
      checkedAt: json['checkedAt'] as String? ?? '',
    );
  }

  final String overall;
  final String database;
  final String redis;
  final String checkedAt;
}

class HealthApi {
  HealthApi(this._dio);

  final Dio _dio;

  Future<HealthStatus> fetchHealth() async {
    try {
      final response = await _dio.get<Map<String, dynamic>>('/health');
      return HealthStatus.fromJson(response.data ?? <String, dynamic>{});
    } on DioException catch (error) {
      throw mapDioError(error);
    }
  }
}

final healthApiProvider = Provider<HealthApi>((ref) => HealthApi(ref.watch(dioProvider)));

final healthProvider = FutureProvider<HealthStatus>((ref) {
  return ref.watch(healthApiProvider).fetchHealth();
});
