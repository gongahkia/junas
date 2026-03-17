import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path/path.dart' as path;
import 'package:sqflite/sqflite.dart';

import '../models/board_models.dart';
import '../models/catalog_models.dart';
import '../models/provider_models.dart';
import '../network/api_client.dart';
import 'catalog_storage_platform.dart';

final Provider<OfflineKilterCatalogRepository>
    offlineKilterCatalogRepositoryProvider =
    Provider<OfflineKilterCatalogRepository>((Ref ref) {
  return OfflineKilterCatalogRepository(
    apiClient: ref.read(apiClientProvider),
    storagePlatform: ref.read(catalogStoragePlatformProvider),
  );
});

class OfflineKilterCatalogRepository {
  OfflineKilterCatalogRepository({
    required ApiClient apiClient,
    required CatalogStoragePlatform storagePlatform,
  })  : _apiClient = apiClient,
        _storagePlatform = storagePlatform;

  final ApiClient _apiClient;
  final CatalogStoragePlatform _storagePlatform;

  static const List<int> _angles = <int>[
    5,
    10,
    15,
    20,
    25,
    30,
    35,
    40,
    45,
    50,
    55,
    60,
    65,
    70,
  ];
  static const int _bootstrapPageSize = 200;
  static const String _rootFolderName = 'kilter_catalog';
  static const String _schemaFolderName = 'v1';
  static const String _liveDbName = 'catalog.db';
  static const String _liveImagesFolderName = 'images';
  static const String _tempDbName = 'catalog.bootstrap.db';
  static const String _tempImagesFolderName = 'images.bootstrap';
  static const String _bootstrapStateName = 'bootstrap_state.json';

  Future<CatalogManifest> getManifest(Uri server) {
    return _apiClient.getKilterCatalogManifest(server: server);
  }

  Future<CatalogStatus> getStatus() async {
    final File liveDb = await _liveDbFile();
    if (!await liveDb.exists()) {
      return CatalogStatus.empty();
    }

    try {
      final Database db = await _openDatabase(liveDb.path, readOnly: true);
      try {
        final Map<String, String> meta = await _loadMeta(db);
        return _statusFromMeta(
          meta,
          storedBytes: await _calculateStoredBytes(),
        );
      } finally {
        await db.close();
      }
    } catch (error, stackTrace) {
      await _rethrowCatalogAccessError(error, stackTrace);
    }
  }

  Future<List<BoardOption>> getBoards() async {
    final File liveDb = await _liveDbFile();
    if (!await liveDb.exists()) {
      return const <BoardOption>[];
    }

    try {
      final Database db = await _openDatabase(liveDb.path, readOnly: true);
      try {
        final List<Map<String, Object?>> rows = await db.query(
          'boards',
          orderBy: 'kilter_name ASC, name ASC, id ASC',
        );
        return rows
            .map(
              (Map<String, Object?> row) => BoardOption(
                id: (row['id'] as num?)?.toInt() ?? 0,
                name: row['name'] as String? ?? '',
                kilterName: row['kilter_name'] as String? ?? '',
                previewImageFilename: row['preview_image_filename'] as String?,
                climbCount: (row['climb_count'] as num?)?.toInt(),
              ),
            )
            .toList(growable: false);
      } finally {
        await db.close();
      }
    } catch (error, stackTrace) {
      await _rethrowCatalogAccessError(error, stackTrace);
    }
  }

