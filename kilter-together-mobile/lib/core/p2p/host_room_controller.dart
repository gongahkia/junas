import 'dart:async';
import 'dart:developer' as developer;
import 'dart:math';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../models/provider_models.dart';
import '../models/room_models.dart';
import '../storage/offline_kilter_catalog_repository.dart';
import 'catalog_relay_service.dart';
import 'host_room_service.dart';
import 'p2p_message_types.dart';
import 'p2p_provider.dart';
import 'p2p_transport.dart';

const String _stateKey = 'kilter_host_room_state';

String _generateSlug() {
  const String chars = 'abcdefghijklmnopqrstuvwxyz0123456789';
  final Random rng = Random();
  return List<String>.generate(8, (_) => chars[rng.nextInt(chars.length)])
      .join();
}

class HostRoomArgs {
  const HostRoomArgs({
    required this.providerId,
    required this.roomName,
    required this.displayName,
    required this.fistBumpsEnabled,
  });
  final String providerId;
  final String roomName;
  final String displayName;
  final bool fistBumpsEnabled;
}

class HostRoomViewState {
  const HostRoomViewState({
    this.room,
    this.hosting = false,
    this.errorMessage,
  });
  final RoomSnapshot? room;
  final bool hosting;
  final String? errorMessage;
}

final hostRoomControllerProvider = StateNotifierProvider.autoDispose
    .family<HostRoomController, HostRoomViewState, HostRoomArgs>(
  (Ref ref, HostRoomArgs args) {
    return HostRoomController(
      args: args,
      transport: ref.read(p2pTransportProvider),
      catalogRepository: ref.read(offlineKilterCatalogRepositoryProvider),
    );
  },
);

class HostRoomController extends StateNotifier<HostRoomViewState> {
  HostRoomController({
    required HostRoomArgs args,
    required P2pTransport transport,
    required OfflineKilterCatalogRepository catalogRepository,
  })  : _args = args,
        _transport = transport,
        _catalogRepository = catalogRepository,
        super(const HostRoomViewState()) {
    _init();
  }

  final HostRoomArgs _args;
  final P2pTransport _transport;
  final OfflineKilterCatalogRepository _catalogRepository;
  late final HostRoomService _service;
  CatalogRelayService? _catalogRelay;
  final Map<String, int> _peerParticipantIds =
      <String, int>{}; // peerId -> participantId
  StreamSubscription<P2pMessage>? _messageSub;
  StreamSubscription<P2pConnectionChange>? _connectionSub;
  int? _hostParticipantId;

  Future<void> _init() async {
    final String slug = _generateSlug();
    final HostRoomState roomState = HostRoomState(
      slug: slug,
      providerId: _args.providerId,
      roomName: _args.roomName,
      fistBumpsEnabled: _args.fistBumpsEnabled,
    );
    _service = HostRoomService(state: roomState);
    _hostParticipantId = _service.addParticipant(
      displayName: _args.displayName,
      role: 'host',
    );
    _catalogRelay = CatalogRelayService(
      transport: _transport,
      catalogRepository: _catalogRepository,
    )..start();
    _messageSub = _transport.messages.listen(_handleMessage);
    _connectionSub =
        _transport.connectionChanges.listen(_handleConnectionChange);
    try {
      await _transport.startAdvertising(
        displayName: '${_args.roomName}|$slug',
        serviceId: p2pServiceId,
      );
      state = HostRoomViewState(
        room: _service.toSnapshot(forParticipantId: _hostParticipantId),
        hosting: true,
      );
    } catch (e) {
      state = HostRoomViewState(errorMessage: 'Failed to start hosting: $e');
    }
  }

  void _handleConnectionChange(P2pConnectionChange change) {
    if (change.event == P2pConnectionEvent.disconnected) {
      final int? participantId = _peerParticipantIds.remove(change.peer.id);
      if (participantId != null) {
        _service.setParticipantOnline(participantId, false);
        _broadcastState();
      }
    }
  }

  bool _senderIsHost(String peerId) {
    final int? participantId = _peerParticipantIds[peerId];
    if (participantId == null) return false;
    final Participant? p = _service.state.participants
        .where((Participant p) => p.id == participantId)
        .firstOrNull;
    return p != null && (p.role == 'host' || p.role == 'co_host');
  }

