import 'dart:convert';
import 'dart:math';
import '../models/provider_models.dart';
import '../models/room_models.dart';

class HostRoomState {
  HostRoomState({
    required this.slug,
    required this.providerId,
    this.roomName,
    this.surface,
    this.connection = const ProviderConnectionState(connected: false, providerId: '', metadata: <String, String>{}),
    this.currentClimb,
    this.status = 'open',
    this.fistBumpsEnabled = true,
    this.version = 1,
  });
  final String slug;
  String? roomName;
  String status;
  String providerId;
  int version;
  ProviderSurface? surface;
  ProviderConnectionState connection;
  ProviderClimb? currentClimb;
  bool fistBumpsEnabled;
  final List<Participant> participants = <Participant>[];
  final List<FinalistEntry> finalists = <FinalistEntry>[];
  final List<QueueEntry> queue = <QueueEntry>[];
  final Map<String, int> voteCounts = <String, int>{};
  final Map<int, List<String>> participantVotes = <int, List<String>>{}; // participantId -> climbIds
  int _nextParticipantId = 1;
  int _nextQueueEntryId = 1;
  int _nextFinalistId = 1;
  final AssistantState assistant = const AssistantState(mode: 'manual');

  int nextParticipantId() => _nextParticipantId++;
  int nextQueueEntryId() => _nextQueueEntryId++;
  int nextFinalistId() => _nextFinalistId++;
  void bumpVersion() => version++;

  String serialize() => jsonEncode(<String, dynamic>{
    'slug': slug, 'provider_id': providerId, 'room_name': roomName,
    'status': status, 'version': version, 'fist_bumps_enabled': fistBumpsEnabled,
    '_next_participant_id': _nextParticipantId,
    '_next_queue_entry_id': _nextQueueEntryId,
    '_next_finalist_id': _nextFinalistId,
    'participants': participants.map((Participant p) => <String, dynamic>{
      'id': p.id, 'display_name': p.displayName, 'role': p.role,
      'status': p.status, 'is_online': p.isOnline,
    }).toList(growable: false),
    'queue': queue.map((QueueEntry e) => <String, dynamic>{
      'id': e.id, 'status': e.status, 'position': e.position,
      'added_by': e.addedBy, 'climb': e.climb.toJson(),
    }).toList(growable: false),
    'finalists': finalists.map((FinalistEntry e) => <String, dynamic>{
      'id': e.id, 'position': e.position, 'added_by': e.addedBy, 'climb': e.climb.toJson(),
    }).toList(growable: false),
    'vote_counts': voteCounts,
    'participant_votes': participantVotes.map((int k, List<String> v) => MapEntry('$k', v)),
    if (surface != null) 'surface': surface!.toJson(),
    if (currentClimb != null) 'current_climb': currentClimb!.toJson(),
  });

  static HostRoomState deserialize(String data) {
    final Map<String, dynamic> json = jsonDecode(data) as Map<String, dynamic>;
    final HostRoomState state = HostRoomState(
      slug: json['slug'] as String? ?? '',
      providerId: json['provider_id'] as String? ?? '',
      roomName: json['room_name'] as String?,
      status: json['status'] as String? ?? 'open',
      fistBumpsEnabled: json['fist_bumps_enabled'] as bool? ?? true,
      version: (json['version'] as num?)?.toInt() ?? 1,
      surface: json['surface'] is Map<String, dynamic> ? ProviderSurface.fromJson(json['surface'] as Map<String, dynamic>) : null,
      currentClimb: json['current_climb'] is Map<String, dynamic> ? ProviderClimb.fromJson(json['current_climb'] as Map<String, dynamic>) : null,
    );
    state._nextParticipantId = (json['_next_participant_id'] as num?)?.toInt() ?? 1;
    state._nextQueueEntryId = (json['_next_queue_entry_id'] as num?)?.toInt() ?? 1;
    state._nextFinalistId = (json['_next_finalist_id'] as num?)?.toInt() ?? 1;
    final List<dynamic> rawParticipants = (json['participants'] as List<dynamic>?) ?? <dynamic>[];
    for (final dynamic p in rawParticipants) {
      if (p is Map<String, dynamic>) state.participants.add(Participant.fromJson(p));
    }
    final List<dynamic> rawQueue = (json['queue'] as List<dynamic>?) ?? <dynamic>[];
    for (final dynamic e in rawQueue) {
      if (e is Map<String, dynamic>) state.queue.add(QueueEntry.fromJson(e));
    }
    final List<dynamic> rawFinalists = (json['finalists'] as List<dynamic>?) ?? <dynamic>[];
    for (final dynamic e in rawFinalists) {
      if (e is Map<String, dynamic>) state.finalists.add(FinalistEntry.fromJson(e));
    }
    final Map<String, dynamic> rawVotes = (json['vote_counts'] as Map<String, dynamic>?) ?? <String, dynamic>{};
    for (final MapEntry<String, dynamic> entry in rawVotes.entries) {
      state.voteCounts[entry.key] = (entry.value as num?)?.toInt() ?? 0;
    }
    final Map<String, dynamic> rawPVotes = (json['participant_votes'] as Map<String, dynamic>?) ?? <String, dynamic>{};
    for (final MapEntry<String, dynamic> entry in rawPVotes.entries) {
      final int key = int.tryParse(entry.key) ?? 0;
      state.participantVotes[key] = ((entry.value as List<dynamic>?) ?? <dynamic>[]).map((dynamic v) => '$v').toList();
    }
    return state;
  }
}

