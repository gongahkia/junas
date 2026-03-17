import 'dart:convert';

import 'board_models.dart';

class CatalogManifest {
  const CatalogManifest({
    required this.revision,
    required this.generatedAt,
    required this.climbCount,
    required this.imageCount,
    required this.estimatedBytes,
    required this.requiresFullResync,
  });

  final String revision;
  final String generatedAt;
  final int climbCount;
  final int imageCount;
  final int estimatedBytes;
  final bool requiresFullResync;

  factory CatalogManifest.fromJson(Map<String, dynamic> json) {
    return CatalogManifest(
      revision: json['revision'] as String? ?? '',
      generatedAt: json['generated_at'] as String? ?? '',
      climbCount: (json['climb_count'] as num?)?.toInt() ?? 0,
      imageCount: (json['image_count'] as num?)?.toInt() ?? 0,
      estimatedBytes: (json['estimated_bytes'] as num?)?.toInt() ?? 0,
      requiresFullResync: json['requires_full_resync'] as bool? ?? false,
    );
  }
}

class CatalogClimb {
  const CatalogClimb({
    required this.uuid,
    required this.climbName,
    required this.frames,
    required this.setterName,
    required this.productSizeId,
    required this.createdAt,
    this.description,
    this.imageFilenames = const <String>[],
    this.highlightedHoldsJson = '[]',
    this.grades = const <String, Map<String, String>>{},
    this.ascends = const <String, int>{},
  });

  final String uuid;
  final String climbName;
  final String frames;
  final String setterName;
  final int productSizeId;
  final String createdAt;
  final String? description;
  final List<String> imageFilenames;
  final String highlightedHoldsJson;
  final Map<String, Map<String, String>> grades;
  final Map<String, int> ascends;

  factory CatalogClimb.fromJson(Map<String, dynamic> json) {
    final List<dynamic> rawImages =
        (json['image_filenames'] as List<dynamic>?) ?? <dynamic>[];
    final Map<String, dynamic> rawGrades =
        (json['grades'] as Map<String, dynamic>?) ?? <String, dynamic>{};
    final Map<String, dynamic> rawAscends =
        (json['ascends'] as Map<String, dynamic>?) ?? <String, dynamic>{};
    return CatalogClimb(
      uuid: json['uuid'] as String? ?? '',
      climbName: json['climb_name'] as String? ?? '',
      frames: json['frames'] as String? ?? '',
      setterName: json['setter_name'] as String? ?? 'Unknown setter',
      productSizeId: (json['product_size_id'] as num?)?.toInt() ?? 0,
      createdAt: json['created_at'] as String? ?? '',
      description: json['description'] as String?,
      imageFilenames:
          rawImages.map((dynamic value) => '$value').toList(growable: false),
      highlightedHoldsJson: _encodeHoldsJson(json['highlighted_holds']),
      grades: rawGrades.map(
        (String key, dynamic value) => MapEntry(
          key,
          ((value as Map<dynamic, dynamic>?) ?? const <dynamic, dynamic>{}).map(
            (dynamic nestedKey, dynamic nestedValue) =>
                MapEntry('$nestedKey', '$nestedValue'),
          ),
        ),
      ),
      ascends: rawAscends.map(
        (String key, dynamic value) =>
            MapEntry(key, (value as num?)?.toInt() ?? 0),
      ),
    );
  }

  static String _encodeHoldsJson(dynamic value) {
    if (value is List<dynamic>) {
      return jsonEncode(value);
    }
    if (value is String) {
      return value;
    }
    return '[]';
  }
}

class CatalogBootstrapResponse {
  const CatalogBootstrapResponse({
    required this.manifest,
    required this.boards,
    required this.climbs,
    required this.hasMore,
    required this.pageSize,
    this.syncToken,
    this.nextCursor,
  });

  final CatalogManifest manifest;
  final List<BoardOption> boards;
  final List<CatalogClimb> climbs;
  final bool hasMore;
  final int pageSize;
  final String? syncToken;
  final String? nextCursor;
}

class CatalogDeltaResponse {
  const CatalogDeltaResponse({
    required this.manifest,
    required this.climbs,
    required this.requiresFullResync,
    this.nextToken,
  });

  final CatalogManifest manifest;
  final List<CatalogClimb> climbs;
  final bool requiresFullResync;
  final String? nextToken;
}

class CatalogStatus {
  const CatalogStatus({
    required this.installed,
    this.sourceServer,
    this.revision,
    this.syncToken,
    this.generatedAt,
    this.climbCount = 0,
    this.imageCount = 0,
    this.estimatedBytes = 0,
    this.storedBytes = 0,
    this.lastFullSyncAt,
    this.lastPollAt,
    this.updateAvailable = false,
    this.requiresFullResync = false,
  });

  final bool installed;
  final String? sourceServer;
  final String? revision;
  final String? syncToken;
  final String? generatedAt;
  final int climbCount;
  final int imageCount;
  final int estimatedBytes;
  final int storedBytes;
  final String? lastFullSyncAt;
  final String? lastPollAt;
  final bool updateAvailable;
  final bool requiresFullResync;

  bool matchesServer(Uri? server) {
    final String active = server?.toString() ?? '';
    return installed && active.isNotEmpty && sourceServer == active;
  }

  CatalogStatus copyWith({
    bool? installed,
    String? sourceServer,
    bool clearSourceServer = false,
    String? revision,
    bool clearRevision = false,
    String? syncToken,
    bool clearSyncToken = false,
    String? generatedAt,
    bool clearGeneratedAt = false,
    int? climbCount,
    int? imageCount,
    int? estimatedBytes,
    int? storedBytes,
    String? lastFullSyncAt,
    bool clearLastFullSyncAt = false,
    String? lastPollAt,
    bool clearLastPollAt = false,
    bool? updateAvailable,
    bool? requiresFullResync,
  }) {
    return CatalogStatus(
      installed: installed ?? this.installed,
      sourceServer:
          clearSourceServer ? null : (sourceServer ?? this.sourceServer),
      revision: clearRevision ? null : (revision ?? this.revision),
      syncToken: clearSyncToken ? null : (syncToken ?? this.syncToken),
      generatedAt: clearGeneratedAt ? null : (generatedAt ?? this.generatedAt),
      climbCount: climbCount ?? this.climbCount,
      imageCount: imageCount ?? this.imageCount,
      estimatedBytes: estimatedBytes ?? this.estimatedBytes,
      storedBytes: storedBytes ?? this.storedBytes,
      lastFullSyncAt:
          clearLastFullSyncAt ? null : (lastFullSyncAt ?? this.lastFullSyncAt),
      lastPollAt: clearLastPollAt ? null : (lastPollAt ?? this.lastPollAt),
      updateAvailable: updateAvailable ?? this.updateAvailable,
      requiresFullResync: requiresFullResync ?? this.requiresFullResync,
    );
  }

  static CatalogStatus empty() => const CatalogStatus(installed: false);
}

class OfflineCatalogQuery {
  const OfflineCatalogQuery({
    required this.boardId,
    required this.angle,
    required this.page,
    this.pageSize = 10,
    this.name,
    this.setter,
    this.grade,
    this.gradeMin,
    this.gradeMax,
    this.sort,
  });

  final String boardId;
  final int angle;
  final int page;
  final int pageSize;
  final String? name;
  final String? setter;
  final String? grade;
  final String? gradeMin;
  final String? gradeMax;
  final String? sort;
}

class CatalogSyncResult {
  const CatalogSyncResult({
    required this.status,
    this.performedSync = false,
  });

  final CatalogStatus status;
  final bool performedSync;
}
