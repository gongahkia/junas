import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'secure_store.dart';

final Provider<ProviderSecretRepository> providerSecretRepositoryProvider =
    Provider<ProviderSecretRepository>((Ref ref) {
  return ProviderSecretRepository(
    secureStore: ref.read(secureStoreProvider),
  );
});

class ProviderSecretRepository {
  ProviderSecretRepository({
    required SecureStore secureStore,
  }) : _secureStore = secureStore;

  final SecureStore _secureStore;

  String _key({
    required Uri server,
    required String providerId,
  }) {
    final String raw = '${server.toString()}::$providerId';
    return 'provider_secret_${base64Url.encode(utf8.encode(raw))}';
  }

  Future<void> saveSecret({
    required Uri server,
    required String providerId,
    required Map<String, String> secret,
  }) {
    return _secureStore.write(
      _key(server: server, providerId: providerId),
      jsonEncode(secret),
    );
  }

  Future<Map<String, String>> readSecret({
    required Uri server,
    required String providerId,
  }) async {
    final String? raw =
        await _secureStore.read(_key(server: server, providerId: providerId));
    if (raw == null || raw.isEmpty) {
      return const <String, String>{};
    }

    try {
      final Map<String, dynamic> decoded =
          jsonDecode(raw) as Map<String, dynamic>;
      return decoded
          .map((String key, dynamic value) => MapEntry(key, '$value'));
    } catch (_) {
      return const <String, String>{};
    }
  }

  Future<void> clearSecret({
    required Uri server,
    required String providerId,
  }) {
    return _secureStore.delete(_key(server: server, providerId: providerId));
  }
}