class HostRoomService {
  HostRoomService({required this.state});
  final HostRoomState state;
  final Random _random = Random();

  int addParticipant({required String displayName, required String role}) {
    for (final Participant p in state.participants) {
      if (p.displayName == displayName) return -1; // name taken
    }
    final int id = state.nextParticipantId();
    state.participants.add(Participant(
      id: id,
      displayName: displayName,
      role: role,
      status: 'watching',
      isOnline: true,
    ));
    state.bumpVersion();
    return id;
  }

  bool removeParticipant(int participantId) {
    final int idx = state.participants.indexWhere((Participant p) => p.id == participantId);
    if (idx < 0) return false;
    state.participants.removeAt(idx);
    state.participantVotes.remove(participantId);
    state.bumpVersion();
    return true;
  }

  bool updateParticipantRole(int participantId, String role) {
    final int idx = state.participants.indexWhere((Participant p) => p.id == participantId);
    if (idx < 0) return false;
    final Participant old = state.participants[idx];
    state.participants[idx] = Participant(
      id: old.id, displayName: old.displayName, role: role,
      status: old.status, isOnline: old.isOnline,
    );
    state.bumpVersion();
    return true;
  }

  bool updateParticipantStatus(int participantId, String status) {
    final int idx = state.participants.indexWhere((Participant p) => p.id == participantId);
    if (idx < 0) return false;
    final Participant old = state.participants[idx];
    state.participants[idx] = Participant(
      id: old.id, displayName: old.displayName, role: old.role,
      status: status, isOnline: old.isOnline,
    );
    state.bumpVersion();
    return true;
  }

  void setParticipantOnline(int participantId, bool online) {
    final int idx = state.participants.indexWhere((Participant p) => p.id == participantId);
    if (idx < 0) return;
    final Participant old = state.participants[idx];
    state.participants[idx] = Participant(
      id: old.id, displayName: old.displayName, role: old.role,
      status: old.status, isOnline: online,
    );
    state.bumpVersion();
  }

  bool toggleVote(int participantId, String climbId) {
    if (!state.fistBumpsEnabled) return false;
    final List<String> votes = state.participantVotes.putIfAbsent(
      participantId, () => <String>[],
    );
    if (votes.contains(climbId)) {
      votes.remove(climbId);
      state.voteCounts[climbId] = (state.voteCounts[climbId] ?? 1) - 1;
      if ((state.voteCounts[climbId] ?? 0) <= 0) state.voteCounts.remove(climbId);
    } else {
      votes.add(climbId);
      state.voteCounts[climbId] = (state.voteCounts[climbId] ?? 0) + 1;
    }
    state.bumpVersion();
    return true;
  }

  void clearVotes() {
    state.voteCounts.clear();
    state.participantVotes.clear();
    state.bumpVersion();
  }

  bool addQueueEntry({required String climbId, required String addedBy, required ProviderClimb climb}) {
    for (final QueueEntry e in state.queue) {
      if (e.climb.id == climbId) return false; // already queued
    }
    final int id = state.nextQueueEntryId();
    state.queue.add(QueueEntry(
      id: id,
      status: 'queued',
      position: state.queue.length,
      addedBy: addedBy,
      climb: climb,
    ));
    state.bumpVersion();
    return true;
  }

  bool deleteQueueEntry(int entryId) {
    final int idx = state.queue.indexWhere((QueueEntry e) => e.id == entryId);
    if (idx < 0) return false;
    state.queue.removeAt(idx);
    _reindexQueue();
    state.bumpVersion();
    return true;
  }

  bool reorderQueue(List<int> entryIds) {
    final Map<int, QueueEntry> byId = <int, QueueEntry>{
      for (final QueueEntry e in state.queue) e.id: e,
    };
    final List<QueueEntry> reordered = <QueueEntry>[];
    for (final int id in entryIds) {
      final QueueEntry? entry = byId[id];
      if (entry == null) return false;
      reordered.add(entry);
    }
    state.queue
      ..clear()
      ..addAll(reordered);
    _reindexQueue();
    state.bumpVersion();
    return true;
  }

  bool updateQueueEntryStatus(int entryId, String status) {
    final int idx = state.queue.indexWhere((QueueEntry e) => e.id == entryId);
    if (idx < 0) return false;
    final QueueEntry old = state.queue[idx];
    state.queue[idx] = QueueEntry(
      id: old.id, status: status, position: old.position,
      addedBy: old.addedBy, climb: old.climb,
    );
    state.bumpVersion();
    return true;
  }

