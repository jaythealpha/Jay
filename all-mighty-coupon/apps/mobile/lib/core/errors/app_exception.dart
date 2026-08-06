/// User-facing failures carry a message safe to render as-is; internal
/// details stay in [debugDetail] and never reach the UI (spec §18).
abstract class AppException implements Exception {
  const AppException(this.userMessage, {this.debugDetail});

  final String userMessage;
  final String? debugDetail;

  @override
  String toString() => '$runtimeType($debugDetail)';
}

class NetworkException extends AppException {
  const NetworkException({String? debugDetail})
      : super('네트워크 연결을 확인해 주세요.', debugDetail: debugDetail);
}

class ServerException extends AppException {
  const ServerException({String? debugDetail})
      : super('일시적인 오류가 발생했어요. 잠시 후 다시 시도해 주세요.', debugDetail: debugDetail);
}

class CacheMissException extends AppException {
  const CacheMissException()
      : super('저장된 쿠폰이 아직 없어요. 네트워크 연결 후 다시 시도해 주세요.');
}

class SessionExpiredException extends AppException {
  const SessionExpiredException() : super('로그인이 만료되었어요. 다시 로그인해 주세요.');
}
