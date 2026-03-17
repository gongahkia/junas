import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path/path.dart' as path;
import 'package:sqflite/sqflite.dart';

import '../models/climb_log_models.dart';

final Provider<ClimbLogRepository> climbLogRepositoryProvider =
    Provider<ClimbLogRepository>((Ref ref) {
  return ClimbLogRepository();
});

class ClimbLogRepository {
  static const String _dbName = 'climb_log.db';

  Future<Database> _openDatabase() async {
    final String dbPath = path.join(await getDatabasesPath(), _dbName);
    return openDatabase(
      dbPath,
      version: 1,
      onCreate: (Database db, int version) async {
        await db.execute('''
          CREATE TABLE IF NOT EXISTS climb_log_entries (
            id TEXT PRIMARY KEY,
            climb_id TEXT NOT NULL,
            provider_id TEXT NOT NULL,
            surface_context_json TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            status TEXT NOT NULL,
            note TEXT,
            climb_name TEXT
          )
        ''');
        await db.execute('''
          CREATE INDEX IF NOT EXISTS idx_climb_log_climb_id
          ON climb_log_entries(climb_id)
        ''');
        await db.execute('''
          CREATE INDEX IF NOT EXISTS idx_climb_log_timestamp
          ON climb_log_entries(timestamp DESC)
        ''');
      },
    );
  }

  Future<void> upsert(ClimbLogEntry entry) async {
    final Database db = await _openDatabase();
    try {
      await db.insert(
        'climb_log_entries',
        <String, Object?>{
          'id': entry.id,
          'climb_id': entry.climbId,
          'provider_id': entry.providerId,
          'surface_context_json': jsonEncode(entry.surfaceContext),
          'timestamp': entry.timestamp,
          'status': entry.status,
          'note': entry.note,
          'climb_name': entry.climbName,
        },
        conflictAlgorithm: ConflictAlgorithm.replace,
      );
    } finally {
      await db.close();
    }
  }

  Future<List<ClimbLogEntry>> listAll() async {
    final Database db = await _openDatabase();
    try {
      final List<Map<String, Object?>> rows = await db.query(
        'climb_log_entries',
        orderBy: 'timestamp DESC',
      );
      return rows.map(_entryFromRow).toList(growable: false);
    } finally {
      await db.close();
    }
  }

  Future<List<ClimbLogEntry>> getForClimb(String climbId) async {
    final Database db = await _openDatabase();
    try {
      final List<Map<String, Object?>> rows = await db.query(
        'climb_log_entries',
        where: 'climb_id = ?',
        whereArgs: <Object?>[climbId],
        orderBy: 'timestamp DESC',
      );
      return rows.map(_entryFromRow).toList(growable: false);
    } finally {
      await db.close();
    }
  }

  Future<String> exportJson() async {
    final List<ClimbLogEntry> entries = await listAll();
    return jsonEncode(
      entries
          .map((ClimbLogEntry entry) => entry.toJson())
          .toList(growable: false),
    );
  }

  Future<String> exportCsv() async {
    final List<ClimbLogEntry> entries = await listAll();
    final StringBuffer buffer = StringBuffer()
      ..writeln(
          'id,climb_id,provider_id,timestamp,status,climb_name,note,surface_context');
    for (final ClimbLogEntry entry in entries) {
      buffer.writeln(
        '${_csvEscape(entry.id)},'
        '${_csvEscape(entry.climbId)},'
        '${_csvEscape(entry.providerId)},'
        '${_csvEscape(entry.timestamp)},'
        '${_csvEscape(entry.status)},'
        '${_csvEscape(entry.climbName ?? '')},'
        '${_csvEscape(entry.note ?? '')},'
        '${_csvEscape(jsonEncode(entry.surfaceContext))}',
      );
    }
    return buffer.toString();
  }

  ClimbLogEntry _entryFromRow(Map<String, Object?> row) {
    final String rawContext = row['surface_context_json'] as String? ?? '{}';
    Map<String, String> surfaceContext;
    try {
      final dynamic decoded = jsonDecode(rawContext);
      if (decoded is Map<String, dynamic>) {
        surfaceContext = decoded
            .map((String key, dynamic value) => MapEntry(key, '$value'));
      } else {
        surfaceContext = const <String, String>{};
      }
    } catch (_) {
      surfaceContext = const <String, String>{};
    }
    return ClimbLogEntry(
      id: row['id'] as String? ?? '',
      climbId: row['climb_id'] as String? ?? '',
      providerId: row['provider_id'] as String? ?? '',
      surfaceContext: surfaceContext,
      timestamp: row['timestamp'] as String? ?? '',
      status: row['status'] as String? ?? 'seen',
      note: row['note'] as String?,
      climbName: row['climb_name'] as String?,
    );
  }

  String _csvEscape(String value) {
    if (value.contains(',') || value.contains('"') || value.contains('\n')) {
      return '"${value.replaceAll('"', '""')}"';
    }
    return value;
  }
}
