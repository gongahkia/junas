import 'dart:async';
import 'dart:developer' as developer;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/models/product_models.dart';
import '../../../core/models/provider_models.dart';
import '../../../core/models/room_models.dart';
import '../../../core/p2p/host_room_controller.dart';
import '../../../core/p2p/guest_room_controller.dart';
import '../../../core/p2p/p2p_transport.dart';
import '../../../core/storage/local_recap_repository.dart';

const int defaultBoardAngle = 40;
const String defaultClimbSort = 'popular';

class RoomRouteArgs {
  const RoomRouteArgs({
    required this.server,
    required this.slug,
    this.role = 'host',
    this.displayName,
    this.hostPeerId,
    this.hostPeerName,
  });
  final String server;
  final String slug;
  final String role;
  final String? displayName;
  final String? hostPeerId;
  final String? hostPeerName;
  @override
  bool operator ==(Object other) =>
      other is RoomRouteArgs && other.server == server && other.slug == slug && other.role == role;
  @override
  int get hashCode => Object.hash(server, slug, role);
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
    RoomSnapshot? room, RoomCatalogClimbsResponse? catalog,
    RoomCatalogClimbResponse? selectedCatalogClimb,
    List<ProviderSurface>? parentSurfaces, List<ProviderSurface>? childSurfaces,
    String? selectedParentSurfaceId, String? selectedChildSurfaceId,
    int? selectedAngle, String? catalogQuery, String? catalogSort,
    String? catalogNextCursor, bool? loading, bool? refreshing,
    bool? catalogLoading, bool? surfacesLoading, bool? actionInFlight,
    String? errorMessage, bool clearErrorMessage = false,
    String? joinReason, bool clearJoinReason = false,
    String? notice, bool clearNotice = false,
  }) {
    return RoomViewState(
      server: server, slug: slug,
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
    HostRoomController? hostCtrl;
    GuestRoomController? guestCtrl;
    if (args.role == 'host') {
      final HostRoomArgs ha = HostRoomArgs(
        providerId: 'kilter',
        roomName: args.slug,
        displayName: args.displayName ?? 'Host',
        fistBumpsEnabled: true,
      );
      hostCtrl = ref.read(hostRoomControllerProvider(ha).notifier);
    } else {
      final GuestRoomArgs ga = GuestRoomArgs(
        hostPeer: P2pPeer(
          id: args.hostPeerId ?? args.slug,
          displayName: args.hostPeerName ?? args.slug,
        ),
        displayName: args.displayName ?? 'Guest',
      );
      guestCtrl = ref.read(guestRoomControllerProvider(ga).notifier);
    }
    final RoomController ctrl = RoomController(
      args: args,
      hostController: hostCtrl,
      guestController: guestCtrl,
      recapRepository: ref.read(localRecapRepositoryProvider),
    );
    if (args.role == 'host') {
      final HostRoomArgs ha = HostRoomArgs(
        providerId: 'kilter',
        roomName: args.slug,
        displayName: args.displayName ?? 'Host',
        fistBumpsEnabled: true,
      );
      ref.listen<HostRoomViewState>(hostRoomControllerProvider(ha),
          (HostRoomViewState? _, HostRoomViewState next) {
        ctrl._applyHostState(next);
      });
      ctrl._applyHostState(ref.read(hostRoomControllerProvider(ha)));
    } else {
      final GuestRoomArgs ga = GuestRoomArgs(
        hostPeer: P2pPeer(
          id: args.hostPeerId ?? args.slug,
          displayName: args.hostPeerName ?? args.slug,
        ),
        displayName: args.displayName ?? 'Guest',
      );
      ref.listen<GuestRoomViewState>(guestRoomControllerProvider(ga),
          (GuestRoomViewState? _, GuestRoomViewState next) {
        ctrl._applyGuestState(next);
      });
      ctrl._applyGuestState(ref.read(guestRoomControllerProvider(ga)));
    }
    return ctrl;
  },
);

class RoomController extends StateNotifier<RoomViewState> {
  RoomController({
    required RoomRouteArgs args,
    this.hostController,
    this.guestController,
    required this.recapRepository,
  }) : super(RoomViewState(server: Uri.parse(args.server), slug: args.slug));

  final HostRoomController? hostController;
  final GuestRoomController? guestController;
  final LocalRecapRepository recapRepository;

  void _applyHostState(HostRoomViewState hs) {
    state = state.copyWith(
      room: hs.room, loading: !hs.hosting,
      errorMessage: hs.errorMessage, clearErrorMessage: hs.errorMessage == null,
    );
  }

