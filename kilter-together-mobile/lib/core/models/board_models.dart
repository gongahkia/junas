import 'provider_models.dart';

const int defaultBoardAngle = 40;
const String defaultClimbSort = 'popular';

class BoardOption {
  const BoardOption({
    required this.id,
    required this.name,
    required this.kilterName,
    this.previewImageFilename,
    this.climbCount,
  });

  final int id;
  final String name;
  final String kilterName;
  final String? previewImageFilename;
  final int? climbCount;

  factory BoardOption.fromJson(Map<String, dynamic> json) {
    return BoardOption(
      id: (json['id'] as num?)?.toInt() ?? 0,
      name: json['name'] as String? ?? '',
      kilterName: json['kilter_name'] as String? ?? '',
      previewImageFilename: json['preview_image_filename'] as String?,
      climbCount: (json['climb_count'] as num?)?.toInt(),
    );
  }
}

class GradeInfo {
  const GradeInfo({
    required this.boulder,
    required this.route,
  });

  final String boulder;
  final String route;

  factory GradeInfo.fromJson(Map<String, dynamic> json) {
    return GradeInfo(
      boulder: json['boulder'] as String? ?? '',
      route: json['route'] as String? ?? '',
    );
  }

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'boulder': boulder,
      'route': route,
    };
  }
}

class BoardClimb {
  const BoardClimb({
    required this.uuid,
    required this.climbName,
    required this.frames,
    required this.setterName,
    required this.productSizeId,
    required this.ascends,
    required this.createdAt,
    this.description,
    this.imageFilenames = const <String>[],
    this.highlightedHolds = const <HighlightedHold>[],
    this.grades = const <String, GradeInfo>{},
  });

  final String uuid;
  final String climbName;
  final String frames;
  final String setterName;
  final int productSizeId;
  final int ascends;
  final String createdAt;
  final String? description;
  final List<String> imageFilenames;
  final List<HighlightedHold> highlightedHolds;
  final Map<String, GradeInfo> grades;

  factory BoardClimb.fromJson(Map<String, dynamic> json) {
    final List<dynamic> rawImages = (json['image_filenames'] as List<dynamic>?) ?? <dynamic>[];
    final List<dynamic> rawHolds = (json['highlighted_holds'] as List<dynamic>?) ?? <dynamic>[];
    final Map<String, dynamic> rawGrades = (json['grades'] as Map<String, dynamic>?) ?? <String, dynamic>{};
    return BoardClimb(
      uuid: json['uuid'] as String? ?? '',
      climbName: json['climb_name'] as String? ?? '',
      frames: json['frames'] as String? ?? '',
      setterName: json['setter_name'] as String? ?? 'Unknown setter',
      productSizeId: (json['product_size_id'] as num?)?.toInt() ?? 0,
      ascends: (json['ascends'] as num?)?.toInt() ?? 0,
      createdAt: json['created_at'] as String? ?? '',
      description: json['description'] as String?,
      imageFilenames: rawImages.map((dynamic value) => '$value').toList(growable: false),
      highlightedHolds: rawHolds
          .whereType<Map<String, dynamic>>()
          .map(HighlightedHold.fromJson)
          .toList(growable: false),
      grades: rawGrades.map(
        (String key, dynamic value) => MapEntry(
          key,
          GradeInfo.fromJson((value as Map<dynamic, dynamic>).cast<String, dynamic>()),
        ),
      ),
    );
  }

  String? gradeForAngle(int angle) {
    return grades['$angle']?.boulder;
  }
}

class PaginatedBoardClimbsResponse {
  const PaginatedBoardClimbsResponse({
    required this.climbs,
    required this.hasMore,
    required this.pageSize,
    this.nextCursor,
  });

  final List<BoardClimb> climbs;
  final bool hasMore;
  final int pageSize;
  final String? nextCursor;

  factory PaginatedBoardClimbsResponse.fromJson(Map<String, dynamic> json) {
    final List<dynamic> rawClimbs = (json['climbs'] as List<dynamic>?) ?? <dynamic>[];
    return PaginatedBoardClimbsResponse(
      climbs: rawClimbs
          .whereType<Map<String, dynamic>>()
          .map(BoardClimb.fromJson)
          .toList(growable: false),
      hasMore: json['has_more'] as bool? ?? false,
      pageSize: (json['page_size'] as num?)?.toInt() ?? 10,
      nextCursor: json['next_cursor'] as String?,
    );
  }
}

class SoloSavedClimb {
  const SoloSavedClimb({
    required this.uuid,
    required this.productSizeId,
    required this.climbName,
    required this.setterName,
    required this.boardId,
    required this.boardName,
    required this.angle,
    required this.ascends,
    required this.savedAt,
    this.grade,
    this.imageFilename,
  });

  final String uuid;
  final int productSizeId;
  final String climbName;
  final String setterName;
  final String boardId;
  final String boardName;
  final int angle;
  final int ascends;
  final String savedAt;
  final String? grade;
  final String? imageFilename;

  String get key => '$productSizeId:$uuid';

  factory SoloSavedClimb.fromJson(Map<String, dynamic> json) {
    return SoloSavedClimb(
      uuid: json['uuid'] as String? ?? '',
      productSizeId: (json['product_size_id'] as num?)?.toInt() ?? 0,
      climbName: json['climb_name'] as String? ?? '',
      setterName: json['setter_name'] as String? ?? 'Unknown setter',
      boardId: json['board_id'] as String? ?? '',
      boardName: json['board_name'] as String? ?? '',
      angle: (json['angle'] as num?)?.toInt() ?? defaultBoardAngle,
      ascends: (json['ascends'] as num?)?.toInt() ?? 0,
      savedAt: json['saved_at'] as String? ?? '',
      grade: json['grade'] as String?,
      imageFilename: json['image_filename'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'uuid': uuid,
      'product_size_id': productSizeId,
      'climb_name': climbName,
      'setter_name': setterName,
      'board_id': boardId,
      'board_name': boardName,
      'angle': angle,
      'ascends': ascends,
      'saved_at': savedAt,
      'grade': grade,
      'image_filename': imageFilename,
    };
  }
}

class SoloFilterPreset {
  const SoloFilterPreset({
    required this.id,
    required this.label,
    required this.boardId,
    required this.boardName,
    required this.angle,
    required this.sort,
    required this.savedAt,
    this.q,
    this.setter,
    this.grade,
  });

  final String id;
  final String label;
  final String boardId;
  final String boardName;
  final int angle;
  final String sort;
  final String savedAt;
  final String? q;
  final String? setter;
  final String? grade;

  factory SoloFilterPreset.fromJson(Map<String, dynamic> json) {
    return SoloFilterPreset(
      id: json['id'] as String? ?? '',
      label: json['label'] as String? ?? '',
      boardId: json['board_id'] as String? ?? '',
      boardName: json['board_name'] as String? ?? '',
      angle: (json['angle'] as num?)?.toInt() ?? defaultBoardAngle,
      sort: json['sort'] as String? ?? defaultClimbSort,
      savedAt: json['saved_at'] as String? ?? '',
      q: json['q'] as String?,
      setter: json['setter'] as String?,
      grade: json['grade'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'id': id,
      'label': label,
      'board_id': boardId,
      'board_name': boardName,
      'angle': angle,
      'sort': sort,
      'saved_at': savedAt,
      'q': q,
      'setter': setter,
      'grade': grade,
    };
  }
}