  Future<PaginatedBoardClimbsResponse> queryClimbs(
    OfflineCatalogQuery query,
  ) async {
    final File liveDb = await _liveDbFile();
    if (!await liveDb.exists()) {
      return const PaginatedBoardClimbsResponse(
        climbs: <BoardClimb>[],
        hasMore: false,
        pageSize: 10,
      );
    }

    final String ascendsColumn = _ascendsColumnFor(query.angle);
    final String boulderColumn = _gradeBoulderColumnFor(query.angle);
    final String routeColumn = _gradeRouteColumnFor(query.angle);
    final int page = query.page <= 0 ? 1 : query.page;
    final int limit = query.pageSize <= 0 ? 10 : query.pageSize;
    final int offset = (page - 1) * limit;

    final List<Object?> whereArgs = <Object?>[int.tryParse(query.boardId) ?? 0];
    final List<String> whereParts = <String>['product_size_id = ?'];

    final String name = (query.name ?? '').trim().toLowerCase();
    if (name.isNotEmpty) {
      whereParts.add('LOWER(climb_name) LIKE ?');
      whereArgs.add('%$name%');
    }

    final String setter = (query.setter ?? '').trim().toLowerCase();
    if (setter.isNotEmpty) {
      whereParts.add('LOWER(setter_name) LIKE ?');
      whereArgs.add('%$setter%');
    }

    final String grade = (query.grade ?? '').trim().toLowerCase();
    if (grade.isNotEmpty) {
      whereParts.add(
          '(LOWER(COALESCE($boulderColumn, \'\')) LIKE ? OR LOWER(COALESCE($routeColumn, \'\')) LIKE ?)');
      whereArgs
        ..add('%$grade%')
        ..add('%$grade%');
    }

    final String gradeMin = (query.gradeMin ?? '').trim().toLowerCase();
    if (gradeMin.isNotEmpty) {
      whereParts.add(
          '(LOWER(COALESCE($boulderColumn, \'\')) >= ? OR LOWER(COALESCE($routeColumn, \'\')) >= ?)');
      whereArgs
        ..add(gradeMin)
        ..add(gradeMin);
    }

    final String gradeMax = (query.gradeMax ?? '').trim().toLowerCase();
    if (gradeMax.isNotEmpty) {
      whereParts.add(
          '(LOWER(COALESCE($boulderColumn, \'\')) <= ? OR LOWER(COALESCE($routeColumn, \'\')) <= ?)');
      whereArgs
        ..add(gradeMax)
        ..add(gradeMax);
    }

    final String orderBy = (query.sort ?? defaultClimbSort) == 'newest'
        ? 'created_at DESC, uuid DESC'
        : 'COALESCE($ascendsColumn, 0) DESC, created_at DESC, uuid DESC';

    try {
      final Database db = await _openDatabase(liveDb.path, readOnly: true);
      try {
        final List<Map<String, Object?>> rows = await db.query(
          'climbs',
          where: whereParts.join(' AND '),
          whereArgs: whereArgs,
          orderBy: orderBy,
          limit: limit + 1,
          offset: offset,
        );

        final bool hasMore = rows.length > limit;
        final List<Map<String, Object?>> visibleRows =
            hasMore ? rows.sublist(0, limit) : rows;
        return PaginatedBoardClimbsResponse(
          climbs: visibleRows
              .map((Map<String, Object?> row) =>
                  _boardClimbFromRow(row, query.angle))
              .toList(growable: false),
          hasMore: hasMore,
          pageSize: limit,
        );
      } finally {
        await db.close();
      }
    } catch (error, stackTrace) {
      await _rethrowCatalogAccessError(error, stackTrace);
    }
  }

  Future<void> downloadCatalog(Uri server) async {
    final CatalogManifest manifest = await getManifest(server);
    final Directory root = await _rootDirectory();
    await root.create(recursive: true);
    await _ensureSufficientFreeSpace(root, manifest.estimatedBytes);
    final File stateFile = await _bootstrapStateFile();
    final File tempDbFile = await _tempDbFile();
    final Directory tempImagesDir = await _tempImagesDirectory();
    final _BootstrapState? existingState = await _readBootstrapState();
    final bool resume = existingState != null &&
        existingState.server == server.toString() &&
        existingState.revision == manifest.revision &&
        await tempDbFile.exists();

    if (!resume) {
      await _deleteIfExists(tempDbFile);
      await _deleteDirectoryIfExists(tempImagesDir);
      await tempImagesDir.create(recursive: true);
      await stateFile.writeAsString(
        jsonEncode(
          _BootstrapState(
            server: server.toString(),
            revision: manifest.revision,
            cursor: null,
          ).toJson(),
        ),
      );
    } else {
      await tempImagesDir.create(recursive: true);
    }

    final Database db = await _openDatabase(tempDbFile.path);
    try {
      String? cursor = existingState?.cursor;
      if (!resume) {
        await _replaceBoards(db, const <BoardOption>[]);
      }

      while (true) {
        final CatalogBootstrapResponse response =
            await _apiClient.getKilterCatalogBootstrap(
          server: server,
          cursor: cursor,
          pageSize: _bootstrapPageSize,
        );
        await db.transaction((Transaction txn) async {
          if ((cursor ?? '').isEmpty) {
            await _replaceBoards(txn, response.boards);
          }
          await _upsertClimbs(txn, response.climbs);
          await _writeMeta(
            txn,
            <String, String>{
              'source_server': server.toString(),
              'revision': response.manifest.revision,
              'generated_at': response.manifest.generatedAt,
              'climb_count': '${response.manifest.climbCount}',
              'image_count': '${response.manifest.imageCount}',
              'estimated_bytes': '${response.manifest.estimatedBytes}',
              'sync_token': response.syncToken ?? '',
              'last_full_sync_at': DateTime.now().toUtc().toIso8601String(),
              'last_poll_at': DateTime.now().toUtc().toIso8601String(),
              'update_available': '0',
              'requires_full_resync': '0',
            },
          );
        });
        await _ensureImages(
          server,
          response.boards
              .map((BoardOption board) => board.previewImageFilename)
              .whereType<String>()
              .followedBy(
                response.climbs
                    .expand((CatalogClimb climb) => climb.imageFilenames),
              ),
          tempImagesDir,
        );
        cursor = response.nextCursor;
        await stateFile.writeAsString(
          jsonEncode(
            _BootstrapState(
              server: server.toString(),
              revision: manifest.revision,
              cursor: cursor,
            ).toJson(),
          ),
        );
        if (!response.hasMore) {
          break;
        }
      }
    } finally {
      await db.close();
    }

    await _promoteTempCatalog();
    await _storagePlatform.excludeFromBackup((await _schemaDirectory()).path);
    await _deleteIfExists(stateFile);
  }

