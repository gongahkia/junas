import 'product_models.dart';
import 'provider_models.dart';
import 'session_models.dart';

class Participant {
  const Participant({
    required this.id,
    required this.displayName,
    required this.role,
    required this.status,
    required this.isOnline,
  });

  final int id;
  final String displayName;
  final String role;
  final String status;
  final bool isOnline;

  factory Participant.fromJson(Map<String, dynamic> json) {
    return Participant(
      id: (json['id'] as num?)?.toInt() ?? 0,
      displayName: json['display_name'] as String? ?? '',
      role: json['role'] as String? ?? 'participant',
      status: json['status'] as String? ?? 'watching',
      isOnline: json['is_online'] as bool? ?? false,
    );
  }
}

class RoomPermissions {
  const RoomPermissions({
    required this.manageSession,
    required this.manageSurface,
    required this.manageQueue,
    required this.manageFinalists,
    required this.editRoomSettings,
    required this.manageParticipants,
    required this.assignCoHosts,
    required this.closeRoom,
  });

  final bool manageSession;
  final bool manageSurface;
  final bool manageQueue;
  final bool manageFinalists;
  final bool editRoomSettings;
  final bool manageParticipants;
  final bool assignCoHosts;
  final bool closeRoom;

  factory RoomPermissions.fromJson(Map<String, dynamic> json) {
    return RoomPermissions(
      manageSession: json['manage_session'] as bool? ?? false,
      manageSurface: json['manage_surface'] as bool? ?? false,
      manageQueue: json['manage_queue'] as bool? ?? false,
      manageFinalists: json['manage_finalists'] as bool? ?? false,
      editRoomSettings: json['edit_room_settings'] as bool? ?? false,
      manageParticipants: json['manage_participants'] as bool? ?? false,
      assignCoHosts: json['assign_co_hosts'] as bool? ?? false,
      closeRoom: json['close_room'] as bool? ?? false,
    );
  }
}

class QueueEntry {
  const QueueEntry({
    required this.id,
    required this.status,
    required this.position,
    required this.addedBy,
    required this.climb,
  });

  final int id;
  final String status;
  final int position;
  final String addedBy;
  final ProviderClimb climb;

  factory QueueEntry.fromJson(Map<String, dynamic> json) {
    return QueueEntry(
      id: (json['id'] as num?)?.toInt() ?? 0,
      status: json['status'] as String? ?? 'queued',
      position: (json['position'] as num?)?.toInt() ?? 0,
      addedBy: json['added_by'] as String? ?? '',
      climb: ProviderClimb.fromJson((json['climb'] as Map<String, dynamic>?) ?? <String, dynamic>{}),
    );
  }
}

class FinalistEntry {
  const FinalistEntry({
    required this.id,
    required this.position,
    required this.addedBy,
    required this.climb,
  });

  final int id;
  final int position;
  final String addedBy;
  final ProviderClimb climb;

  factory FinalistEntry.fromJson(Map<String, dynamic> json) {
    return FinalistEntry(
      id: (json['id'] as num?)?.toInt() ?? 0,
      position: (json['position'] as num?)?.toInt() ?? 0,
      addedBy: json['added_by'] as String? ?? '',
      climb: ProviderClimb.fromJson((json['climb'] as Map<String, dynamic>?) ?? <String, dynamic>{}),
    );
  }
}

class AssistantSuggestion {
  const AssistantSuggestion({
    required this.source,
    required this.readyCount,
    required this.climb,
  });

  final String source;
  final int readyCount;
  final ProviderClimb climb;

  factory AssistantSuggestion.fromJson(Map<String, dynamic> json) {
    return AssistantSuggestion(
      source: json['source'] as String? ?? '',
      readyCount: (json['ready_count'] as num?)?.toInt() ?? 0,
      climb: ProviderClimb.fromJson((json['climb'] as Map<String, dynamic>?) ?? <String, dynamic>{}),
    );
  }
}

class AssistantState {
  const AssistantState({
    required this.mode,
    this.message,
    this.suggestion,
  });

  final String mode;
  final String? message;
  final AssistantSuggestion? suggestion;

  factory AssistantState.fromJson(Map<String, dynamic> json) {
    return AssistantState(
      mode: json['mode'] as String? ?? 'manual',
      message: json['message'] as String?,
      suggestion: json['suggestion'] is Map<String, dynamic>
          ? AssistantSuggestion.fromJson(json['suggestion'] as Map<String, dynamic>)
          : null,
    );
  }
}

class RoomCatalogClimbsResponse {
  const RoomCatalogClimbsResponse({
    required this.climbs,
    required this.hasMore,
    required this.pageSize,
    required this.voteCounts,
    required this.myVotes,
    this.nextCursor,
  });

  final List<ProviderClimb> climbs;
  final bool hasMore;
  final int pageSize;
  final Map<String, int> voteCounts;
  final List<String> myVotes;
  final String? nextCursor;

  factory RoomCatalogClimbsResponse.fromJson(Map<String, dynamic> json) {
    final List<dynamic> rawClimbs = (json['climbs'] as List<dynamic>?) ?? <dynamic>[];
    final Map<String, dynamic> rawVoteCounts = (json['vote_counts'] as Map<String, dynamic>?) ?? <String, dynamic>{};
    final List<dynamic> rawMyVotes = (json['my_votes'] as List<dynamic>?) ?? <dynamic>[];
    return RoomCatalogClimbsResponse(
      climbs: rawClimbs
          .whereType<Map<String, dynamic>>()
          .map(ProviderClimb.fromJson)
          .toList(growable: false),
      hasMore: json['has_more'] as bool? ?? false,
      pageSize: (json['page_size'] as num?)?.toInt() ?? 10,
      voteCounts: rawVoteCounts
          .map((String key, dynamic value) => MapEntry(key, (value as num?)?.toInt() ?? 0)),
      myVotes: rawMyVotes.map((dynamic value) => '$value').toList(growable: false),
      nextCursor: json['next_cursor'] as String?,
    );
  }
}

