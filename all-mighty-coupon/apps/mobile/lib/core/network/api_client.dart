import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../auth/auth_controller.dart';
import '../auth/token_store.dart';
import '../errors/app_exception.dart';

/// API host is injected at build time:
/// flutter run --dart-define=AMC_API_BASE_URL=http://10.0.2.2:3001
const apiBaseUrl = String.fromEnvironment(
  'AMC_API_BASE_URL',
  defaultValue: 'http://localhost:3001',
);

bool _isAuthPath(String path) => path.startsWith('/v1/auth/');

final dioProvider = Provider<Dio>((ref) {
  final dio = Dio(
    BaseOptions(
      baseUrl: apiBaseUrl,
      connectTimeout: const Duration(seconds: 5),
      receiveTimeout: const Duration(seconds: 10),
    ),
  );
  dio.interceptors.add(
    InterceptorsWrapper(
      onRequest: (options, handler) async {
        if (!_isAuthPath(options.path)) {
          final token = await ref.read(tokenStoreProvider).read();
          if (token != null) {
            options.headers['Authorization'] = 'Bearer $token';
          }
        }
        handler.next(options);
      },
      onError: (error, handler) async {
        // Expired/invalid session: drop the token so the router sends the
        // user back to login instead of looping on 401s.
        if (error.response?.statusCode == 401 && !_isAuthPath(error.requestOptions.path)) {
          await ref.read(authControllerProvider.notifier).sessionExpired();
        }
        handler.next(error);
      },
    ),
  );
  return dio;
});

/// Maps transport-level failures to typed app exceptions so the UI layer
/// never branches on Dio internals.
AppException mapDioError(DioException error) {
  if (error.response?.statusCode == 401) {
    return const SessionExpiredException();
  }
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