  Future<CatalogSyncResult> syncCatalog(
    Uri server, {
    bool allowFullResync = true,
  }) async {
    try {
      CatalogStatus status = await getStatus();
      if (!status.installed || !status.matchesServer(server)) {
        if (allowFullResync) {
          await downloadCatalog(server);
          return CatalogSyncResult(
              status: await getStatus(), performedSync: true);
        }
        return CatalogSyncResult(status: status);
      }

      final CatalogManifest manifest =
          await _apiClient.getKilterCatalogManifest(server: server);
      final String now = DateTime.now().toUtc().toIso8601String();
      if (manifest.revision == status.revision) {
        await _updateLiveMeta(<String, String>{
          'last_poll_at': now,
          'update_available': '0',
          'requires_full_resync': '0',
        });
        return CatalogSyncResult(
          status: (await getStatus()).copyWith(
            updateAvailable: false,
            requiresFullResync: false,
          ),
        );
      }

      if (manifest.requiresFullResync && !allowFullResync) {
        await _updatePendingResync(manifest, now);
        return CatalogSyncResult(status: await getStatus());
      }
      if (manifest.requiresFullResync && allowFullResync) {
        await downloadCatalog(server);
        return CatalogSyncResult(
            status: await getStatus(), performedSync: true);
      }

      final CatalogDeltaResponse delta = await _apiClient.getKilterCatalogDelta(
        server: server,
        afterToken: status.syncToken,
      );
      if (delta.requiresFullResync && !allowFullResync) {
        await _updatePendingResync(delta.manifest, now);
        return CatalogSyncResult(status: await getStatus());
      }
      if (delta.requiresFullResync && allowFullResync) {
        await downloadCatalog(server);
        return CatalogSyncResult(
            status: await getStatus(), performedSync: true);
      }

      final Database db = await _openDatabase((await _liveDbFile()).path);
      try {
        await db.transaction((Transaction txn) async {
          await _upsertClimbs(txn, delta.climbs);
          await _writeMeta(
            txn,
            <String, String>{
              'source_server': server.toString(),
              'revision': delta.manifest.revision,
              'generated_at': delta.manifest.generatedAt,
              'climb_count': '${delta.manifest.climbCount}',
              'image_count': '${delta.manifest.imageCount}',
              'estimated_bytes': '${delta.manifest.estimatedBytes}',
              'sync_token': delta.nextToken ?? (status.syncToken ?? ''),
              'last_full_sync_at': now,
              'last_poll_at': now,
              'update_available': '0',
              'requires_full_resync': '0',
            },
          );
        });
      } finally {
        await db.close();
      }

      if (delta.climbs.isNotEmpty) {
        await _ensureImages(
          server,
          delta.climbs.expand((CatalogClimb climb) => climb.imageFilenames),
          await _liveImagesDirectory(),
        );
      }

      return CatalogSyncResult(
        status: await getStatus(),
        performedSync: delta.climbs.isNotEmpty,
      );
    } catch (error, stackTrace) {
      if (_isCatalogAccessError(error)) {
        await _purgeCatalogFiles();
        if (allowFullResync) {
          await downloadCatalog(server);
          return CatalogSyncResult(
            status: await getStatus(),
            performedSync: true,
          );
        }
        Error.throwWithStackTrace(
          const CatalogCorruptionException(),
          stackTrace,
        );
      }
      rethrow;
    }
  }