  void _handleMessage(P2pMessage message) {
    final String? senderId = message.senderId;
    if (senderId == null) return;
    switch (message.type) {
      case P2pMessageType.joinRequest:
        _handleJoinRequest(senderId, message.payload);
      case P2pMessageType.voteToggle:
        _handleVoteToggle(senderId, message.payload);
      case P2pMessageType.queueAdd:
        _handleQueueAdd(senderId, message.payload);
      case P2pMessageType.queueDelete:
        _handleQueueDelete(senderId, message.payload);
      case P2pMessageType.queueReorder:
        _handleQueueReorder(senderId, message.payload);
      case P2pMessageType.finalistAdd:
        _handleFinalistAdd(senderId, message.payload);
      case P2pMessageType.finalistDelete:
        _handleFinalistDelete(senderId, message.payload);
      case P2pMessageType.finalistReorder:
        _handleFinalistReorder(senderId, message.payload);
      case P2pMessageType.statusUpdate:
        _handleStatusUpdate(senderId, message.payload);
      case P2pMessageType.leaveRoom:
        _handleLeaveRoom(senderId);
      case P2pMessageType.promoteClimb:
        if (!_senderIsHost(senderId)) return;
        _handlePromoteClimb(senderId, message.payload);
      case P2pMessageType.clearVotes:
        if (!_senderIsHost(senderId)) return;
        _service.clearVotes();
        _broadcastState();
      case P2pMessageType.updateRoomName:
        if (!_senderIsHost(senderId)) return;
        _service.updateRoomName(message.payload['room_name'] as String? ?? '');
        _broadcastState();
      case P2pMessageType.setFistBumps:
        if (!_senderIsHost(senderId)) return;
        _service
            .setFistBumpsEnabled(message.payload['enabled'] as bool? ?? true);
        _broadcastState();
      case P2pMessageType.setSurface:
        if (!_senderIsHost(senderId)) return;
        final Map<String, dynamic> raw =
            (message.payload['surface'] as Map<String, dynamic>?) ??
                <String, dynamic>{};
        _service.setSurface(ProviderSurface.fromJson(raw));
        _broadcastState();
      case P2pMessageType.pickRandom:
        if (!_senderIsHost(senderId)) return;
        _handlePickRandom(senderId, message.payload);
      case P2pMessageType.updateRole:
        if (!_senderIsHost(senderId)) return;
        _handleUpdateRole(senderId, message.payload);
      case P2pMessageType.removeParticipant:
        if (!_senderIsHost(senderId)) return;
        _handleRemoveParticipant(senderId, message.payload);
      case P2pMessageType.closeRoom:
        if (!_senderIsHost(senderId)) return;
        _handleCloseRoom(senderId);
      case P2pMessageType.catalogQuery:
        break; // handled by catalog relay
      default:
        break;
    }
  }

  void _handleJoinRequest(String peerId, Map<String, dynamic> payload) {
    final String displayName =
        (payload['display_name'] as String? ?? '').trim();
    if (displayName.isEmpty) {
      _sendTo(
          peerId,
          P2pMessage(
            type: P2pMessageType.joinRejected,
            payload: <String, dynamic>{'reason': 'Display name is required.'},
          ));
      return;
    }
    if (displayName.length > 40) {
      _sendTo(
          peerId,
          P2pMessage(
            type: P2pMessageType.joinRejected,
            payload: <String, dynamic>{
              'reason': 'Display name must be 40 characters or fewer.'
            },
          ));
      return;
    }
    final int participantId =
        _service.addParticipant(displayName: displayName, role: 'participant');
    if (participantId < 0) {
      _sendTo(
          peerId,
          P2pMessage(
            type: P2pMessageType.joinRejected,
            payload: <String, dynamic>{
              'reason': 'That display name is already taken.'
            },
          ));
      return;
    }
    _peerParticipantIds[peerId] = participantId;
    final RoomSnapshot snapshot =
        _service.toSnapshot(forParticipantId: participantId);
    _sendTo(
        peerId,
        P2pMessage(
          type: P2pMessageType.joinAccepted,
          payload: <String, dynamic>{
            'participant_id': participantId,
            'snapshot': _snapshotToJson(snapshot),
          },
        ));
    _broadcastState();
  }

