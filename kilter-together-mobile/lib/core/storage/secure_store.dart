import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

final Provider<SecureStore> secureStoreProvider =
    Provider<SecureStore>((Ref ref) {
  return const SecureStore();
});

class SecureStore {
  const SecureStore() : _storage = const FlutterSecureStorage();

  final FlutterSecureStorage _storage;

  Future<void> write(String key, String value) {
    return _storage.write(key: key, value: value);
  }

  Future<String?> read(String key) {
    return _storage.read(key: key);
  }

  Future<void> delete(String key) {
    return _storage.delete(key: key);
  }
}
