import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../models/app_prefs_models.dart';
import '../models/session_models.dart';

final Provider<AppPreferences> appPreferencesProvider =
    Provider<AppPreferences>((Ref ref) {
  return const AppPreferences();
});

class AppPreferences {
  const AppPreferences();

  static const String _activeServerKey = 'active_server';
  static const String _recentServersKey = 'recent_servers';
  static const String _appPrefsKey = 'kilter_together_mobile:app_prefs:v1';

  Future<SharedPreferences> _prefs() => SharedPreferences.getInstance();

  Future<AppPrefs> loadAppPrefs() async {
    final SharedPreferences prefs = await _prefs();
    final String? raw = prefs.getString(_appPrefsKey);
    if (raw == null || raw.isEmpty) {
      return AppPrefs.defaults();
    }

    try {
      return AppPrefs.fromJson(jsonDecode(raw) as Map<String, dynamic>);
    } catch (_) {
      return AppPrefs.defaults();
    }
  }

  Future<void> saveAppPrefs(AppPrefs appPrefs) async {
    final SharedPreferences prefs = await _prefs();
    await prefs.setString(_appPrefsKey, jsonEncode(appPrefs.toJson()));
  }

  Future<AppPrefs> updateAppPrefs(
      AppPrefs Function(AppPrefs current) updater) async {
    final AppPrefs current = await loadAppPrefs();
    final AppPrefs next = updater(current);
    await saveAppPrefs(next);
    return next;
  }

  Future<Uri?> loadActiveServer() async {
    final SharedPreferences prefs = await _prefs();
    final String? raw = prefs.getString(_activeServerKey);
    if (raw == null || raw.isEmpty) {
      return null;
    }
    return normalizeServerUri(raw);
  }

  Future<void> saveActiveServer(Uri server) async {
    final SharedPreferences prefs = await _prefs();
    await prefs.setString(_activeServerKey, server.toString());
  }

  Future<List<Uri>> loadRecentServers() async {
    final SharedPreferences prefs = await _prefs();
    final List<String> raw =
        prefs.getStringList(_recentServersKey) ?? <String>[];
    return raw.map(normalizeServerUri).toList(growable: false);
  }

  Future<void> rememberServer(Uri server) async {
    final SharedPreferences prefs = await _prefs();
    final List<String> existing =
        prefs.getStringList(_recentServersKey) ?? <String>[];
    final List<String> next = <String>[server.toString()];
    for (final String candidate in existing) {
      if (candidate != server.toString()) {
        next.add(candidate);
      }
      if (next.length == 6) {
        break;
      }
    }
    await prefs.setStringList(_recentServersKey, next);
    await saveActiveServer(server);
  }
}