  void _handleVoteToggle(String peerId, Map<String, dynamic> payload) {
    final int? participantId = _peerParticipantIds[peerId];
    if (participantId == null) return;
    final String climbId = payload['climb_id'] as String? ?? '';
    if (climbId.isEmpty) return;
    _service.toggleVote(participantId, climbId);
    _broadcastState();
  }

  void _handleQueueAdd(String peerId, Map<String, dynamic> payload) {
    final int? participantId = _peerParticipantIds[peerId];
    final String addedBy = participantId != null
        ? _service.state.participants
                .where((Participant p) => p.id == participantId)
                .map((Participant p) => p.displayName)
                .firstOrNull ??
            ''
        : '';
    final Map<String, dynamic> climbJson =
        (payload['climb'] as Map<String, dynamic>?) ?? <String, dynamic>{};
    final ProviderClimb climb = ProviderClimb.fromJson(climbJson);
    _service.addQueueEntry(climbId: climb.id, addedBy: addedBy, climb: climb);
    _broadcastState();
  }

  void _handleQueueDelete(String peerId, Map<String, dynamic> payload) {
    final int entryId = (payload['entry_id'] as num?)?.toInt() ?? 0;
    _service.deleteQueueEntry(entryId);
    _broadcastState();
  }

  void _handleQueueReorder(String peerId, Map<String, dynamic> payload) {
    final List<int> entryIds =
        ((payload['entry_ids'] as List<dynamic>?) ?? <dynamic>[])
            .map((dynamic e) => (e as num).toInt())
            .toList(growable: false);
    _service.reorderQueue(entryIds);
    _broadcastState();
  }

  void _handleFinalistAdd(String peerId, Map<String, dynamic> payload) {
    final int? participantId = _peerParticipantIds[peerId];
    final String addedBy = participantId != null
        ? _service.state.participants
                .where((Participant p) => p.id == participantId)
                .map((Participant p) => p.displayName)
                .firstOrNull ??
            ''
        : '';
    final Map<String, dynamic> climbJson =
        (payload['climb'] as Map<String, dynamic>?) ?? <String, dynamic>{};
    final ProviderClimb climb = ProviderClimb.fromJson(climbJson);
    _service.addFinalist(climbId: climb.id, addedBy: addedBy, climb: climb);
    _broadcastState();
  }

  void _handleFinalistDelete(String peerId, Map<String, dynamic> payload) {
    final int entryId = (payload['entry_id'] as num?)?.toInt() ?? 0;
    _service.deleteFinalist(entryId);
    _broadcastState();
  }

  void _handleFinalistReorder(String peerId, Map<String, dynamic> payload) {
    final List<int> entryIds =
        ((payload['entry_ids'] as List<dynamic>?) ?? <dynamic>[])
            .map((dynamic e) => (e as num).toInt())
            .toList(growable: false);
    _service.reorderFinalists(entryIds);
    _broadcastState();
  }

  void _handleStatusUpdate(String peerId, Map<String, dynamic> payload) {
    final int? participantId = _peerParticipantIds[peerId];
    if (participantId == null) return;
    final String status = payload['status'] as String? ?? 'watching';
    _service.updateParticipantStatus(participantId, status);
    _broadcastState();
  }

  void _handleLeaveRoom(String peerId) {
    final int? participantId = _peerParticipantIds.remove(peerId);
    if (participantId != null) {
      _service.removeParticipant(participantId);
    }
    unawaited(_transport.disconnectFromPeer(peerId));
    _broadcastState();
  }

  void _handlePromoteClimb(String peerId, Map<String, dynamic> payload) {
    final String climbId = payload['climb_id'] as String? ?? '';
    final String status = payload['status'] as String? ?? 'current';
    _service.promoteClimb(climbId, status);
    _broadcastState();
  }

  void _handlePickRandom(String peerId, Map<String, dynamic> payload) {
    final String source = payload['source'] as String? ?? 'queue';
    _service.pickRandom(source);
    _broadcastState();
  }

  void _handleUpdateRole(String peerId, Map<String, dynamic> payload) {
    final int participantId = (payload['participant_id'] as num?)?.toInt() ?? 0;
    final String role = payload['role'] as String? ?? 'participant';
    _service.updateParticipantRole(participantId, role);
    _broadcastState();
  }

