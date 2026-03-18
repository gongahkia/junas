import 'dart:async';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/models/provider_models.dart';
import '../../../core/models/room_models.dart';
import '../../../core/p2p/host_room_controller.dart';
import '../../../core/p2p/guest_room_controller.dart';
import '../../../core/storage/app_prefs_controller.dart';

const int defaultBoardAngle = 40;
const String defaultClimbSort = 'popular';

class RoomRouteArgs {
  const RoomRouteArgs({
    required this.server,
    required this.slug,
  });
  final String server;
  final String slug;
  @override
  bool operator ==(Object other) =>
      other is RoomRouteArgs && other.server == server && other.slug == slug;
  @override
  int get hashCode => Object.hash(server, slug);
}

class RoomViewState {
  const RoomViewState({
    required this.server,
    required this.slug,
    this.room,
    this.catalog,
    this.selectedCatalogClimb,
    this.parentSurfaces = const <ProviderSurface>[],
    this.childSurfaces = const <ProviderSurface>[],
    this.selectedParentSurfaceId = '',
    this.selectedChildSurfaceId = '',
    this.selectedAngle = defaultBoardAngle,
    this.catalogQuery = '',
    this.catalogSort = defaultClimbSort,
    this.catalogNextCursor,
    this.loading = true,
    this.refreshing = false,
    this.catalogLoading = false,
    this.surfacesLoading = false,
    this.actionInFlight = false,
    this.errorMessage,
    this.joinReason,
    this.notice,
  });
  final Uri server;
  final String slug;
  final RoomSnapshot? room;
  final RoomCatalogClimbsResponse? catalog;
  final RoomCatalogClimbResponse? selectedCatalogClimb;
  final List<ProviderSurface> parentSurfaces;
  final List<ProviderSurface> childSurfaces;
  final String selectedParentSurfaceId;
  final String selectedChildSurfaceId;
  final int selectedAngle;
  final String catalogQuery;
  final String catalogSort;
  final String? catalogNextCursor;
  final bool loading;
  final bool refreshing;
  final bool catalogLoading;
  final bool surfacesLoading;
  final bool actionInFlight;
  final String? errorMessage;
  final String? joinReason;
  final String? notice;
  bool get requiresRejoin => joinReason != null;
  bool get hasNestedSurfaceHierarchy => room?.providerId == 'crux';

  RoomViewState copyWith({
    RoomSnapshot? room,
    RoomCatalogClimbsResponse? catalog,
    RoomCatalogClimbResponse? selectedCatalogClimb,
    List<ProviderSurface>? parentSurfaces,
    List<ProviderSurface>? childSurfaces,
    String? selectedParentSurfaceId,
    String? selectedChildSurfaceId,
    int? selectedAngle,
    String? catalogQuery,
    String? catalogSort,
    String? catalogNextCursor,
    bool? loading,
    bool? refreshing,
    bool? catalogLoading,
    bool? surfacesLoading,
    bool? actionInFlight,
    String? errorMessage,
    bool clearErrorMessage = false,
    String? joinReason,
    bool clearJoinReason = false,
    String? notice,
    bool clearNotice = false,
  }) {
    return RoomViewState(
      server: server,
      slug: slug,
      room: room ?? this.room,
      catalog: catalog ?? this.catalog,
      selectedCatalogClimb: selectedCatalogClimb ?? this.selectedCatalogClimb,
      parentSurfaces: parentSurfaces ?? this.parentSurfaces,
      childSurfaces: childSurfaces ?? this.childSurfaces,
      selectedParentSurfaceId: selectedParentSurfaceId ?? this.selectedParentSurfaceId,
      selectedChildSurfaceId: selectedChildSurfaceId ?? this.selectedChildSurfaceId,
      selectedAngle: selectedAngle ?? this.selectedAngle,
      catalogQuery: catalogQuery ?? this.catalogQuery,
      catalogSort: catalogSort ?? this.catalogSort,
      catalogNextCursor: catalogNextCursor ?? this.catalogNextCursor,
      loading: loading ?? this.loading,
      refreshing: refreshing ?? this.refreshing,
      catalogLoading: catalogLoading ?? this.catalogLoading,
      surfacesLoading: surfacesLoading ?? this.surfacesLoading,
      actionInFlight: actionInFlight ?? this.actionInFlight,
      errorMessage: clearErrorMessage ? null : (errorMessage ?? this.errorMessage),
      joinReason: clearJoinReason ? null : (joinReason ?? this.joinReason),
      notice: clearNotice ? null : (notice ?? this.notice),
    );
  }
}