class RoomCatalogClimbResponse {
  const RoomCatalogClimbResponse({
    required this.climb,
    required this.voteCount,
    required this.myVote,
    required this.isQueued,
  });

  final ProviderClimb climb;
  final int voteCount;
  final bool myVote;
  final bool isQueued;

  factory RoomCatalogClimbResponse.fromJson(Map<String, dynamic> json) {
    return RoomCatalogClimbResponse(
      climb: ProviderClimb.fromJson((json['climb'] as Map<String, dynamic>?) ?? <String, dynamic>{}),
      voteCount: (json['vote_count'] as num?)?.toInt() ?? 0,
      myVote: json['my_vote'] as bool? ?? false,
      isQueued: json['is_queued'] as bool? ?? false,
    );
  }
}

class RoomSnapshot {
  const RoomSnapshot({
    required this.slug,
    required this.status,
    required this.providerId,
    required this.version,
    required this.connection,
    required this.participants,
    required this.finalists,
    required this.queue,
    required this.voteCounts,
    required this.myVotes,
    required this.fistBumpsEnabled,
    required this.canManage,
    required this.permissions,
    required this.assistant,
    this.roomName,
    this.surface,
    this.currentClimb,
    this.displayName,
  });

  final String slug;
  final String? roomName;
  final String status;
  final String providerId;
  final int version;
  final ProviderSurface? surface;
  final ProviderConnectionState connection;
  final ProviderClimb? currentClimb;
  final List<Participant> participants;
  final List<FinalistEntry> finalists;
  final List<QueueEntry> queue;
  final Map<String, int> voteCounts;
  final List<String> myVotes;
  final bool fistBumpsEnabled;
  final bool canManage;
  final RoomPermissions permissions;
  final String? displayName;
  final AssistantState assistant;

  factory RoomSnapshot.fromJson(Map<String, dynamic> json) {
    final List<dynamic> rawParticipants = (json['participants'] as List<dynamic>?) ?? <dynamic>[];
    final List<dynamic> rawFinalists = (json['finalists'] as List<dynamic>?) ?? <dynamic>[];
    final List<dynamic> rawQueue = (json['queue'] as List<dynamic>?) ?? <dynamic>[];
    final Map<String, dynamic> rawVotes = (json['vote_counts'] as Map<String, dynamic>?) ?? <String, dynamic>{};
    final List<dynamic> rawMyVotes = (json['my_votes'] as List<dynamic>?) ?? <dynamic>[];
    return RoomSnapshot(
      slug: json['slug'] as String? ?? '',
      roomName: json['room_name'] as String?,
      status: json['status'] as String? ?? 'open',
      providerId: json['provider_id'] as String? ?? '',
      version: (json['version'] as num?)?.toInt() ?? 0,
      surface: json['surface'] is Map<String, dynamic>
          ? ProviderSurface.fromJson(json['surface'] as Map<String, dynamic>)
          : null,
      connection: ProviderConnectionState.fromJson(
        (json['connection'] as Map<String, dynamic>?) ?? <String, dynamic>{},
      ),
      currentClimb: json['current_climb'] is Map<String, dynamic>
          ? ProviderClimb.fromJson(json['current_climb'] as Map<String, dynamic>)
          : null,
      participants: rawParticipants
          .whereType<Map<String, dynamic>>()
          .map(Participant.fromJson)
          .toList(growable: false),
      finalists: rawFinalists
          .whereType<Map<String, dynamic>>()
          .map(FinalistEntry.fromJson)
          .toList(growable: false),
      queue: rawQueue
          .whereType<Map<String, dynamic>>()
          .map(QueueEntry.fromJson)
          .toList(growable: false),
      voteCounts: rawVotes.map((String key, dynamic value) => MapEntry(key, (value as num?)?.toInt() ?? 0)),
      myVotes: rawMyVotes.map((dynamic value) => '$value').toList(growable: false),
      fistBumpsEnabled: json['fist_bumps_enabled'] as bool? ?? true,
      canManage: json['can_manage'] as bool? ?? false,
      permissions: RoomPermissions.fromJson(
        (json['permissions'] as Map<String, dynamic>?) ?? <String, dynamic>{},
      ),
      displayName: json['display_name'] as String?,
      assistant: AssistantState.fromJson(
        (json['assistant'] as Map<String, dynamic>?) ?? <String, dynamic>{},
      ),
    );
  }
}

class RoomSessionEnvelope {
  const RoomSessionEnvelope({
    required this.room,
    required this.session,
  });

  final RoomSnapshot room;
  final RoomSession session;

  factory RoomSessionEnvelope.fromJson(Map<String, dynamic> json) {
    return RoomSessionEnvelope(
      room: RoomSnapshot.fromJson((json['room'] as Map<String, dynamic>?) ?? <String, dynamic>{}),
      session: RoomSession.fromJson((json['session'] as Map<String, dynamic>?) ?? <String, dynamic>{}),
    );
  }
}
