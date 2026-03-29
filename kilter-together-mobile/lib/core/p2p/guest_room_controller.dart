import 'dart:async';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/room_models.dart';
import '../../features/room/application/room_controller.dart';
import 'guest_room_service.dart';
import 'p2p_message_types.dart';
import 'p2p_provider.dart';
import 'p2p_transport.dart';

class GuestRoomArgs {
  const GuestRoomArgs({
    required this.hostPeer,
    required this.displayName,
  });
  final P2pPeer hostPeer;
  final String displayName;
}

class GuestRoomViewState {
  const GuestRoomViewState({
    this.room,
    this.participantId,
    this.connected = false,
    this.loading = true,
    this.kicked = false,
    this.roomClosed = false,
    this.errorMessage,
    this.catalog,
  });
  final RoomSnapshot? room;
  final int? participantId;
  final bool connected;
  final bool loading;
  final bool kicked;
  final bool roomClosed;
  final String? errorMessage;
  final RoomCatalogClimbsResponse? catalog;
}

final guestRoomControllerProvider = StateNotifierProvider.autoDispose
    .family<GuestRoomController, GuestRoomViewState, GuestRoomArgs>(
  (Ref ref, GuestRoomArgs args) {
    return GuestRoomController(
      args: args,
      transport: ref.read(p2pTransportProvider),
    );
  },
);

class GuestRoomController extends StateNotifier<GuestRoomViewState> {
  GuestRoomController({
    required GuestRoomArgs args,
    required P2pTransport transport,
  })  : _args = args,
        _transport = transport,
        super(const GuestRoomViewState()) {
    _init();
  }

  final GuestRoomArgs _args;
  final P2pTransport _transport;
  GuestRoomService? _service;
  StreamSubscription<P2pMessage>? _messageSub;
  StreamSubscription<P2pConnectionChange>? _connectionSub;

  Future<void> _init() async {
    _messageSub = _transport.messages.listen(_handleMessage);
    _connectionSub =
        _transport.connectionChanges.listen(_handleConnectionChange);
    try {
      await _transport.connectToPeer(_args.hostPeer);
    } catch (e) {
      state = GuestRoomViewState(errorMessage: 'Failed to connect: $e');
      return;
    }
    _service = GuestRoomService(
      transport: _transport,
      hostPeerId: _args.hostPeer.id,
    );
    _service!.sendJoinRequest(_args.displayName);
  }

  void _handleConnectionChange(P2pConnectionChange change) {
    if (change.peer.id == _args.hostPeer.id &&
        change.event == P2pConnectionEvent.disconnected) {
      state = const GuestRoomViewState(
        connected: false,
        loading: false,
        errorMessage: 'Lost connection to host.',
      );
    }
  }

  void _handleMessage(P2pMessage message) {
    switch (message.type) {
      case P2pMessageType.joinAccepted:
        final int participantId =
            (message.payload['participant_id'] as num?)?.toInt() ?? 0;
        final Map<String, dynamic> snapshotJson =
            (message.payload['snapshot'] as Map<String, dynamic>?) ??
                <String, dynamic>{};
        state = GuestRoomViewState(
          room: RoomSnapshot.fromJson(snapshotJson),
          participantId: participantId,
          connected: true,
          loading: false,
        );
      case P2pMessageType.joinRejected:
        final String reason =
            message.payload['reason'] as String? ?? 'Join rejected.';
        state = GuestRoomViewState(
          loading: false,
          errorMessage: reason,
        );
      case P2pMessageType.roomStateUpdate:
        state = GuestRoomViewState(
          room: RoomSnapshot.fromJson(message.payload),
          participantId: state.participantId,
          connected: true,
          loading: false,
          catalog: state.catalog,
        );
      case P2pMessageType.kicked:
        state = const GuestRoomViewState(
          connected: false,
          loading: false,
          kicked: true,
          errorMessage: 'You were removed from the room.',
        );
      case P2pMessageType.roomClosed:
        state = GuestRoomViewState(
          room: state.room,
          participantId: state.participantId,
          connected: false,
          loading: false,
          roomClosed: true,
        );
      case P2pMessageType.catalogResponse:
        state = GuestRoomViewState(
          room: state.room,
          participantId: state.participantId,
          connected: state.connected,
          loading: false,
          catalog: RoomCatalogClimbsResponse.fromJson(message.payload),
        );
      default:
        break;
    }
  }

  // guest actions — delegate to service
  GuestRoomService? get service => _service;

  RoomViewState toRoomViewState() {
    final RoomSnapshot? room = state.room;
    return RoomViewState(
      server: Uri.parse('p2p://local'),
      slug: room?.slug ?? '',
      room: room,
      loading: state.loading,
      errorMessage: state.errorMessage,
    );
  }

  @override
  void dispose() {
    _messageSub?.cancel();
    _connectionSub?.cancel();
    _service?.leaveRoom();
    super.dispose();
  }
}
