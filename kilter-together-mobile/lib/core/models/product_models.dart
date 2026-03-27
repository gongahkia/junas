import 'provider_models.dart';

class SessionSummaryClimb {
  const SessionSummaryClimb({
    required this.climb,
    this.position,
    this.status,
    this.addedBy,
    this.voteCount,
  });

  final ProviderClimb climb;
  final int? position;
  final String? status;
  final String? addedBy;
  final int? voteCount;

  factory SessionSummaryClimb.fromJson(Map<String, dynamic> json) {
    return SessionSummaryClimb(
      climb: ProviderClimb.fromJson(
          (json['climb'] as Map<String, dynamic>?) ?? <String, dynamic>{}),
      position: (json['position'] as num?)?.toInt(),
      status: json['status'] as String?,
      addedBy: json['added_by'] as String?,
      voteCount: (json['vote_count'] as num?)?.toInt(),
    );
  }

  Map<String, dynamic> toJson() => <String, dynamic>{
        'climb': climb.toJson(),
        if (position != null) 'position': position,
        if (status != null) 'status': status,
        if (addedBy != null) 'added_by': addedBy,
        if (voteCount != null) 'vote_count': voteCount,
      };
}

class SessionSummary {
  const SessionSummary({
    required this.roomSlug,
    required this.providerId,
    required this.participantCount,
    required this.closedAt,
    required this.topVoted,
    required this.finalQueue,
    required this.finalists,
    this.roomName,
    this.surfaceName,
    this.surfaceKind,
    this.recapShareId,
  });

  final String roomSlug;
  final String? roomName;
  final String providerId;
  final String? surfaceName;
  final String? surfaceKind;
  final int participantCount;
  final String? recapShareId;
  final DateTime closedAt;
  final List<SessionSummaryClimb> topVoted;
  final List<SessionSummaryClimb> finalQueue;
  final List<SessionSummaryClimb> finalists;

  factory SessionSummary.fromJson(Map<String, dynamic> json) {
    final List<dynamic> rawTopVoted =
        (json['top_voted'] as List<dynamic>?) ?? <dynamic>[];
    final List<dynamic> rawFinalQueue =
        (json['final_queue'] as List<dynamic>?) ?? <dynamic>[];
    final List<dynamic> rawFinalists =
        (json['finalists'] as List<dynamic>?) ?? <dynamic>[];
    return SessionSummary(
      roomSlug: json['room_slug'] as String? ?? '',
      roomName: json['room_name'] as String?,
      providerId: json['provider_id'] as String? ?? '',
      surfaceName: json['surface_name'] as String?,
      surfaceKind: json['surface_kind'] as String?,
      participantCount: (json['participant_count'] as num?)?.toInt() ?? 0,
      recapShareId: json['recap_share_id'] as String?,
      closedAt: DateTime.tryParse(json['closed_at'] as String? ?? '') ??
          DateTime.now().toUtc(),
      topVoted: rawTopVoted
          .whereType<Map<String, dynamic>>()
          .map(SessionSummaryClimb.fromJson)
          .toList(growable: false),
      finalQueue: rawFinalQueue
          .whereType<Map<String, dynamic>>()
          .map(SessionSummaryClimb.fromJson)
          .toList(growable: false),
      finalists: rawFinalists
          .whereType<Map<String, dynamic>>()
          .map(SessionSummaryClimb.fromJson)
          .toList(growable: false),
    );
  }
}

class ProviderCatalogClimbsResponse {
  const ProviderCatalogClimbsResponse({
    required this.climbs,
    required this.hasMore,
    required this.pageSize,
    this.nextCursor,
  });

  final List<ProviderClimb> climbs;
  final bool hasMore;
  final int pageSize;
  final String? nextCursor;

  factory ProviderCatalogClimbsResponse.fromJson(Map<String, dynamic> json) {
    final List<dynamic> rawClimbs =
        (json['climbs'] as List<dynamic>?) ?? <dynamic>[];
    return ProviderCatalogClimbsResponse(
      climbs: rawClimbs
          .whereType<Map<String, dynamic>>()
          .map(ProviderClimb.fromJson)
          .toList(growable: false),
      hasMore: json['has_more'] as bool? ?? false,
      pageSize: (json['page_size'] as num?)?.toInt() ?? 10,
      nextCursor: json['next_cursor'] as String?,
    );
  }
}

