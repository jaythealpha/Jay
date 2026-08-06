import 'package:amc_mobile/core/auth/auth_api.dart';
import 'package:amc_mobile/core/auth/auth_controller.dart';
import 'package:amc_mobile/core/auth/token_store.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

class MockAuthApi extends Mock implements AuthApi {}

class InMemoryTokenStore implements TokenStore {
  String? token;

  @override
  Future<String?> read() async => token;

  @override
  Future<void> write(String value) async => token = value;

  @override
  Future<void> clear() async => token = null;
}

ProviderContainer containerWith(TokenStore store, AuthApi api) {
  final container = ProviderContainer(
    overrides: [
      tokenStoreProvider.overrideWithValue(store),
      authApiProvider.overrideWithValue(api),
    ],
  );
  addTearDown(container.dispose);
  return container;
}

void main() {
  test('startup without a stored token lands on Unauthenticated', () async {
    final container = containerWith(InMemoryTokenStore(), MockAuthApi());
    expect(container.read(authControllerProvider), isA<AuthUnknown>());
    await Future<void>.delayed(Duration.zero);
    expect(container.read(authControllerProvider), isA<Unauthenticated>());
  });

  test('startup with a stored token restores the session', () async {
    final store = InMemoryTokenStore()..token = 'stored-jwt';
    final container = containerWith(store, MockAuthApi());
    container.read(authControllerProvider); // trigger lazy build
    await Future<void>.delayed(Duration.zero);
    expect(container.read(authControllerProvider), isA<Authenticated>());
  });

  test('login stores the token securely and authenticates', () async {
    final store = InMemoryTokenStore();
    final api = MockAuthApi();
    when(() => api.login('a@b.com', 'password-123')).thenAnswer(
      (_) async => const AuthResult(accessToken: 'fresh-jwt', email: 'a@b.com'),
    );

    final container = containerWith(store, api);
    await container.read(authControllerProvider.notifier).login('a@b.com', 'password-123');

    expect(store.token, 'fresh-jwt');
    final state = container.read(authControllerProvider);
    expect(state, isA<Authenticated>());
    expect((state as Authenticated).email, 'a@b.com');
  });

  test('failed login surfaces the server message and stores nothing', () async {
    final store = InMemoryTokenStore();
    final api = MockAuthApi();
    when(() => api.login(any(), any()))
        .thenThrow(const InvalidCredentialsException('이메일 또는 비밀번호가 올바르지 않습니다.'));

    final container = containerWith(store, api);
    await expectLater(
      container.read(authControllerProvider.notifier).login('a@b.com', 'wrong'),
      throwsA(isA<InvalidCredentialsException>()),
    );
    expect(store.token, isNull);
  });

  test('logout clears the token and de-authenticates', () async {
    final store = InMemoryTokenStore()..token = 'stored-jwt';
    final container = containerWith(store, MockAuthApi());
    await Future<void>.delayed(Duration.zero);

    await container.read(authControllerProvider.notifier).logout();

    expect(store.token, isNull);
    expect(container.read(authControllerProvider), isA<Unauthenticated>());
  });
}