  bool promoteClimb(String climbId, String status) {
    if (status == 'current') {
      QueueEntry? entry;
      for (final QueueEntry e in state.queue) {
        if (e.climb.id == climbId) {
          entry = e;
          break;
        }
      }
      if (entry != null) {
        state.currentClimb = entry.climb;
        deleteQueueEntry(entry.id);
      }
      state.bumpVersion();
      return true;
    }
    return false;
  }

  bool addFinalist({required String climbId, required String addedBy, required ProviderClimb climb}) {
    for (final FinalistEntry e in state.finalists) {
      if (e.climb.id == climbId) return false;
    }
    final int id = state.nextFinalistId();
    state.finalists.add(FinalistEntry(
      id: id,
      position: state.finalists.length,
      addedBy: addedBy,
      climb: climb,
    ));
    state.bumpVersion();
    return true;
  }

  bool deleteFinalist(int entryId) {
    final int idx = state.finalists.indexWhere((FinalistEntry e) => e.id == entryId);
    if (idx < 0) return false;
    state.finalists.removeAt(idx);
    _reindexFinalists();
    state.bumpVersion();
    return true;
  }

  bool reorderFinalists(List<int> entryIds) {
    final Map<int, FinalistEntry> byId = <int, FinalistEntry>{
      for (final FinalistEntry e in state.finalists) e.id: e,
    };
    final List<FinalistEntry> reordered = <FinalistEntry>[];
    for (final int id in entryIds) {
      final FinalistEntry? entry = byId[id];
      if (entry == null) return false;
      reordered.add(entry);
    }
    state.finalists
      ..clear()
      ..addAll(reordered);
    _reindexFinalists();
    state.bumpVersion();
    return true;
  }

  void updateRoomName(String name) {
    state.roomName = name;
    state.bumpVersion();
  }

  void setFistBumpsEnabled(bool enabled) {
    state.fistBumpsEnabled = enabled;
    state.bumpVersion();
  }

  void setSurface(ProviderSurface surface) {
    state.surface = surface;
    state.bumpVersion();
  }

  void setConnection(ProviderConnectionState connection) {
    state.connection = connection;
    state.bumpVersion();
  }

  ProviderClimb? pickRandom(String source) {
    final List<ProviderClimb> pool;
    if (source == 'queue' && state.queue.isNotEmpty) {
      pool = state.queue.map((QueueEntry e) => e.climb).toList(growable: false);
    } else if (source == 'finalists' && state.finalists.isNotEmpty) {
      pool = state.finalists.map((FinalistEntry e) => e.climb).toList(growable: false);
    } else {
      return null;
    }
    if (pool.isEmpty) return null;
    return pool[_random.nextInt(pool.length)];
  }

  void closeRoom() {
    state.status = 'closed';
    state.bumpVersion();
  }

  RoomSnapshot toSnapshot({int? forParticipantId}) {
    final List<String> myVotes = forParticipantId != null
        ? (state.participantVotes[forParticipantId] ?? <String>[])
        : <String>[];
    final bool isHostOrCoHost = forParticipantId != null &&
        state.participants.any((Participant p) =>
            p.id == forParticipantId && (p.role == 'host' || p.role == 'co_host'));
    return RoomSnapshot(
      slug: state.slug,
      roomName: state.roomName,
      status: state.status,
      providerId: state.providerId,
      version: state.version,
      surface: state.surface,
      connection: state.connection,
      currentClimb: state.currentClimb,
      participants: List<Participant>.from(state.participants),
      finalists: List<FinalistEntry>.from(state.finalists),
      queue: List<QueueEntry>.from(state.queue),
      voteCounts: Map<String, int>.from(state.voteCounts),
      myVotes: myVotes,
      fistBumpsEnabled: state.fistBumpsEnabled,
      canManage: isHostOrCoHost,
      permissions: RoomPermissions(
        manageSession: isHostOrCoHost,
        manageSurface: isHostOrCoHost,
        manageQueue: true,
        manageFinalists: true,
        editRoomSettings: isHostOrCoHost,
        manageParticipants: isHostOrCoHost,
        assignCoHosts: isHostOrCoHost,
        closeRoom: isHostOrCoHost,
      ),
      displayName: forParticipantId != null
          ? state.participants
              .where((Participant p) => p.id == forParticipantId)
              .map((Participant p) => p.displayName)
              .firstOrNull
          : null,
      assistant: state.assistant,
    );
  }

  void _reindexQueue() {
    for (int i = 0; i < state.queue.length; i++) {
      final QueueEntry old = state.queue[i];
      state.queue[i] = QueueEntry(
        id: old.id, status: old.status, position: i,
        addedBy: old.addedBy, climb: old.climb,
      );
    }
  }

  void _reindexFinalists() {
    for (int i = 0; i < state.finalists.length; i++) {
      final FinalistEntry old = state.finalists[i];
      state.finalists[i] = FinalistEntry(
        id: old.id, position: i,
        addedBy: old.addedBy, climb: old.climb,
      );
    }
  }
}
