import 'dart:convert';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:sqflite/sqflite.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/product_models.dart';

final Provider<LocalRecapRepository> localRecapRepositoryProvider =
    Provider<LocalRecapRepository>((Ref ref) => LocalRecapRepository());

class LocalRecapRepository {
  Database? _db;

  Future<Database> _open() async {
    if (_db != null) return _db!;
    final dir = await getApplicationDocumentsDirectory();
    _db = await openDatabase(
      p.join(dir.path, 'local_recaps.db'),
      version: 1,
      onCreate: (Database db, int version) async {
        await db.execute('''
          CREATE TABLE recaps (
            share_id TEXT PRIMARY KEY,
            slug TEXT NOT NULL,
            room_name TEXT,
            provider_id TEXT NOT NULL,
            data TEXT NOT NULL,
            created_at TEXT NOT NULL
          )
        ''');
      },
    );
    return _db!;
  }

  Future<void> saveRecap({
    required String shareId,
    required String slug,
    required String? roomName,
    required String providerId,
    required RoomRecap recap,
  }) async {
    final Database db = await _open();
    await db.insert(
      'recaps',
      <String, dynamic>{
        'share_id': shareId,
        'slug': slug,
        'room_name': roomName,
        'provider_id': providerId,
        'data': jsonEncode(recap.toJson()),
        'created_at': DateTime.now().toUtc().toIso8601String(),
      },
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  Future<RoomRecap?> loadRecap(String shareId) async {
    final Database db = await _open();
    final List<Map<String, dynamic>> rows = await db.query(
      'recaps',
      where: 'share_id = ?',
      whereArgs: <Object?>[shareId],
      limit: 1,
    );
    if (rows.isEmpty) return null;
    try {
      return RoomRecap.fromJson(
        jsonDecode(rows.first['data'] as String) as Map<String, dynamic>,
      );
    } catch (_) {
      return null;
    }
  }

  Future<List<({String shareId, String slug, String? roomName, String providerId, String createdAt})>> listRecaps({
    int limit = 20,
  }) async {
    final Database db = await _open();
    final List<Map<String, dynamic>> rows = await db.query(
      'recaps',
      orderBy: 'created_at DESC',
      limit: limit,
    );
    return rows.map((Map<String, dynamic> row) => (
      shareId: row['share_id'] as String,
      slug: row['slug'] as String,
      roomName: row['room_name'] as String?,
      providerId: row['provider_id'] as String,
      createdAt: row['created_at'] as String,
    )).toList(growable: false);
  }

  Future<void> deleteRecap(String shareId) async {
    final Database db = await _open();
    await db.delete('recaps', where: 'share_id = ?', whereArgs: <Object?>[shareId]);
  }
}
