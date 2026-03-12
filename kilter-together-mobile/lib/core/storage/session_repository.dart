import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/app_prefs_models.dart';
import '../models/session_models.dart';
import 'app_preferences.dart';
import 'secure_store.dart';

final Provider<SessionRepository> sessionRepositoryProvider = Provider<SessionRepository>((Ref ref) {
  return SessionRepository(
    appPreferences: ref.read(appPreferencesProvider),
    secureStore: ref.read(secureStoreProvider),
  );
});

class SessionRepository {
  SessionRepository({
    required AppPreferences appPreferences,
    required SecureStore secureStore,
  })  : _appPreferences = appPreferences,
        _secureStore = secureStore;

  final AppPreferences _appPreferences;
  final SecureStore _secureStore;

  String _sessionKey(Uri server, String slug) {
    final String raw = '${server.toString()}::$slug';
    return 'room_session_${base64Url.encode(utf8.encode(raw))}';
  }

  Future<void> saveSession({
    required Uri server,
    required String slug,
    required RoomSession session,
  }) async {
    await _secureStore.write(_sessionKey(server, slug), session.encode());
    await _appPreferences.rememberServer(server);
  }

  Future<RoomSession?> readSession({
    required Uri server,
    required String slug,
  }) async {
    final String? raw = await _secureStore.read(_sessionKey(server, slug));
    if (raw == null || raw.isEmpty) {
      return null;
    }
    return RoomSession.decode(raw);
  }

  Future<void> clearSession({
    required Uri server,
    required String slug,
  }) {
    return _secureStore.delete(_sessionKey(server, slug));
  }

  Future<Uri?> loadActiveServer() {
    return _appPreferences.loadActiveServer();
  }

  Future<List<Uri>> loadRecentServers() {
    return _appPreferences.loadRecentServers();
  }

  Future<void> rememberServer(Uri server) {
    return _appPreferences.rememberServer(server);
  }

  Future<AppPrefs> loadAppPrefs() {
    return _appPreferences.loadAppPrefs();
  }

  Future<void> saveAppPrefs(AppPrefs prefs) {
    return _appPreferences.saveAppPrefs(prefs);
  }
}