  void _handleRemoveParticipant(String peerId, Map<String, dynamic> payload) {
    final int participantId = (payload['participant_id'] as num?)?.toInt() ?? 0;
    final String? targetPeerId = _peerParticipantIds.entries
        .where((MapEntry<String, int> e) => e.value == participantId)
        .map((MapEntry<String, int> e) => e.key)
        .firstOrNull;
    _service.removeParticipant(participantId);
    if (targetPeerId != null) {
      _peerParticipantIds.remove(targetPeerId);
      _sendTo(
          targetPeerId,
          const P2pMessage(
            type: P2pMessageType.kicked,
            payload: <String, dynamic>{},
          ));
      unawaited(_transport.disconnectFromPeer(targetPeerId));
    }
    _broadcastState();
  }

  void _handleCloseRoom(String peerId) {
    _service.closeRoom();
    _transport.broadcast(const P2pMessage(
      type: P2pMessageType.roomClosed,
      payload: <String, dynamic>{},
    ));
    _broadcastState();
  }

  // host-local actions
  void hostToggleVote(String climbId) {
    if (_hostParticipantId == null) return;
    _service.toggleVote(_hostParticipantId!, climbId);
    _broadcastState();
  }

  void hostAddQueueEntry(ProviderClimb climb) {
    _service.addQueueEntry(
        climbId: climb.id, addedBy: _args.displayName, climb: climb);
    _broadcastState();
  }

  void hostDeleteQueueEntry(int entryId) {
    _service.deleteQueueEntry(entryId);
    _broadcastState();
  }

  void hostReorderQueue(List<int> entryIds) {
    _service.reorderQueue(entryIds);
    _broadcastState();
  }

  void hostUpdateQueueEntryStatus(int entryId, String status) {
    _service.updateQueueEntryStatus(entryId, status);
    _broadcastState();
  }

  void hostAddFinalist(ProviderClimb climb) {
    _service.addFinalist(
        climbId: climb.id, addedBy: _args.displayName, climb: climb);
    _broadcastState();
  }

  void hostDeleteFinalist(int entryId) {
    _service.deleteFinalist(entryId);
    _broadcastState();
  }

  void hostReorderFinalists(List<int> entryIds) {
    _service.reorderFinalists(entryIds);
    _broadcastState();
  }

  void hostPromoteClimb(String climbId, String status) {
    _service.promoteClimb(climbId, status);
    _broadcastState();
  }

  void hostClearVotes() {
    _service.clearVotes();
    _broadcastState();
  }

  void hostPickRandom(String source) {
    _service.pickRandom(source);
    _broadcastState();
  }

  void hostUpdateRoomName(String name) {
    _service.updateRoomName(name);
    _broadcastState();
  }

  void hostSetFistBumpsEnabled(bool enabled) {
    _service.setFistBumpsEnabled(enabled);
    _broadcastState();
  }

  void hostSetSurface(ProviderSurface surface) {
    _service.setSurface(surface);
    _broadcastState();
  }

  void hostUpdateMyStatus(String status) {
    if (_hostParticipantId != null) {
      _service.updateParticipantStatus(_hostParticipantId!, status);
      _broadcastState();
    }
  }

  void hostUpdateParticipantRole(int participantId, String role) {
    _service.updateParticipantRole(participantId, role);
    _broadcastState();
  }

  void hostRemoveParticipant(int participantId) {
    final String? targetPeerId = _peerParticipantIds.entries
        .where((MapEntry<String, int> e) => e.value == participantId)
        .map((MapEntry<String, int> e) => e.key)
        .firstOrNull;
    _service.removeParticipant(participantId);
    if (targetPeerId != null) {
      _peerParticipantIds.remove(targetPeerId);
      _sendTo(
          targetPeerId,
          const P2pMessage(
            type: P2pMessageType.kicked,
            payload: <String, dynamic>{},
          ));
      unawaited(_transport.disconnectFromPeer(targetPeerId));
    }
    _broadcastState();
  }

  void hostCloseRoom() {
    _service.closeRoom();
    _transport.broadcast(const P2pMessage(
      type: P2pMessageType.roomClosed,
      payload: <String, dynamic>{},
    ));
    _broadcastState();
  }

  RoomSnapshot get hostSnapshot =>
      _service.toSnapshot(forParticipantId: _hostParticipantId);
  String get slug => _service.state.slug;
  int? get hostParticipantId => _hostParticipantId;

