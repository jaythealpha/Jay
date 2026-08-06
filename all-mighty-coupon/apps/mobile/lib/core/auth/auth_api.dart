import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../errors/app_exception.dart';
import '../network/api_client.dart';

class AuthResult {
  const AuthResult({required this.accessToken, required this.email});

  final String accessToken;
  final String email;
}

class InvalidCredentialsException extends AppException {
  const InvalidCredentialsException(super.message);
}

class AuthApi {
  AuthApi(this._dio);

  final Dio _dio;

  Future<AuthResult> register(String email, String password) =>
      _post('/v1/auth/register', email, password);

  Future<AuthResult> login(String email, String password) =>
      _post('/v1/auth/login', email, password);

  Future<AuthResult> _post(String path, String email, String password) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        path,
        data: {'email': email, 'password': password},
      );
      final token = response.data?['accessToken'] as String?;
      final user = response.data?['user'] as Map<String, dynamic>?;
      if (token == null) {
        throw const ServerException(debugDetail: 'missing accessToken');
      }
      return AuthResult(accessToken: token, email: user?['email'] as String? ?? email);
    } on DioException catch (error) {
      // 400/401/409 carry a user-safe message in the common error envelope.
      final data = error.response?.data;
      final serverMessage = data is Map<String, dynamic>
          ? ((data['error'] as Map<String, dynamic>?)?['message'] as String?)
          : null;
      if (serverMessage != null) {
        throw InvalidCredentialsException(serverMessage);
      }
      throw mapDioError(error);
    }
  }
}

final authApiProvider = Provider<AuthApi>((ref) => AuthApi(ref.watch(dioProvider)));