final roomControllerProvider = StateNotifierProvider.autoDispose
    .family<RoomController, RoomViewState, RoomRouteArgs>(
  (Ref ref, RoomRouteArgs args) {
    return RoomController(
      args: args,
      appPrefsController: ref.read(appPrefsControllerProvider.notifier),
    );
  },
);

/// P2P adapter — wraps host or guest controller into RoomViewState.
/// The room_screen reads this provider unchanged; actual P2P state comes
/// from hostRoomControllerProvider / guestRoomControllerProvider which are
/// activated by create_room / join flows before navigating here.
class RoomController extends StateNotifier<RoomViewState> {
  RoomController({
    required RoomRouteArgs args,
    required AppPrefsController appPrefsController,
  })  : super(RoomViewState(
          server: Uri.parse(args.server),
          slug: args.slug,
          loading: false,
        ));

  HostRoomController? _hostController;
  GuestRoomController? _guestController;

  void bindHost(HostRoomController controller) {
    _hostController = controller;
    _syncFromHost();
  }

  void bindGuest(GuestRoomController controller) {
    _guestController = controller;
    _syncFromGuest();
  }

  void _syncFromHost() {
    final HostRoomViewState? hs = _hostController?.state;
    if (hs == null) return;
    state = state.copyWith(
      room: hs.room,
      loading: false,
      errorMessage: hs.errorMessage,
      clearErrorMessage: hs.errorMessage == null,
    );
  }

  void _syncFromGuest() {
    final GuestRoomViewState? gs = _guestController?.state;
    if (gs == null) return;
    state = state.copyWith(
      room: gs.room,
      loading: gs.loading,
      errorMessage: gs.errorMessage,
      clearErrorMessage: gs.errorMessage == null,
    );
  }

  void updateFromSnapshot(RoomSnapshot snapshot) {
    state = state.copyWith(room: snapshot, loading: false);
  }

  // action forwarding — host path
  Future<void> load() async { _syncFromHost(); _syncFromGuest(); }
  Future<void> refresh({bool silent = false}) async { _syncFromHost(); _syncFromGuest(); }

  Future<void> toggleVote(String climbId) async {
    _hostController?.hostToggleVote(climbId);
    _guestController?.service?.toggleVote(climbId);
  }

  Future<void> addQueueEntry(String climbId) async {
    // need ProviderClimb — find from catalog or queue
    final ProviderClimb? climb = _findClimb(climbId);
    if (climb == null) return;
    _hostController?.hostAddQueueEntry(climb);
    _guestController?.service?.addQueueEntry(climb);
  }

  Future<void> addFinalist(String climbId) async {
    final ProviderClimb? climb = _findClimb(climbId);
    if (climb == null) return;
    _hostController?.hostAddFinalist(climb);
    _guestController?.service?.addFinalist(climb);
  }

  Future<void> deleteQueueEntry(int entryId) async {
    _hostController?.hostDeleteQueueEntry(entryId);
    _guestController?.service?.deleteQueueEntry(entryId);
  }

  Future<void> deleteFinalist(int entryId) async {
    _hostController?.hostDeleteFinalist(entryId);
    _guestController?.service?.deleteFinalist(entryId);
  }

  Future<void> moveQueueEntry(int entryId, int delta) async {
    final RoomSnapshot? room = state.room;
    if (room == null) return;
    final List<QueueEntry> queue = List<QueueEntry>.from(room.queue);
    final int idx = queue.indexWhere((QueueEntry e) => e.id == entryId);
    if (idx < 0) return;
    final int next = idx + delta;
    if (next < 0 || next >= queue.length) return;
    final QueueEntry moved = queue.removeAt(idx);
    queue.insert(next, moved);
    final List<int> ids = queue.map((QueueEntry e) => e.id).toList(growable: false);
    _hostController?.hostReorderQueue(ids);
    _guestController?.service?.reorderQueue(ids);
  }