  void _broadcastState() {
    state = HostRoomViewState(
      room: _service.toSnapshot(forParticipantId: _hostParticipantId),
      hosting: true,
    );
    for (final MapEntry<String, int> entry in _peerParticipantIds.entries) {
      final RoomSnapshot peerSnapshot =
          _service.toSnapshot(forParticipantId: entry.value);
      _sendTo(
          entry.key,
          P2pMessage(
            type: P2pMessageType.roomStateUpdate,
            payload: _snapshotToJson(peerSnapshot),
          ));
    }
    _persistState();
  }

  Future<void> _persistState() async {
    try {
      final SharedPreferences prefs = await SharedPreferences.getInstance();
      await prefs.setString(_stateKey, _service.state.serialize());
    } catch (e) {
      developer.log('failed to persist host room state: $e', name: 'HostRoom');
    }
  }

  static Future<void> clearPersistedState() async {
    final SharedPreferences prefs = await SharedPreferences.getInstance();
    await prefs.remove(_stateKey);
  }

  static Future<HostRoomState?> loadPersistedState() async {
    try {
      final SharedPreferences prefs = await SharedPreferences.getInstance();
      final String? data = prefs.getString(_stateKey);
      if (data == null) return null;
      return HostRoomState.deserialize(data);
    } catch (e) {
      developer.log('failed to load persisted host room state: $e',
          name: 'HostRoom');
      return null;
    }
  }

  void _sendTo(String peerId, P2pMessage message) {
    unawaited(_transport.send(peerId, message));
  }

  Map<String, dynamic> _snapshotToJson(RoomSnapshot snapshot) {
    return <String, dynamic>{
      'slug': snapshot.slug,
      'room_name': snapshot.roomName,
      'status': snapshot.status,
      'provider_id': snapshot.providerId,
      'version': snapshot.version,
      'fist_bumps_enabled': snapshot.fistBumpsEnabled,
      'can_manage': snapshot.canManage,
      'display_name': snapshot.displayName,
      'vote_counts': snapshot.voteCounts,
      'my_votes': snapshot.myVotes,
      'participants': snapshot.participants
          .map((Participant p) => <String, dynamic>{
                'id': p.id,
                'display_name': p.displayName,
                'role': p.role,
                'status': p.status,
                'is_online': p.isOnline,
              })
          .toList(growable: false),
      'queue': snapshot.queue
          .map((QueueEntry e) => <String, dynamic>{
                'id': e.id,
                'status': e.status,
                'position': e.position,
                'added_by': e.addedBy,
                'climb': e.climb.toJson(),
              })
          .toList(growable: false),
      'finalists': snapshot.finalists
          .map((FinalistEntry e) => <String, dynamic>{
                'id': e.id,
                'position': e.position,
                'added_by': e.addedBy,
                'climb': e.climb.toJson(),
              })
          .toList(growable: false),
      if (snapshot.surface != null) 'surface': snapshot.surface!.toJson(),
      if (snapshot.currentClimb != null)
        'current_climb': snapshot.currentClimb!.toJson(),
      'connection': <String, dynamic>{
        'connected': snapshot.connection.connected,
        'provider_id': snapshot.connection.providerId,
        'metadata': snapshot.connection.metadata,
      },
      'permissions': <String, dynamic>{
        'manage_session': snapshot.permissions.manageSession,
        'manage_surface': snapshot.permissions.manageSurface,
        'manage_queue': snapshot.permissions.manageQueue,
        'manage_finalists': snapshot.permissions.manageFinalists,
        'edit_room_settings': snapshot.permissions.editRoomSettings,
        'manage_participants': snapshot.permissions.manageParticipants,
        'assign_co_hosts': snapshot.permissions.assignCoHosts,
        'close_room': snapshot.permissions.closeRoom,
      },
      'assistant': <String, dynamic>{
        'mode': snapshot.assistant.mode,
      },
    };
  }

  @override
  void dispose() {
    _catalogRelay?.dispose();
    _messageSub?.cancel();
    _connectionSub?.cancel();
    unawaited(_transport.stopAdvertising());
    unawaited(_transport.disconnectAll());
    if (_service.state.status == 'closed') {
      unawaited(clearPersistedState()); // clean close — no recovery needed
    }
    super.dispose();
  }
}