  Future<void> deleteCatalog() async {
    await _purgeCatalogFiles(ignoreErrors: false);
  }

  Future<String?> resolveImagePath(String filename) async {
    final File imageFile = File(
      path.join((await _liveImagesDirectory()).path,
          _normalizeImageFilename(filename)),
    );
    if (!await imageFile.exists()) {
      return null;
    }
    return imageFile.path;
  }

  Future<void> _ensureSufficientFreeSpace(
    Directory root,
    int requiredBytes,
  ) async {
    if (requiredBytes <= 0) {
      return;
    }
    final int? availableBytes =
        await _storagePlatform.availableBytesAt(root.path);
    if (availableBytes == null) {
      return;
    }
    const int safetyMarginBytes = 25 * 1024 * 1024;
    if (availableBytes < requiredBytes + safetyMarginBytes) {
      throw InsufficientCatalogStorageException(
        requiredBytes: requiredBytes,
        availableBytes: availableBytes,
      );
    }
  }

  Future<void> _promoteTempCatalog() async {
    final File liveDb = await _liveDbFile();
    final Directory liveImagesDir = await _liveImagesDirectory();
    final File tempDb = await _tempDbFile();
    final Directory tempImagesDir = await _tempImagesDirectory();

    await _deleteIfExists(liveDb);
    await _deleteDirectoryIfExists(liveImagesDir);
    if (await tempDb.exists()) {
      await tempDb.rename(liveDb.path);
    }
    if (await tempImagesDir.exists()) {
      await tempImagesDir.rename(liveImagesDir.path);
    }
  }

  Future<void> _updatePendingResync(
      CatalogManifest manifest, String now) async {
    await _updateLiveMeta(<String, String>{
      'revision': manifest.revision,
      'generated_at': manifest.generatedAt,
      'climb_count': '${manifest.climbCount}',
      'image_count': '${manifest.imageCount}',
      'estimated_bytes': '${manifest.estimatedBytes}',
      'last_poll_at': now,
      'update_available': '1',
      'requires_full_resync': '1',
    });
  }

  Future<void> _updateLiveMeta(Map<String, String> meta) async {
    final File liveDb = await _liveDbFile();
    if (!await liveDb.exists()) {
      return;
    }
    final Database db = await _openDatabase(liveDb.path);
    try {
      await _writeMeta(db, meta);
    } finally {
      await db.close();
    }
  }

  Future<void> _replaceBoards(
    DatabaseExecutor db,
    List<BoardOption> boards,
  ) async {
    await db.delete('boards');
    if (boards.isEmpty) {
      return;
    }
    final Batch batch = db.batch();
    for (final BoardOption board in boards) {
      batch.insert(
        'boards',
        <String, Object?>{
          'id': board.id,
          'name': board.name,
          'kilter_name': board.kilterName,
          'preview_image_filename':
              _normalizeImageFilename(board.previewImageFilename),
          'climb_count': board.climbCount ?? 0,
        },
        conflictAlgorithm: ConflictAlgorithm.replace,
      );
    }
    await batch.commit(noResult: true);
  }

  Future<void> _upsertClimbs(
    DatabaseExecutor db,
    List<CatalogClimb> climbs,
  ) async {
    if (climbs.isEmpty) {
      return;
    }
    final Batch batch = db.batch();
    for (final CatalogClimb climb in climbs) {
      batch.insert(
        'climbs',
        _catalogClimbRow(climb),
        conflictAlgorithm: ConflictAlgorithm.replace,
      );
    }
    await batch.commit(noResult: true);
  }

  Future<void> _writeMeta(
    DatabaseExecutor db,
    Map<String, String> values,
  ) async {
    final Batch batch = db.batch();
    values.forEach((String key, String value) {
      batch.insert(
        'catalog_meta',
        <String, Object?>{'key': key, 'value': value},
        conflictAlgorithm: ConflictAlgorithm.replace,
      );
    });
    await batch.commit(noResult: true);
  }

