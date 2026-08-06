import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'auth_api.dart';
import 'token_store.dart';

@immutable
sealed class AuthState {
  const AuthState();
}

/// Startup: token not yet read from secure storage.
class AuthUnknown extends AuthState {
  const AuthUnknown();
}

class Authenticated extends AuthState {
  const Authenticated(this.email);

  final String? email;
}

class Unauthenticated extends AuthState {
  const Unauthenticated();
}

class AuthController extends Notifier<AuthState> {
  @override
  AuthState build() {
    _restore();
    return const AuthUnknown();
  }

  Future<void> _restore() async {
    final token = await ref.read(tokenStoreProvider).read();
    state = token == null ? const Unauthenticated() : const Authenticated(null);
  }

  Future<void> login(String email, String password) async {
    final result = await ref.read(authApiProvider).login(email, password);
    await ref.read(tokenStoreProvider).write(result.accessToken);
    state = Authenticated(result.email);
  }

  Future<void> register(String email, String password) async {
    final result = await ref.read(authApiProvider).register(email, password);
    await ref.read(tokenStoreProvider).write(result.accessToken);
    state = Authenticated(result.email);
  }

  Future<void> logout() async {
    await ref.read(tokenStoreProvider).clear();
    state = const Unauthenticated();
  }

  /// Called by the network layer when the server answers 401.
  Future<void> sessionExpired() => logout();
}

final authControllerProvider = NotifierProvider<AuthController, AuthState>(AuthController.new);