class ProviderCatalogClimbResponse {
  const ProviderCatalogClimbResponse({
    required this.climb,
  });

  final ProviderClimb climb;

  factory ProviderCatalogClimbResponse.fromJson(Map<String, dynamic> json) {
    return ProviderCatalogClimbResponse(
      climb: ProviderClimb.fromJson(
          (json['climb'] as Map<String, dynamic>?) ?? <String, dynamic>{}),
    );
  }
}

class RecapStat {
  const RecapStat({
    required this.label,
    required this.value,
  });

  final String label;
  final String value;

  factory RecapStat.fromJson(Map<String, dynamic> json) {
    return RecapStat(
      label: json['label'] as String? ?? '',
      value: json['value'] as String? ?? '',
    );
  }

  Map<String, dynamic> toJson() =>
      <String, dynamic>{'label': label, 'value': value};
}

class RecapSlide {
  const RecapSlide({
    required this.id,
    required this.eyebrow,
    required this.title,
    required this.description,
    this.stats = const <RecapStat>[],
    this.featuredClimb,
    this.climbs = const <SessionSummaryClimb>[],
    this.participants = const <String>[],
  });

  final String id;
  final String eyebrow;
  final String title;
  final String description;
  final List<RecapStat> stats;
  final ProviderClimb? featuredClimb;
  final List<SessionSummaryClimb> climbs;
  final List<String> participants;

  factory RecapSlide.fromJson(Map<String, dynamic> json) {
    final List<dynamic> rawStats =
        (json['stats'] as List<dynamic>?) ?? <dynamic>[];
    final List<dynamic> rawClimbs =
        (json['climbs'] as List<dynamic>?) ?? <dynamic>[];
    final List<dynamic> rawParticipants =
        (json['participants'] as List<dynamic>?) ?? <dynamic>[];
    return RecapSlide(
      id: json['id'] as String? ?? '',
      eyebrow: json['eyebrow'] as String? ?? '',
      title: json['title'] as String? ?? '',
      description: json['description'] as String? ?? '',
      stats: rawStats
          .whereType<Map<String, dynamic>>()
          .map(RecapStat.fromJson)
          .toList(growable: false),
      featuredClimb: json['featured_climb'] is Map<String, dynamic>
          ? ProviderClimb.fromJson(
              json['featured_climb'] as Map<String, dynamic>)
          : null,
      climbs: rawClimbs
          .whereType<Map<String, dynamic>>()
          .map(SessionSummaryClimb.fromJson)
          .toList(growable: false),
      participants: rawParticipants
          .map((dynamic value) => '$value')
          .toList(growable: false),
    );
  }

  Map<String, dynamic> toJson() => <String, dynamic>{
        'id': id,
        'eyebrow': eyebrow,
        'title': title,
        'description': description,
        'stats': stats.map((RecapStat s) => s.toJson()).toList(growable: false),
        if (featuredClimb != null) 'featured_climb': featuredClimb!.toJson(),
        'climbs': climbs
            .map((SessionSummaryClimb c) => c.toJson())
            .toList(growable: false),
        'participants': participants,
      };
}

class RoomSeed {
  const RoomSeed({
    required this.providerId,
    required this.surface,
    required this.climbs,
  });

  final String providerId;
  final ProviderSurface surface;
  final List<ProviderClimb> climbs;

  factory RoomSeed.fromJson(Map<String, dynamic> json) {
    final List<dynamic> rawClimbs =
        (json['climbs'] as List<dynamic>?) ?? <dynamic>[];
    return RoomSeed(
      providerId: json['provider_id'] as String? ?? '',
      surface: ProviderSurface.fromJson(
          (json['surface'] as Map<String, dynamic>?) ?? <String, dynamic>{}),
      climbs: rawClimbs
          .whereType<Map<String, dynamic>>()
          .map(ProviderClimb.fromJson)
          .toList(growable: false),
    );
  }

