import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/app_prefs_models.dart';
import 'app_preferences.dart';

final Provider<SessionRepository> sessionRepositoryProvider =
    Provider<SessionRepository>((Ref ref) {
  return SessionRepository(appPreferences: ref.read(appPreferencesProvider));
});

class SessionRepository {
  SessionRepository({required AppPreferences appPreferences})
      : _appPreferences = appPreferences;
  final AppPreferences _appPreferences;
  Future<Uri?> loadActiveServer() => _appPreferences.loadActiveServer();
  Future<List<Uri>> loadRecentServers() => _appPreferences.loadRecentServers();
  Future<void> rememberServer(Uri server) =>
      _appPreferences.rememberServer(server);
  Future<AppPrefs> loadAppPrefs() => _appPreferences.loadAppPrefs();
  Future<void> saveAppPrefs(AppPrefs prefs) =>
      _appPreferences.saveAppPrefs(prefs);
}