  Future<Map<String, String>> _loadMeta(Database db) async {
    final List<Map<String, Object?>> rows = await db.query('catalog_meta');
    return <String, String>{
      for (final Map<String, Object?> row in rows)
        '${row['key']}': '${row['value'] ?? ''}',
    };
  }

  CatalogStatus _statusFromMeta(
    Map<String, String> meta, {
    required int storedBytes,
  }) {
    if (meta.isEmpty) {
      return CatalogStatus.empty();
    }
    return CatalogStatus(
      installed: true,
      sourceServer: _emptyToNull(meta['source_server']),
      revision: _emptyToNull(meta['revision']),
      syncToken: _emptyToNull(meta['sync_token']),
      generatedAt: _emptyToNull(meta['generated_at']),
      climbCount: int.tryParse(meta['climb_count'] ?? '') ?? 0,
      imageCount: int.tryParse(meta['image_count'] ?? '') ?? 0,
      estimatedBytes: int.tryParse(meta['estimated_bytes'] ?? '') ?? 0,
      storedBytes: storedBytes,
      lastFullSyncAt: _emptyToNull(meta['last_full_sync_at']),
      lastPollAt: _emptyToNull(meta['last_poll_at']),
      updateAvailable: meta['update_available'] == '1',
      requiresFullResync: meta['requires_full_resync'] == '1',
    );
  }

  Map<String, Object?> _catalogClimbRow(CatalogClimb climb) {
    final Map<String, Object?> row = <String, Object?>{
      'product_size_id': climb.productSizeId,
      'uuid': climb.uuid,
      'climb_name': climb.climbName,
      'setter_name': climb.setterName,
      'description': climb.description,
      'frames': climb.frames,
      'created_at': climb.createdAt,
      'image_filenames_json': jsonEncode(
        climb.imageFilenames
            .map(_normalizeImageFilename)
            .toList(growable: false),
      ),
      'highlighted_holds_json': climb.highlightedHoldsJson,
    };

    for (final int angle in _angles) {
      final String key = '$angle';
      final Map<String, String> grade =
          climb.grades[key] ?? const <String, String>{};
      row[_ascendsColumnFor(angle)] = climb.ascends[key] ?? 0;
      row[_gradeBoulderColumnFor(angle)] = grade['boulder'];
      row[_gradeRouteColumnFor(angle)] = grade['route'];
    }
    return row;
  }

  BoardClimb _boardClimbFromRow(Map<String, Object?> row, int angle) {
    final String climbUuid = row['uuid'] as String? ?? '';
    final List<dynamic> rawImages = _decodeJsonList(
      row['image_filenames_json'] as String?,
      fieldName: 'image_filenames_json',
      climbUuid: climbUuid,
    );
    final List<dynamic> rawHolds = _decodeJsonList(
      row['highlighted_holds_json'] as String?,
      fieldName: 'highlighted_holds_json',
      climbUuid: climbUuid,
    );
    final Map<String, GradeInfo> grades = <String, GradeInfo>{};
    for (final int candidate in _angles) {
      final String? boulder = row[_gradeBoulderColumnFor(candidate)] as String?;
      final String? route = row[_gradeRouteColumnFor(candidate)] as String?;
      if ((boulder ?? '').isEmpty && (route ?? '').isEmpty) {
        continue;
      }
      grades['$candidate'] = GradeInfo(
        boulder: boulder ?? '',
        route: route ?? '',
      );
    }

    return BoardClimb(
      uuid: row['uuid'] as String? ?? '',
      climbName: row['climb_name'] as String? ?? '',
      frames: row['frames'] as String? ?? '',
      setterName: row['setter_name'] as String? ?? 'Unknown setter',
      productSizeId: (row['product_size_id'] as num?)?.toInt() ?? 0,
      ascends: (row[_ascendsColumnFor(angle)] as num?)?.toInt() ?? 0,
      createdAt: row['created_at'] as String? ?? '',
      description: row['description'] as String?,
      imageFilenames:
          rawImages.map((dynamic item) => '$item').toList(growable: false),
      highlightedHolds: rawHolds
          .whereType<Map<dynamic, dynamic>>()
          .map(
            (Map<dynamic, dynamic> item) => item.map(
              (dynamic key, dynamic value) => MapEntry('$key', value),
            ),
          )
          .map(HighlightedHold.fromJson)
          .toList(growable: false),
      grades: grades,
    );
  }