  void _applyGuestState(GuestRoomViewState gs) {
    state = state.copyWith(
      room: gs.room, loading: gs.loading,
      errorMessage: gs.errorMessage, clearErrorMessage: gs.errorMessage == null,
    );
  }

  Future<void> load() async {
    // force re-read from underlying P2P controller
    final RoomSnapshot? hostSnap = hostController?.hostSnapshot;
    final RoomSnapshot? guestSnap = guestController?.state.room;
    final RoomSnapshot? snap = hostSnap ?? guestSnap;
    if (snap != null) {
      state = state.copyWith(room: snap, loading: false, clearErrorMessage: true);
    } else {
      state = state.copyWith(loading: false, errorMessage: 'No room data available from P2P peer.');
    }
  }

  Future<void> refresh({bool silent = false}) async {
    if (!silent) state = state.copyWith(refreshing: true, clearErrorMessage: true);
    final RoomSnapshot? hostSnap = hostController?.hostSnapshot;
    final RoomSnapshot? guestSnap = guestController?.state.room;
    final RoomSnapshot? snap = hostSnap ?? guestSnap;
    if (snap != null) {
      state = state.copyWith(room: snap, refreshing: false, loading: false, clearErrorMessage: true);
    } else {
      state = state.copyWith(refreshing: false, loading: false, errorMessage: 'No room data available from P2P peer.');
    }
  }

  Future<void> toggleVote(String climbId) async {
    hostController?.hostToggleVote(climbId);
    guestController?.service?.toggleVote(climbId);
  }

  Future<void> addQueueEntry(String climbId) async {
    final ProviderClimb? climb = _findClimb(climbId);
    if (climb == null) return;
    hostController?.hostAddQueueEntry(climb);
    guestController?.service?.addQueueEntry(climb);
  }

  Future<void> addFinalist(String climbId) async {
    final ProviderClimb? climb = _findClimb(climbId);
    if (climb == null) return;
    hostController?.hostAddFinalist(climb);
    guestController?.service?.addFinalist(climb);
  }

  Future<void> deleteQueueEntry(int entryId) async {
    hostController?.hostDeleteQueueEntry(entryId);
    guestController?.service?.deleteQueueEntry(entryId);
  }

  Future<void> deleteFinalist(int entryId) async {
    hostController?.hostDeleteFinalist(entryId);
    guestController?.service?.deleteFinalist(entryId);
  }

  Future<void> moveQueueEntry(int entryId, int delta) async {
    final RoomSnapshot? room = state.room;
    if (room == null) return;
    final List<QueueEntry> q = List<QueueEntry>.from(room.queue);
    final int i = q.indexWhere((QueueEntry e) => e.id == entryId);
    if (i < 0 || i + delta < 0 || i + delta >= q.length) return;
    q.insert(i + delta, q.removeAt(i));
    final List<int> ids = q.map((QueueEntry e) => e.id).toList(growable: false);
    hostController?.hostReorderQueue(ids);
    guestController?.service?.reorderQueue(ids);
  }

  Future<void> moveFinalist(int entryId, int delta) async {
    final RoomSnapshot? room = state.room;
    if (room == null) return;
    final List<FinalistEntry> f = List<FinalistEntry>.from(room.finalists);
    final int i = f.indexWhere((FinalistEntry e) => e.id == entryId);
    if (i < 0 || i + delta < 0 || i + delta >= f.length) return;
    f.insert(i + delta, f.removeAt(i));
    final List<int> ids = f.map((FinalistEntry e) => e.id).toList(growable: false);
    hostController?.hostReorderFinalists(ids);
    guestController?.service?.reorderFinalists(ids);
  }

  Future<void> promoteClimb(String climbId, String status) async {
    hostController?.hostPromoteClimb(climbId, status);
    guestController?.service?.promoteClimb(climbId, status);
  }

  Future<void> addQueueStatusUpdate(int entryId, String status) async {
    hostController?.hostUpdateQueueEntryStatus(entryId, status);
  }

  Future<void> clearVotes() async {
    hostController?.hostClearVotes();
    guestController?.service?.clearVotes();
  }

  Future<void> pickRandom(String source) async {
    hostController?.hostPickRandom(source);
    guestController?.service?.pickRandom(source);
  }

  Future<void> updateRoomName(String roomName) async {
    hostController?.hostUpdateRoomName(roomName);
    guestController?.service?.updateRoomName(roomName);
  }

  Future<void> setFistBumpsEnabled(bool enabled) async {
    hostController?.hostSetFistBumpsEnabled(enabled);
    guestController?.service?.setFistBumpsEnabled(enabled);
  }

