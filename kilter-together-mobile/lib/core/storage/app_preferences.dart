import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../models/session_models.dart';

final Provider<AppPreferences> appPreferencesProvider = Provider<AppPreferences>((Ref ref) {
  return const AppPreferences();
});

class AppPreferences {
  const AppPreferences();

  static const String _activeServerKey = 'active_server';
  static const String _recentServersKey = 'recent_servers';

  Future<SharedPreferences> _prefs() => SharedPreferences.getInstance();

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
    final List<String> raw = prefs.getStringList(_recentServersKey) ?? <String>[];
    return raw.map(normalizeServerUri).toList(growable: false);
  }

  Future<void> rememberServer(Uri server) async {
    final SharedPreferences prefs = await _prefs();
    final List<String> existing = prefs.getStringList(_recentServersKey) ?? <String>[];
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

  Future<void> saveLastDraft(Map<String, dynamic> value) async {
    final SharedPreferences prefs = await _prefs();
    await prefs.setString('last_draft', jsonEncode(value));
  }
}