  Map<String, dynamic> toJson() => <String, dynamic>{
        'provider_id': providerId,
        'surface': surface.toJson(),
        'climbs':
            climbs.map((ProviderClimb c) => c.toJson()).toList(growable: false),
      };
}

class RoomRecap {
  const RoomRecap({
    required this.shareId,
    required this.roomSlug,
    required this.providerId,
    required this.closedAt,
    required this.slides,
    this.roomName,
    this.surfaceName,
    this.rematchSeed,
  });

  final String shareId;
  final String roomSlug;
  final String? roomName;
  final String providerId;
  final String? surfaceName;
  final DateTime closedAt;
  final List<RecapSlide> slides;
  final RoomSeed? rematchSeed;

  factory RoomRecap.fromJson(Map<String, dynamic> json) {
    final List<dynamic> rawSlides =
        (json['slides'] as List<dynamic>?) ?? <dynamic>[];
    return RoomRecap(
      shareId: json['share_id'] as String? ?? '',
      roomSlug: json['room_slug'] as String? ?? '',
      roomName: json['room_name'] as String?,
      providerId: json['provider_id'] as String? ?? '',
      surfaceName: json['surface_name'] as String?,
      closedAt: DateTime.tryParse(json['closed_at'] as String? ?? '') ??
          DateTime.now().toUtc(),
      slides: rawSlides
          .whereType<Map<String, dynamic>>()
          .map(RecapSlide.fromJson)
          .toList(growable: false),
      rematchSeed: json['rematch_seed'] is Map<String, dynamic>
          ? RoomSeed.fromJson(json['rematch_seed'] as Map<String, dynamic>)
          : null,
    );
  }

  Map<String, dynamic> toJson() => <String, dynamic>{
        'share_id': shareId,
        'room_slug': roomSlug,
        if (roomName != null) 'room_name': roomName,
        'provider_id': providerId,
        if (surfaceName != null) 'surface_name': surfaceName,
        'closed_at': closedAt.toUtc().toIso8601String(),
        'slides':
            slides.map((RecapSlide s) => s.toJson()).toList(growable: false),
        if (rematchSeed != null) 'rematch_seed': rematchSeed!.toJson(),
      };
}

class SoloPlanSnapshot {
  const SoloPlanSnapshot({
    required this.shareId,
    required this.providerId,
    required this.title,
    required this.surface,
    required this.climbs,
    required this.createdAt,
    this.notes,
    this.filters = const <String, String>{},
    this.openPath,
    this.createdBy,
  });

  final String shareId;
  final String providerId;
  final String title;
  final String? notes;
  final ProviderSurface surface;
  final Map<String, String> filters;
  final List<ProviderClimb> climbs;
  final String? openPath;
  final String? createdBy;
  final DateTime createdAt;

  factory SoloPlanSnapshot.fromJson(Map<String, dynamic> json) {
    final List<dynamic> rawClimbs =
        (json['climbs'] as List<dynamic>?) ?? <dynamic>[];
    final Map<String, dynamic> rawFilters =
        (json['filters'] as Map<String, dynamic>?) ?? <String, dynamic>{};
    return SoloPlanSnapshot(
      shareId: json['share_id'] as String? ?? '',
      providerId: json['provider_id'] as String? ?? '',
      title: json['title'] as String? ?? '',
      notes: json['notes'] as String?,
      surface: ProviderSurface.fromJson(
          (json['surface'] as Map<String, dynamic>?) ?? <String, dynamic>{}),
      filters: rawFilters
          .map((String key, dynamic value) => MapEntry(key, '$value')),
      climbs: rawClimbs
          .whereType<Map<String, dynamic>>()
          .map(ProviderClimb.fromJson)
          .toList(growable: false),
      openPath: json['open_path'] as String?,
      createdBy: json['created_by'] as String?,
      createdAt: DateTime.tryParse(json['created_at'] as String? ?? '') ??
          DateTime.now().toUtc(),
    );
  }
}