  Future<void> updateMyStatus(String status) async {
    hostController?.hostUpdateMyStatus(status);
    guestController?.service?.updateMyStatus(status);
  }

  Future<void> updateParticipantRole(int participantId, String role) async {
    hostController?.hostUpdateParticipantRole(participantId, role);
    guestController?.service?.updateParticipantRole(participantId, role);
  }

  Future<void> removeParticipant(int participantId) async {
    hostController?.hostRemoveParticipant(participantId);
    guestController?.service?.removeParticipant(participantId);
  }

  Future<void> closeRoom() async {
    hostController?.hostCloseRoom();
    guestController?.service?.closeRoom();
    await _saveRecap();
  }

  Future<void> _saveRecap() async {
    final RoomSnapshot? room = state.room;
    if (room == null) return;
    final String shareId = '${room.slug}-${DateTime.now().millisecondsSinceEpoch}';
    final RoomRecap recap = RoomRecap(
      shareId: shareId,
      roomSlug: room.slug,
      roomName: room.roomName,
      providerId: room.providerId,
      surfaceName: room.surface?.name,
      closedAt: DateTime.now().toUtc(),
      slides: <RecapSlide>[
        RecapSlide(
          id: 'summary',
          eyebrow: 'Session complete',
          title: room.roomName ?? 'Session recap',
          description: '${room.participants.length} participants, ${room.queue.length} queued, ${room.finalists.length} finalists.',
          stats: <RecapStat>[
            RecapStat(label: 'Participants', value: '${room.participants.length}'),
            RecapStat(label: 'Queue', value: '${room.queue.length}'),
            RecapStat(label: 'Finalists', value: '${room.finalists.length}'),
            RecapStat(label: 'Votes', value: '${room.voteCounts.length}'),
          ],
          climbs: <SessionSummaryClimb>[
            ...room.queue.map((QueueEntry e) => SessionSummaryClimb(
              climb: e.climb, position: e.position, status: e.status, addedBy: e.addedBy,
            )),
          ],
          participants: room.participants.map((Participant p) => p.displayName).toList(growable: false),
        ),
      ],
    );
    try {
      await recapRepository.saveRecap(
        shareId: shareId, slug: room.slug,
        roomName: room.roomName, providerId: room.providerId,
        recap: recap,
      );
    } catch (e) {
      developer.log('Failed to save recap: $e', name: 'RoomController');
      state = state.copyWith(errorMessage: 'Recap could not be saved locally: $e');
    }
  }

  Future<void> setSurface() async {
    final String sid = state.room?.providerId == 'kilter'
        ? state.selectedParentSurfaceId : state.selectedChildSurfaceId;
    if (sid.isEmpty) return;
    final ProviderSurface surface = ProviderSurface(
      id: sid, kind: state.room?.providerId == 'kilter' ? 'board' : 'wall',
      name: sid, description: '',
      meta: <String, String>{
        if (state.room?.providerId == 'kilter') 'angle': '${state.selectedAngle}',
        if (state.room?.providerId == 'kilter') 'board_id': sid,
      },
    );
    hostController?.hostSetSurface(surface);
    guestController?.service?.setSurface(surface);
    state = state.copyWith(notice: 'Surface updated.');
  }

  void updateSurfaceDraft({String? parentSurfaceId, String? childSurfaceId, int? angle}) {
    state = state.copyWith(
      selectedParentSurfaceId: parentSurfaceId,
      selectedChildSurfaceId: childSurfaceId,
      selectedAngle: angle,
    );
  }

  Future<void> loadSurfaces({String? parentId}) async {
    // host reads board list from offline Kilter catalog as ProviderSurface entries
    // for Kilter: surfaces are boards (product_size_id + name)
    // for Crux: would need relay — not yet supported
    if (hostController != null) {
      state = state.copyWith(surfacesLoading: true);
      // host can set surface directly by ID — populate with the current surface if available
      final RoomSnapshot? room = state.room;
      final List<ProviderSurface> surfaces = <ProviderSurface>[];
      if (room?.surface != null) {
        surfaces.add(room!.surface!);
      }
      state = state.copyWith(
        surfacesLoading: false,
        parentSurfaces: surfaces,
        selectedParentSurfaceId: room?.surface?.id ?? state.selectedParentSurfaceId,
      );
    } else {
      state = state.copyWith(
        errorMessage: 'Surface selection is managed by the host device.',
        surfacesLoading: false,
      );
    }
  }

