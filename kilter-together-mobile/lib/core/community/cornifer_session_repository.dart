import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../storage/secure_store.dart';
import 'cornifer_models.dart';

final Provider<CorniferSessionRepository> corniferSessionRepositoryProvider =
    Provider<CorniferSessionRepository>((Ref ref) {
  return CorniferSessionRepository(
    secureStore: ref.read(secureStoreProvider),
  );
});

class CorniferSessionRepository {
  CorniferSessionRepository({
    required SecureStore secureStore,
  }) : _secureStore = secureStore;

  static const String _legacySessionKey = 'cornifer_session_v1';
  final SecureStore _secureStore;

  Future<CorniferSession?> load(Uri server) async {
    final String? raw = await _secureStore.read(_sessionKey(server));
    if (raw == null || raw.isEmpty) {
      return null;
    }
    try {
      final Map<String, dynamic> decoded =
          jsonDecode(raw) as Map<String, dynamic>;
      final CorniferSession session = CorniferSession.fromJson(decoded);
      if (session.token.isEmpty || session.username.isEmpty) {
        return null;
      }
      return session;
    } catch (_) {
      return null;
    }
  }

  Future<void> save(Uri server, CorniferSession session) async {
    await _secureStore.write(_sessionKey(server), jsonEncode(session.toJson()));
    await _secureStore.delete(_legacySessionKey);
  }

  Future<void> clear(Uri server) async {
    await _secureStore.delete(_sessionKey(server));
    await _secureStore.delete(_legacySessionKey);
  }

  String _sessionKey(Uri server) =>
      'cornifer_session_v2:${_serverScope(server)}';

  String _serverScope(Uri server) {
    final String normalizedPath = server.path == '/' || server.path.isEmpty
        ? ''
        : server.path.endsWith('/')
            ? server.path.substring(0, server.path.length - 1)
            : server.path;
    return Uri(
      scheme: server.scheme.toLowerCase(),
      host: server.host.toLowerCase(),
      port: server.hasPort ? server.port : null,
      path: normalizedPath,
    ).toString();
  }
}