  Future<void> _ensureImages(
    Uri server,
    Iterable<String> filenames,
    Directory targetDirectory,
  ) async {
    await targetDirectory.create(recursive: true);
    final Set<String> seen = <String>{};
    for (final String filename in filenames) {
      final String normalized = _normalizeImageFilename(filename);
      if (normalized.isEmpty || !seen.add(normalized)) {
        continue;
      }
      final File file = File(path.join(targetDirectory.path, normalized));
      if (await file.exists()) {
        continue;
      }
      final List<int> bytes = await _apiClient.downloadImageBytes(
        server: server,
        filename: normalized,
      );
      await file.writeAsBytes(bytes, flush: true);
    }
  }

  Future<Database> _openDatabase(
    String dbPath, {
    bool readOnly = false,
  }) {
    if (readOnly) {
      return openDatabase(dbPath, readOnly: true);
    }

    return openDatabase(
      dbPath,
      version: 1,
      onCreate: (Database db, int version) async {
        await _createSchema(db);
      },
      onOpen: (Database db) async {
        await _createSchema(db);
      },
    );
  }

  List<dynamic> _decodeJsonList(
    String? raw, {
    required String fieldName,
    required String climbUuid,
  }) {
    final dynamic decoded = jsonDecode(raw ?? '[]');
    if (decoded is! List<dynamic>) {
      throw FormatException(
        'Expected $fieldName to contain a JSON list for climb $climbUuid.',
      );
    }
    return decoded;
  }

  Future<void> _createSchema(Database db) async {
    final StringBuffer climbColumns = StringBuffer()
      ..write('product_size_id INTEGER NOT NULL,')
      ..write('uuid TEXT NOT NULL,')
      ..write('climb_name TEXT NOT NULL,')
      ..write('setter_name TEXT NOT NULL,')
      ..write('description TEXT,')
      ..write('frames TEXT NOT NULL,')
      ..write('created_at TEXT NOT NULL,')
      ..write('image_filenames_json TEXT NOT NULL,')
      ..write('highlighted_holds_json TEXT NOT NULL,');
    for (final int angle in _angles) {
      climbColumns
        ..write('${_ascendsColumnFor(angle)} INTEGER NOT NULL DEFAULT 0,')
        ..write('${_gradeBoulderColumnFor(angle)} TEXT,')
        ..write('${_gradeRouteColumnFor(angle)} TEXT,');
    }
    climbColumns.write('PRIMARY KEY (product_size_id, uuid)');

    await db.execute('''
      CREATE TABLE IF NOT EXISTS boards (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        kilter_name TEXT NOT NULL,
        preview_image_filename TEXT,
        climb_count INTEGER NOT NULL DEFAULT 0
      )
    ''');
    await db.execute('''
      CREATE TABLE IF NOT EXISTS climbs (
        ${climbColumns.toString()}
      )
    ''');
    await db.execute('''
      CREATE TABLE IF NOT EXISTS catalog_meta (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
      )
    ''');
    await db.execute('''
      CREATE INDEX IF NOT EXISTS idx_climbs_board_created
      ON climbs(product_size_id, created_at DESC, uuid DESC)
    ''');
  }

  Future<int> _calculateStoredBytes() async {
    int total = 0;
    for (final FileSystemEntity entity in <FileSystemEntity>[
      await _liveDbFile(),
      await _liveImagesDirectory(),
    ]) {
      if (!await entity.exists()) {
        continue;
      }
      if (entity is File) {
        total += await entity.length();
        continue;
      }
      if (entity is Directory) {
        await for (final FileSystemEntity child
            in entity.list(recursive: true, followLinks: false)) {
          if (child is File) {
            total += await child.length();
          }
        }
      }
    }
    return total;
  }

  Future<_BootstrapState?> _readBootstrapState() async {
    final File stateFile = await _bootstrapStateFile();
    if (!await stateFile.exists()) {
      return null;
    }
    try {
      final Map<String, dynamic> decoded =
          jsonDecode(await stateFile.readAsString()) as Map<String, dynamic>;
      return _BootstrapState.fromJson(decoded);
    } catch (_) {
      return null;
    }
  }

