import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../errors/app_exception.dart';

/// API host is injected at build time:
/// flutter run --dart-define=AMC_API_BASE_URL=http://10.0.2.2:3001
const apiBaseUrl = String.fromEnvironment(
  'AMC_API_BASE_URL',
  defaultValue: 'http://localhost:3001',
);

final dioProvider = Provider<Dio>((ref) {
  return Dio(
    BaseOptions(
      baseUrl: apiBaseUrl,
      connectTimeout: const Duration(seconds: 5),
      receiveTimeout: const Duration(seconds: 10),
    ),
  );
});

/// Maps transport-level failures to typed app exceptions so the UI layer
/// never branches on Dio internals.
AppException mapDioError(DioException error) {
  switch (error.type) {
    case DioExceptionType.connectionTimeout:
    case DioExceptionType.receiveTimeout:
    case DioExceptionType.sendTimeout:
    case DioExceptionType.connectionError:
      return NetworkException(debugDetail: error.message);
    case DioExceptionType.badResponse:
    case DioExceptionType.badCertificate:
    case DioExceptionType.cancel:
    case DioExceptionType.unknown:
    default:
      return ServerException(debugDetail: error.message);
  }
}
