import 'session_models.dart';

class ProviderConnectionState {
  const ProviderConnectionState({
    required this.connected,
    this.providerId,
  });

  final bool connected;
  final String? providerId;

  factory ProviderConnectionState.fromJson(Map<String, dynamic> json) {
    return ProviderConnectionState(
      connected: json['connected'] as bool? ?? false,
      providerId: json['provider_id'] as String?,
    );
  }
}

class ProviderSurface {
  const ProviderSurface({
    required this.id,
    required this.kind,
    required this.name,
    this.description,
    this.parentId,
    this.meta = const <String, String>{},
  });

  final String id;
  final String kind;
  final String name;
  final String? description;
  final String? parentId;
  final Map<String, String> meta;

  factory ProviderSurface.fromJson(Map<String, dynamic> json) {
    final Map<String, dynamic> rawMeta = (json['meta'] as Map<String, dynamic>?) ?? <String, dynamic>{};
    return ProviderSurface(
      id: json['id'] as String? ?? '',
      kind: json['kind'] as String? ?? '',
      name: json['name'] as String? ?? '',
      description: json['description'] as String?,
      parentId: json['parent_id'] as String?,
      meta: rawMeta.map((String key, dynamic value) => MapEntry(key, '$value')),
    );
  }

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'id': id,
      'kind': kind,
      'name': name,
      'description': description,
      'parent_id': parentId,
      'meta': meta,
    };
  }
}

class ProviderClimb {
  const ProviderClimb({
    required this.id,
    required this.name,
    this.setterName,
    this.primaryGrade,
    this.secondaryGrade,
    this.description,
  });

  final String id;
  final String name;
  final String? setterName;
  final String? primaryGrade;
  final String? secondaryGrade;
  final String? description;

  factory ProviderClimb.fromJson(Map<String, dynamic> json) {
    return ProviderClimb(
      id: json['id'] as String? ?? '',
      name: json['name'] as String? ?? '',
      setterName: json['setter_name'] as String?,
      primaryGrade: json['primary_grade'] as String?,
      secondaryGrade: json['secondary_grade'] as String?,
      description: json['description'] as String?,
    );
  }
}

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
      id: json['id'] as int? ?? 0,
      displayName: json['display_name'] as String? ?? '',
      role: json['role'] as String? ?? 'participant',
      status: json['status'] as String? ?? 'watching',
      isOnline: json['is_online'] as bool? ?? false,
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
      id: json['id'] as int? ?? 0,
      status: json['status'] as String? ?? 'queued',
      position: json['position'] as int? ?? 0,
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
      id: json['id'] as int? ?? 0,
      position: json['position'] as int? ?? 0,
      addedBy: json['added_by'] as String? ?? '',
      climb: ProviderClimb.fromJson((json['climb'] as Map<String, dynamic>?) ?? <String, dynamic>{}),
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

class AssistantState {
  const AssistantState({
    required this.mode,
    this.message,
  });

  final String mode;
  final String? message;

  factory AssistantState.fromJson(Map<String, dynamic> json) {
    return AssistantState(
      mode: json['mode'] as String? ?? 'manual',
      message: json['message'] as String?,
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
      version: json['version'] as int? ?? 0,
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