  Future<Never> _rethrowCatalogAccessError(
    Object error,
    StackTrace stackTrace,
  ) async {
    if (error is CatalogCorruptionException) {
      Error.throwWithStackTrace(error, stackTrace);
    }
    if (_isCatalogAccessError(error)) {
      await _purgeCatalogFiles();
      Error.throwWithStackTrace(
        const CatalogCorruptionException(),
        stackTrace,
      );
    }
    Error.throwWithStackTrace(error, stackTrace);
  }

  bool _isCatalogAccessError(Object error) {
    return error is DatabaseException ||
        error is FormatException ||
        error is TypeError ||
        error is FileSystemException;
  }

  Future<void> _purgeCatalogFiles({
    bool ignoreErrors = true,
  }) async {
    try {
      await _deleteIfExists(await _liveDbFile());
      await _deleteDirectoryIfExists(await _liveImagesDirectory());
      await _deleteIfExists(await _tempDbFile());
      await _deleteDirectoryIfExists(await _tempImagesDirectory());
      await _deleteIfExists(await _bootstrapStateFile());
    } catch (_) {
      if (!ignoreErrors) {
        rethrow;
      }
    }
  }

  Future<Directory> _rootDirectory() async {
    final Directory appSupport = await _storagePlatform.appSupportDirectory();
    return Directory(
      path.join(appSupport.path, _rootFolderName, _schemaFolderName),
    );
  }

  Future<Directory> _schemaDirectory() => _rootDirectory();

  Future<File> _liveDbFile() async {
    return File(path.join((await _rootDirectory()).path, _liveDbName));
  }

  Future<File> _tempDbFile() async {
    return File(path.join((await _rootDirectory()).path, _tempDbName));
  }

  Future<Directory> _liveImagesDirectory() async {
    return Directory(
      path.join((await _rootDirectory()).path, _liveImagesFolderName),
    );
  }

  Future<Directory> _tempImagesDirectory() async {
    return Directory(
      path.join((await _rootDirectory()).path, _tempImagesFolderName),
    );
  }

  Future<File> _bootstrapStateFile() async {
    return File(path.join((await _rootDirectory()).path, _bootstrapStateName));
  }

  Future<void> _deleteIfExists(File file) async {
    if (await file.exists()) {
      await file.delete();
    }
  }

  Future<void> _deleteDirectoryIfExists(Directory directory) async {
    if (await directory.exists()) {
      await directory.delete(recursive: true);
    }
  }

  String _ascendsColumnFor(int angle) => 'ascends_$angle';

  String _gradeBoulderColumnFor(int angle) => 'grade_boulder_$angle';

  String _gradeRouteColumnFor(int angle) => 'grade_route_$angle';

  String _normalizeImageFilename(String? filename) {
    if (filename == null) {
      return '';
    }
    return path.basename(filename.trim());
  }

  String? _emptyToNull(String? value) {
    final String normalized = (value ?? '').trim();
    return normalized.isEmpty ? null : normalized;
  }
}

class InsufficientCatalogStorageException implements Exception {
  const InsufficientCatalogStorageException({
    required this.requiredBytes,
    required this.availableBytes,
  });

  final int requiredBytes;
  final int availableBytes;

  @override
  String toString() {
    return 'Not enough free device storage for the offline Kilter catalog. '
        'Need about ${_formatCatalogBytes(requiredBytes)} and only '
        '${_formatCatalogBytes(availableBytes)} is available.';
  }
}

class CatalogCorruptionException implements Exception {
  const CatalogCorruptionException();

  static const String message =
      'Offline Kilter catalog on this device was corrupted and has been cleared. Download it again from Settings.';

  @override
  String toString() => message;
}

String _formatCatalogBytes(int bytes) {
  if (bytes <= 0) {
    return '0 B';
  }
  const List<String> units = <String>['B', 'KB', 'MB', 'GB'];
  double value = bytes.toDouble();
  int unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  final String formatted = value >= 10 || unitIndex == 0
      ? value.toStringAsFixed(0)
      : value.toStringAsFixed(1);
  return '$formatted ${units[unitIndex]}';
}

class _BootstrapState {
  const _BootstrapState({
    required this.server,
    required this.revision,
    required this.cursor,
  });

  final String server;
  final String revision;
  final String? cursor;

  factory _BootstrapState.fromJson(Map<String, dynamic> json) {
    return _BootstrapState(
      server: json['server'] as String? ?? '',
      revision: json['revision'] as String? ?? '',
      cursor: json['cursor'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'server': server,
      'revision': revision,
      'cursor': cursor,
    };
  }
}
