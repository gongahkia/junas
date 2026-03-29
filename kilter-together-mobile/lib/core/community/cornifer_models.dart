class CorniferSession {
  const CorniferSession({
    required this.token,
    required this.username,
  });

  final String token;
  final String username;

  factory CorniferSession.fromJson(Map<String, dynamic> json) {
    return CorniferSession(
      token: json['token'] as String? ?? '',
      username: json['username'] as String? ?? '',
    );
  }

  Map<String, dynamic> toJson() => <String, dynamic>{
        'token': token,
        'username': username,
      };
}

class CorniferBoardHold {
  const CorniferBoardHold({
    required this.id,
    required this.position,
    required this.centroidX,
    required this.centroidY,
    this.contour = const <List<num>>[],
  });

  final String id;
  final int position;
  final double centroidX;
  final double centroidY;
  final List<List<num>> contour;

  factory CorniferBoardHold.fromJson(Map<String, dynamic> json) {
    final List<dynamic> rawContour =
        (json['contour'] as List<dynamic>?) ?? <dynamic>[];
    return CorniferBoardHold(
      id: json['id'] as String? ?? '',
      position: (json['position'] as num?)?.toInt() ?? 0,
      centroidX: (json['centroid_x'] as num?)?.toDouble() ?? 0,
      centroidY: (json['centroid_y'] as num?)?.toDouble() ?? 0,
      contour: rawContour
          .whereType<List<dynamic>>()
          .map(
            (List<dynamic> value) =>
                value.map((dynamic item) => item as num).toList(growable: false),
          )
          .toList(growable: false),
    );
  }

  Map<String, dynamic> toJson() => <String, dynamic>{
        'id': id,
        'position': position,
        'centroid_x': centroidX,
        'centroid_y': centroidY,
        'contour': contour,
      };
}

class CorniferBoardDraft {
  const CorniferBoardDraft({
    required this.id,
    required this.name,
    required this.location,
    required this.description,
    required this.imageUrl,
    required this.draft,
    this.holds = const <CorniferBoardHold>[],
  });

  final String id;
  final String name;
  final String location;
  final String description;
  final String imageUrl;
  final bool draft;
  final List<CorniferBoardHold> holds;

  factory CorniferBoardDraft.fromJson(Map<String, dynamic> json) {
    final Map<String, dynamic> board =
        (json['board'] as Map<String, dynamic>?) ?? json;
    final List<dynamic> rawHolds =
        (board['holds'] as List<dynamic>?) ?? <dynamic>[];
    return CorniferBoardDraft(
      id: board['id'] as String? ?? '',
      name: board['name'] as String? ?? '',
      location: board['location'] as String? ?? '',
      description: board['description'] as String? ?? '',
      imageUrl: board['image_url'] as String? ?? '',
      draft: board['draft'] as bool? ?? true,
      holds: rawHolds
          .whereType<Map<String, dynamic>>()
          .map(CorniferBoardHold.fromJson)
          .toList(growable: false),
    );
  }
}

class CorniferClimbSelection {
  const CorniferClimbSelection({
    required this.boardHoldId,
    required this.role,
  });

  final String boardHoldId;
  final String role;

  Map<String, dynamic> toJson() => <String, dynamic>{
        'board_hold_id': boardHoldId,
        'role': role,
      };
}