  Future<void> loadCatalog({String? q, String? sort, String? cursor, String? gradeMin, String? gradeMax}) async {
    state = state.copyWith(
      catalogLoading: true,
      catalogQuery: q ?? state.catalogQuery,
      catalogSort: sort ?? state.catalogSort,
      clearErrorMessage: true,
    );
    if (guestController != null) {
      // guest sends catalog query to host via P2P
      guestController!.service?.queryCatalog(<String, dynamic>{
        'board_id': state.selectedParentSurfaceId,
        'angle': state.selectedAngle,
        'page': 1,
        'page_size': 10,
        'q': q ?? state.catalogQuery,
        'sort': sort ?? state.catalogSort,
        'grade_min': gradeMin,
        'grade_max': gradeMax,
      });
      // response arrives async via guestController catalogResponse handling
      // set a timeout to clear loading state if no response
      Future<void>.delayed(const Duration(seconds: 5), () {
        if (state.catalogLoading) {
          state = state.copyWith(catalogLoading: false, errorMessage: 'Catalog query timed out.');
        }
      });
    } else if (hostController != null) {
      // host queries own offline catalog directly — build ProviderClimb results
      // from the host's room snapshot current data
      state = state.copyWith(
        catalogLoading: false,
        notice: 'Host catalog browsing uses the offline Kilter database directly via the solo tab.',
      );
    } else {
      state = state.copyWith(catalogLoading: false, errorMessage: 'No P2P connection for catalog.');
    }
  }

  Future<void> selectCatalogClimb(String climbId) async {
    // find the climb in queue, finalists, or current climb and set as selected
    final ProviderClimb? climb = _findClimb(climbId);
    if (climb == null) {
      state = state.copyWith(errorMessage: 'Climb not found in room data.');
      return;
    }
    final bool isQueued = state.room?.queue.any((QueueEntry e) => e.climb.id == climbId) ?? false;
    final int voteCount = state.room?.voteCounts[climbId] ?? 0;
    final bool myVote = state.room?.myVotes.contains(climbId) ?? false;
    state = state.copyWith(
      selectedCatalogClimb: RoomCatalogClimbResponse(
        climb: climb,
        voteCount: voteCount,
        myVote: myVote,
        isQueued: isQueued,
      ),
    );
  }

  Future<void> reconnectProvider(Map<String, String> secret) async {
    // in P2P mode the host already owns the provider connection directly.
    if (hostController != null) {
      state = state.copyWith(notice: 'Provider connection is active on this host device.');
    } else {
      state = state.copyWith(errorMessage: 'Only the host device can manage provider credentials.');
    }
  }

  Future<void> updateAssistantMode(String mode) async {
    // assistant mode was a server-side AI suggestion feature with no P2P equivalent.
    // surface a clear message so the UI toggle isn't silently dead.
    state = state.copyWith(notice: 'Assistant mode is not available in P2P sessions.');
  }

  Future<void> autoRefillQueue() async {
    final RoomSnapshot? room = state.room;
    if (room == null) return;
    final Set<String> existing = <String>{
      ...room.queue.map((QueueEntry e) => e.climb.id),
      ...room.finalists.map((FinalistEntry e) => e.climb.id),
    };
    final List<MapEntry<String, int>> sorted = room.voteCounts.entries
        .where((MapEntry<String, int> e) => e.value > 0 && !existing.contains(e.key))
        .toList(growable: false)
      ..sort((MapEntry<String, int> a, MapEntry<String, int> b) => b.value.compareTo(a.value));
    if (sorted.isEmpty) {
      state = state.copyWith(notice: 'No voted climbs available to refill the queue.');
      return;
    }
    for (final String id in sorted.take(5).map((MapEntry<String, int> e) => e.key)) {
      await addQueueEntry(id);
    }
    state = state.copyWith(notice: 'Added top-voted climbs to the queue.');
  }

  Future<void> importPendingSeed(List<String> climbIds) async {
    if (climbIds.isEmpty) {
      state = state.copyWith(notice: 'Every saved climb is already queued.');
      return;
    }
    for (final String id in climbIds) { await addQueueEntry(id); }
    state = state.copyWith(notice: 'Imported ${climbIds.length} climbs into the queue.');
  }

  void setClientError(String message) {
    state = state.copyWith(errorMessage: message, clearNotice: true);
  }

  ProviderClimb? _findClimb(String climbId) {
    final RoomSnapshot? room = state.room;
    if (room == null) return null;
    for (final QueueEntry e in room.queue) { if (e.climb.id == climbId) return e.climb; }
    for (final FinalistEntry e in room.finalists) { if (e.climb.id == climbId) return e.climb; }
    if (room.currentClimb?.id == climbId) return room.currentClimb;
    return null;
  }
}