  Future<void> moveFinalist(int entryId, int delta) async {
    final RoomSnapshot? room = state.room;
    if (room == null) return;
    final List<FinalistEntry> finalists = List<FinalistEntry>.from(room.finalists);
    final int idx = finalists.indexWhere((FinalistEntry e) => e.id == entryId);
    if (idx < 0) return;
    final int next = idx + delta;
    if (next < 0 || next >= finalists.length) return;
    final FinalistEntry moved = finalists.removeAt(idx);
    finalists.insert(next, moved);
    final List<int> ids = finalists.map((FinalistEntry e) => e.id).toList(growable: false);
    _hostController?.hostReorderFinalists(ids);
    _guestController?.service?.reorderFinalists(ids);
  }

  Future<void> promoteClimb(String climbId, String status) async {
    _hostController?.hostPromoteClimb(climbId, status);
    _guestController?.service?.promoteClimb(climbId, status);
  }

  Future<void> addQueueStatusUpdate(int entryId, String status) async {
    _hostController?.hostUpdateQueueEntryStatus(entryId, status);
  }

  Future<void> clearVotes() async {
    _hostController?.hostClearVotes();
    _guestController?.service?.clearVotes();
  }

  Future<void> pickRandom(String source) async {
    _hostController?.hostPickRandom(source);
    _guestController?.service?.pickRandom(source);
  }

  Future<void> updateRoomName(String roomName) async {
    _hostController?.hostUpdateRoomName(roomName);
    _guestController?.service?.updateRoomName(roomName);
  }

  Future<void> setFistBumpsEnabled(bool enabled) async {
    _hostController?.hostSetFistBumpsEnabled(enabled);
    _guestController?.service?.setFistBumpsEnabled(enabled);
  }

  Future<void> updateMyStatus(String status) async {
    _hostController?.hostUpdateMyStatus(status);
    _guestController?.service?.updateMyStatus(status);
  }

  Future<void> updateParticipantRole(int participantId, String role) async {
    _hostController?.hostUpdateParticipantRole(participantId, role);
    _guestController?.service?.updateParticipantRole(participantId, role);
  }

  Future<void> removeParticipant(int participantId) async {
    _hostController?.hostRemoveParticipant(participantId);
    _guestController?.service?.removeParticipant(participantId);
  }

  Future<void> closeRoom() async {
    _hostController?.hostCloseRoom();
    _guestController?.service?.closeRoom();
  }

  Future<void> setSurface() async {
    // host sets surface locally
    if (_hostController != null) {
      final String surfaceId = state.room?.providerId == 'kilter'
          ? state.selectedParentSurfaceId
          : state.selectedChildSurfaceId;
      if (surfaceId.isEmpty) return;
      _hostController!.hostSetSurface(ProviderSurface(
        id: surfaceId,
        kind: state.room?.providerId == 'kilter' ? 'board' : 'wall',
        name: surfaceId,
        description: '',
        meta: <String, String>{
          if (state.room?.providerId == 'kilter') 'angle': '${state.selectedAngle}',
          if (state.room?.providerId == 'kilter') 'board_id': surfaceId,
        },
      ));
    }
  }

  void updateSurfaceDraft({String? parentSurfaceId, String? childSurfaceId, int? angle}) {
    state = state.copyWith(
      selectedParentSurfaceId: parentSurfaceId,
      selectedChildSurfaceId: childSurfaceId,
      selectedAngle: angle,
    );
  }

  Future<void> loadSurfaces({String? parentId}) async {}
  Future<void> loadCatalog({String? q, String? sort, String? cursor, String? gradeMin, String? gradeMax}) async {}
  Future<void> selectCatalogClimb(String climbId) async {}
  Future<void> reconnectProvider(Map<String, String> secret) async {}
  Future<void> updateAssistantMode(String mode) async {}
  Future<void> autoRefillQueue() async {}
  Future<void> importPendingSeed(List<String> climbIds) async {}
  void setClientError(String message) {
    state = state.copyWith(errorMessage: message, clearNotice: true);
  }

  ProviderClimb? _findClimb(String climbId) {
    final RoomSnapshot? room = state.room;
    if (room == null) return null;
    for (final QueueEntry e in room.queue) {
      if (e.climb.id == climbId) return e.climb;
    }
    for (final FinalistEntry e in room.finalists) {
      if (e.climb.id == climbId) return e.climb;
    }
    if (room.currentClimb?.id == climbId) return room.currentClimb;
    return null;
  }
}
