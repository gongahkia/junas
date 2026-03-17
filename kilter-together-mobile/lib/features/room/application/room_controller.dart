import 'dart:async';
import 'dart:convert';

import 'package:flutter/widgets.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../main.dart';

import '../../../core/models/app_prefs_models.dart';
import '../../../core/models/board_models.dart';
import '../../../core/models/provider_models.dart';
import '../../../core/models/room_models.dart';
import '../../../core/models/session_models.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/sse_client.dart';
import '../../../core/storage/app_prefs_controller.dart';
import '../../../core/storage/provider_secret_repository.dart';
import '../../../core/storage/session_repository.dart';

class RoomRouteArgs {
  const RoomRouteArgs({
    required this.server,
    required this.slug,
  });

  final String server;
  final String slug;

  Uri get serverUri => normalizeServerUri(server);

  @override
  bool operator ==(Object other) {
    return other is RoomRouteArgs &&
        other.server == server &&
        other.slug == slug;
  }

  @override
  int get hashCode => Object.hash(server, slug);
}

class RoomViewState {
  const RoomViewState({
    required this.server,
    required this.slug,
    this.session,
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
  final RoomSession? session;
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
    RoomSession? session,
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
      session: session ?? this.session,
      room: room ?? this.room,
      catalog: catalog ?? this.catalog,
      selectedCatalogClimb: selectedCatalogClimb ?? this.selectedCatalogClimb,
      parentSurfaces: parentSurfaces ?? this.parentSurfaces,
      childSurfaces: childSurfaces ?? this.childSurfaces,
      selectedParentSurfaceId:
          selectedParentSurfaceId ?? this.selectedParentSurfaceId,
      selectedChildSurfaceId:
          selectedChildSurfaceId ?? this.selectedChildSurfaceId,
      selectedAngle: selectedAngle ?? this.selectedAngle,
      catalogQuery: catalogQuery ?? this.catalogQuery,
      catalogSort: catalogSort ?? this.catalogSort,
      catalogNextCursor: catalogNextCursor ?? this.catalogNextCursor,
      loading: loading ?? this.loading,
      refreshing: refreshing ?? this.refreshing,
      catalogLoading: catalogLoading ?? this.catalogLoading,
      surfacesLoading: surfacesLoading ?? this.surfacesLoading,
      actionInFlight: actionInFlight ?? this.actionInFlight,
      errorMessage:
          clearErrorMessage ? null : (errorMessage ?? this.errorMessage),
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
      apiClient: ref.read(apiClientProvider),
      sessionRepository: ref.read(sessionRepositoryProvider),
      sseClient: ref.read(sseClientProvider),
      appPrefsController: ref.read(appPrefsControllerProvider.notifier),
      providerSecretRepository: ref.read(providerSecretRepositoryProvider),
      notifications: ref.read(localNotificationsProvider),
    );
  },
);

class RoomController extends StateNotifier<RoomViewState> {
  RoomController({
    required RoomRouteArgs args,
    required ApiClient apiClient,
    required SessionRepository sessionRepository,
    required SseClient sseClient,
    required AppPrefsController appPrefsController,
    required ProviderSecretRepository providerSecretRepository,
    required FlutterLocalNotificationsPlugin notifications,
  })  : _args = args,
        _apiClient = apiClient,
        _sessionRepository = sessionRepository,
        _sseClient = sseClient,
        _appPrefsController = appPrefsController,
        _providerSecretRepository = providerSecretRepository,
        _notifications = notifications,
        super(RoomViewState(
          server: args.serverUri,
          slug: args.slug,
        )) {
    unawaited(load());
    _sessionRefreshTimer = Timer.periodic(const Duration(minutes: 5), (_) {
      unawaited(_checkSessionRefresh());
    });
  }

  final RoomRouteArgs _args;
  final ApiClient _apiClient;
  final SessionRepository _sessionRepository;
  final SseClient _sseClient;
  final AppPrefsController _appPrefsController;
  final ProviderSecretRepository _providerSecretRepository;
  final FlutterLocalNotificationsPlugin _notifications;

  StreamSubscription<SseMessage>? _subscription;
  String? _lastCurrentClimbId;
  Timer? _sessionRefreshTimer;
  Timer? _debounceTimer;
  bool _refreshInFlight = false;
  bool _disposed = false;

  @override
  void dispose() {
    _disposed = true;
    _sessionRefreshTimer?.cancel();
    _debounceTimer?.cancel();
    unawaited(_subscription?.cancel());
    super.dispose();
  }

  Future<void> load() async {
    state = state.copyWith(
      loading: true,
      clearErrorMessage: true,
      clearJoinReason: true,
      clearNotice: true,
    );

    final RoomSession? session = await _sessionRepository.readSession(
      server: _args.serverUri,
      slug: _args.slug,
    );
    if (session == null) {
      state = state.copyWith(
        session: null,
        loading: false,
        joinReason: 'session_required',
        errorMessage:
            'This device does not have a saved room session. Join the room again.',
      );
      return;
    }

    try {
      final RoomSnapshot room = await _apiClient.getRoom(
        server: _args.serverUri,
        slug: _args.slug,
        sessionToken: session.token,
      );
      final AppPrefs prefs = await _loadAppPrefs();
      final ({
        String selectedParentSurfaceId,
        String selectedChildSurfaceId,
        int selectedAngle
      }) surfaceDraft = _resolveSurfaceDraft(room, prefs);
      state = state.copyWith(
        session: session,
        room: room,
        catalog: room.surface != null && room.connection.connected
            ? state.catalog
            : null,
        selectedCatalogClimb: room.surface != null && room.connection.connected
            ? state.selectedCatalogClimb
            : null,
        selectedParentSurfaceId: surfaceDraft.selectedParentSurfaceId,
        selectedChildSurfaceId: surfaceDraft.selectedChildSurfaceId,
        selectedAngle: surfaceDraft.selectedAngle,
        loading: false,
        clearErrorMessage: true,
        clearJoinReason: true,
      );
      unawaited(_rememberSnapshotContext(room));
      await _attachEvents(session.token);
      if (room.connection.connected && room.permissions.manageSurface) {
        unawaited(loadSurfaces());
      }
      if (room.surface != null && room.connection.connected) {
        unawaited(loadCatalog());
      }
    } on ApiFailure catch (error) {
      await _handleApiFailure(error);
    }
  }

  Future<void> refresh({bool silent = false}) async {
    final RoomSession? session = state.session;
    if (session == null) {
      await load();
      return;
    }

    if (!silent) {
      state = state.copyWith(refreshing: true, clearErrorMessage: true);
    }
    try {
      final RoomSnapshot room = await _apiClient.getRoom(
        server: _args.serverUri,
        slug: _args.slug,
        sessionToken: session.token,
      );
      final AppPrefs prefs = await _loadAppPrefs();
      final ({
        String selectedParentSurfaceId,
        String selectedChildSurfaceId,
        int selectedAngle
      }) surfaceDraft = _resolveSurfaceDraft(room, prefs);
      state = state.copyWith(
        room: room,
        catalog: room.surface != null && room.connection.connected
            ? state.catalog
            : null,
        selectedCatalogClimb: room.surface != null && room.connection.connected
            ? state.selectedCatalogClimb
            : null,
        selectedParentSurfaceId: surfaceDraft.selectedParentSurfaceId,
        selectedChildSurfaceId: surfaceDraft.selectedChildSurfaceId,
        selectedAngle: surfaceDraft.selectedAngle,
        refreshing: false,
        loading: false,
        clearErrorMessage: true,
        clearJoinReason: true,
      );
      unawaited(_rememberSnapshotContext(room));
      unawaited(_checkClimbChangeNotification(room));
      if (room.surface != null && room.connection.connected) {
        unawaited(loadCatalog(
          q: state.catalogQuery,
          sort: state.catalogSort,
          cursor: null,
        ));
      }
    } on ApiFailure catch (error) {
      state = state.copyWith(refreshing: false);
      await _handleApiFailure(error);
    }
  }

  Future<void> loadCatalog({
    String? q,
    String? sort,
    String? cursor,
  }) async {
    final RoomSnapshot? room = state.room;
    final RoomSession? session = state.session;
    if (room == null || session == null || room.surface == null) {
      return;
    }

    state = state.copyWith(
      catalogLoading: true,
      catalogQuery: q ?? state.catalogQuery,
      catalogSort: sort ?? state.catalogSort,
      clearErrorMessage: true,
    );

    try {
      final RoomCatalogClimbsResponse catalog =
          await _apiClient.getRoomCatalogClimbs(
        server: _args.serverUri,
        slug: _args.slug,
        sessionToken: session.token,
        q: q ?? state.catalogQuery,
        sort: sort ?? state.catalogSort,
        cursor: cursor,
      );
      RoomCatalogClimbResponse? selectedCatalogClimb =
          state.selectedCatalogClimb;
      final String? selectedClimbId = selectedCatalogClimb?.climb.id;
      final ProviderClimb? firstClimb =
          catalog.climbs.isEmpty ? null : catalog.climbs.first;
      if (selectedClimbId != null &&
          catalog.climbs
              .any((ProviderClimb item) => item.id == selectedClimbId)) {
        selectedCatalogClimb = await _apiClient.getRoomCatalogClimb(
          server: _args.serverUri,
          slug: _args.slug,
          sessionToken: session.token,
          climbId: selectedClimbId,
        );
      } else if (firstClimb != null) {
        selectedCatalogClimb = await _apiClient.getRoomCatalogClimb(
          server: _args.serverUri,
          slug: _args.slug,
          sessionToken: session.token,
          climbId: firstClimb.id,
        );
      }
      state = state.copyWith(
        catalogLoading: false,
        catalog: catalog,
        selectedCatalogClimb: selectedCatalogClimb,
        catalogNextCursor: catalog.nextCursor,
      );
    } on ApiFailure catch (error) {
      state = state.copyWith(
        catalogLoading: false,
        errorMessage: error.message,
      );
      if (error.isAuthFailure) {
        await _handleApiFailure(error);
      }
    }
  }

  Future<void> selectCatalogClimb(String climbId) async {
    final RoomSession? session = state.session;
    if (session == null) {
      return;
    }
    try {
      final RoomCatalogClimbResponse climb =
          await _apiClient.getRoomCatalogClimb(
        server: _args.serverUri,
        slug: _args.slug,
        sessionToken: session.token,
        climbId: climbId,
      );
      state = state.copyWith(
        selectedCatalogClimb: climb,
        clearErrorMessage: true,
      );
    } on ApiFailure catch (error) {
      state = state.copyWith(errorMessage: error.message);
      if (error.isAuthFailure) {
        await _handleApiFailure(error);
      }
    }
  }

  Future<void> loadSurfaces({String? parentId}) async {
    final RoomSnapshot? room = state.room;
    final RoomSession? session = state.session;
    if (room == null || session == null || !room.connection.connected) {
      return;
    }

    state = state.copyWith(surfacesLoading: true, clearErrorMessage: true);
    try {
      final List<ProviderSurface> surfaces =
          await _apiClient.getRoomCatalogSurfaces(
        server: _args.serverUri,
        slug: _args.slug,
        sessionToken: session.token,
        parentId: parentId,
      );
      if (parentId == null || parentId.isEmpty) {
        String nextParentId = state.selectedParentSurfaceId;
        if (room.providerId == 'kilter') {
          state = state.copyWith(
            surfacesLoading: false,
            parentSurfaces: surfaces,
          );
          return;
        }
        if (nextParentId.isEmpty ||
            !surfaces.any((ProviderSurface item) => item.id == nextParentId)) {
          nextParentId = surfaces.isEmpty ? '' : surfaces.first.id;
        }
        state = state.copyWith(
          surfacesLoading: false,
          parentSurfaces: surfaces,
          selectedParentSurfaceId: nextParentId,
        );
        if (nextParentId.isNotEmpty) {
          await loadSurfaces(parentId: nextParentId);
        }
        return;
      }

      String nextChildId = state.selectedChildSurfaceId;
      if (nextChildId.isEmpty ||
          !surfaces.any((ProviderSurface item) => item.id == nextChildId)) {
        nextChildId = surfaces.isEmpty ? '' : surfaces.first.id;
      }
      state = state.copyWith(
        surfacesLoading: false,
        childSurfaces: surfaces,
        selectedChildSurfaceId: nextChildId,
      );
    } on ApiFailure catch (error) {
      state = state.copyWith(
        surfacesLoading: false,
        errorMessage: error.message,
      );
      if (error.isAuthFailure) {
        await _handleApiFailure(error);
      }
    }
  }

  void updateSurfaceDraft({
    String? parentSurfaceId,
    String? childSurfaceId,
    int? angle,
  }) {
    state = state.copyWith(
      selectedParentSurfaceId: parentSurfaceId,
      selectedChildSurfaceId: childSurfaceId,
      selectedAngle: angle,
    );
  }

  Future<void> setSurface() async {
    final RoomSnapshot? room = state.room;
    final RoomSession? session = state.session;
    if (room == null || session == null) {
      return;
    }

    final String surfaceId = room.providerId == 'kilter'
        ? state.selectedParentSurfaceId
        : state.selectedChildSurfaceId;
    if (surfaceId.isEmpty) {
      state = state.copyWith(
          errorMessage: 'Pick a surface before saving the room context.');
      return;
    }

    final Map<String, String> context = room.providerId == 'kilter'
        ? <String, String>{
            'angle': '${state.selectedAngle}',
            'board_id': surfaceId,
            'parent_id': '',
          }
        : <String, String>{
            'gym_slug': state.selectedParentSurfaceId,
            'parent_id': state.selectedParentSurfaceId,
          };

    await _mutate(
      notice: 'Surface updated.',
      action: () => _apiClient.setRoomSurface(
        server: _args.serverUri,
        slug: _args.slug,
        sessionToken: session.token,
        surfaceId: surfaceId,
        context: context,
      ),
    );
  }

  Future<void> reconnectProvider(Map<String, String> secret) async {
    final RoomSession? session = state.session;
    if (session == null) {
      return;
    }

    try {
      state = state.copyWith(
        actionInFlight: true,
        clearErrorMessage: true,
        clearNotice: true,
      );
      await _apiClient.connectRoomProvider(
        server: _args.serverUri,
        slug: _args.slug,
        sessionToken: session.token,
        secret: secret,
      );
      await refresh(silent: true);
      await loadSurfaces();
      state = state.copyWith(
        actionInFlight: false,
        notice: 'Provider credentials validated.',
      );
    } on ApiFailure catch (error) {
      state = state.copyWith(
        actionInFlight: false,
        errorMessage: _formatReconnectFailure(error),
      );
      if (error.isAuthFailure) {
        await _handleApiFailure(error);
      }
    }
  }

  void setClientError(String message) {
    state = state.copyWith(
      errorMessage: message,
      clearNotice: true,
    );
  }

  Future<void> updateRoomName(String roomName) async {
    final RoomSession? session = state.session;
    if (session == null) {
      return;
    }
    await _mutate(
      notice: 'Room name updated.',
      action: () => _apiClient.updateRoom(
        server: _args.serverUri,
        slug: _args.slug,
        sessionToken: session.token,
        roomName: roomName,
      ),
    );
  }

  Future<void> setFistBumpsEnabled(bool enabled) async {
    final RoomSession? session = state.session;
    if (session == null) {
      return;
    }
    await _mutate(
      notice: enabled ? 'Fist bumps enabled.' : 'Fist bumps disabled.',
      action: () => _apiClient.setRoomFistBumpsEnabled(
        server: _args.serverUri,
        slug: _args.slug,
        sessionToken: session.token,
        enabled: enabled,
      ),
    );
  }

  Future<void> updateAssistantMode(String mode) async {
    final RoomSession? session = state.session;
    if (session == null) {
      return;
    }
    await _mutate(
      notice: 'Assistant mode updated.',
      action: () => _apiClient.updateRoomAssistantMode(
        server: _args.serverUri,
        slug: _args.slug,
        sessionToken: session.token,
        mode: mode,
      ),
    );
  }

  Future<void> toggleVote(String climbId) async {
    final RoomSession? session = state.session;
    if (session == null) {
      return;
    }
    await _mutate(
      action: () => _apiClient.toggleRoomVote(
        server: _args.serverUri,
        slug: _args.slug,
        sessionToken: session.token,
        climbId: climbId,
      ),
    );
  }

  Future<void> addQueueEntry(String climbId) async {
    final RoomSession? session = state.session;
    if (session == null) {
      return;
    }
    await _mutate(
      notice: 'Climb added to queue.',
      action: () => _apiClient.addRoomQueueEntry(
        server: _args.serverUri,
        slug: _args.slug,
        sessionToken: session.token,
        climbId: climbId,
      ),
    );
  }

  Future<void> addFinalist(String climbId) async {
    final RoomSession? session = state.session;
    if (session == null) {
      return;
    }
    await _mutate(
      notice: 'Climb added to finalists.',
      action: () => _apiClient.addRoomFinalist(
        server: _args.serverUri,
        slug: _args.slug,
        sessionToken: session.token,
        climbId: climbId,
      ),
    );
  }

  Future<void> deleteFinalist(int entryId) async {
    final RoomSession? session = state.session;
    if (session == null) {
      return;
    }
    await _mutate(
      notice: 'Finalist removed.',
      action: () => _apiClient.deleteRoomFinalist(
        server: _args.serverUri,
        slug: _args.slug,
        sessionToken: session.token,
        entryId: entryId,
      ),
    );
  }

  Future<void> moveFinalist(int entryId, int delta) async {
    final RoomSession? session = state.session;
    final RoomSnapshot? room = state.room;
    if (session == null || room == null) {
      return;
    }
    final List<FinalistEntry> finalists =
        List<FinalistEntry>.from(room.finalists);
    final int currentIndex =
        finalists.indexWhere((FinalistEntry item) => item.id == entryId);
    if (currentIndex < 0) {
      return;
    }
    final int nextIndex = currentIndex + delta;
    if (nextIndex < 0 || nextIndex >= finalists.length) {
      return;
    }
    final FinalistEntry moved = finalists.removeAt(currentIndex);
    finalists.insert(nextIndex, moved);
    await _mutate(
      notice: 'Finalist order updated.',
      action: () => _apiClient.reorderRoomFinalists(
        server: _args.serverUri,
        slug: _args.slug,
        sessionToken: session.token,
        entryIds: finalists
            .map((FinalistEntry item) => item.id)
            .toList(growable: false),
      ),
    );
  }

  Future<void> addQueueStatusUpdate(int entryId, String status) async {
    final RoomSession? session = state.session;
    if (session == null) {
      return;
    }
    await _mutate(
      notice: 'Queue status updated.',
      action: () => _apiClient.updateRoomQueueEntry(
        server: _args.serverUri,
        slug: _args.slug,
        sessionToken: session.token,
        entryId: entryId,
        status: status,
      ),
    );
  }

  Future<void> deleteQueueEntry(int entryId) async {
    final RoomSession? session = state.session;
    if (session == null) {
      return;
    }
    await _mutate(
      notice: 'Queue entry removed.',
      action: () => _apiClient.deleteRoomQueueEntry(
        server: _args.serverUri,
        slug: _args.slug,
        sessionToken: session.token,
        entryId: entryId,
      ),
    );
  }

  Future<void> moveQueueEntry(int entryId, int delta) async {
    final RoomSession? session = state.session;
    final RoomSnapshot? room = state.room;
    if (session == null || room == null) {
      return;
    }
    final List<QueueEntry> queue = List<QueueEntry>.from(room.queue);
    final int currentIndex =
        queue.indexWhere((QueueEntry item) => item.id == entryId);
    if (currentIndex < 0) {
      return;
    }
    final int nextIndex = currentIndex + delta;
    if (nextIndex < 0 || nextIndex >= queue.length) {
      return;
    }
    final QueueEntry moved = queue.removeAt(currentIndex);
    queue.insert(nextIndex, moved);
    await _mutate(
      notice: 'Queue order updated.',
      action: () => _apiClient.reorderRoomQueue(
        server: _args.serverUri,
        slug: _args.slug,
        sessionToken: session.token,
        entryIds:
            queue.map((QueueEntry item) => item.id).toList(growable: false),
      ),
    );
  }

  Future<void> promoteClimb(String climbId, String status) async {
    final RoomSession? session = state.session;
    if (session == null) {
      return;
    }
    await _mutate(
      notice: status == 'current'
          ? 'Current climb updated.'
          : 'Next climb updated.',
      action: () => _apiClient.promoteRoomQueueClimb(
        server: _args.serverUri,
        slug: _args.slug,
        sessionToken: session.token,
        climbId: climbId,
        status: status,
      ),
    );
  }

  Future<void> clearVotes() async {
    final RoomSession? session = state.session;
    if (session == null) {
      return;
    }
    await _mutate(
      notice: 'Room fist bumps cleared.',
      action: () => _apiClient.clearRoomVotes(
        server: _args.serverUri,
        slug: _args.slug,
        sessionToken: session.token,
      ),
    );
  }

  Future<void> pickRandom(String source) async {
    final RoomSession? session = state.session;
    if (session == null) {
      return;
    }
    try {
      state = state.copyWith(
          actionInFlight: true, clearErrorMessage: true, clearNotice: true);
      final ProviderClimb climb = await _apiClient.pickRandomRoomClimb(
        server: _args.serverUri,
        slug: _args.slug,
        sessionToken: session.token,
        source: source,
      );
      await refresh(silent: true);
      state = state.copyWith(
        actionInFlight: false,
        notice: 'Suggested climb: ${climb.name}',
      );
    } on ApiFailure catch (error) {
      state =
          state.copyWith(actionInFlight: false, errorMessage: error.message);
      if (error.isAuthFailure) {
        await _handleApiFailure(error);
      }
    }
  }

  Future<void> updateMyStatus(String status) async {
    final RoomSession? session = state.session;
    if (session == null) {
      return;
    }
    await _mutate(
      action: () => _apiClient.updateMyParticipantStatus(
        server: _args.serverUri,
        slug: _args.slug,
        sessionToken: session.token,
        status: status,
      ),
    );
  }

  Future<void> updateParticipantRole(int participantId, String role) async {
    final RoomSession? session = state.session;
    if (session == null) {
      return;
    }
    await _mutate(
      notice: 'Participant role updated.',
      action: () => _apiClient.updateRoomParticipantRole(
        server: _args.serverUri,
        slug: _args.slug,
        sessionToken: session.token,
        participantId: participantId,
        role: role,
      ),
    );
  }

  Future<void> removeParticipant(int participantId) async {
    final RoomSession? session = state.session;
    if (session == null) {
      return;
    }
    await _mutate(
      notice: 'Participant removed.',
      action: () => _apiClient.removeRoomParticipant(
        server: _args.serverUri,
        slug: _args.slug,
        sessionToken: session.token,
        participantId: participantId,
      ),
    );
  }

  Future<void> closeRoom() async {
    final RoomSession? session = state.session;
    if (session == null) {
      return;
    }
    await _mutate(
      notice: 'Room closed.',
      action: () => _apiClient.closeRoom(
        server: _args.serverUri,
        slug: _args.slug,
        sessionToken: session.token,
      ),
    );
  }

  Future<void> importPendingSeed(List<String> climbIds) async {
    final RoomSession? session = state.session;
    if (session == null) {
      return;
    }
    if (climbIds.isEmpty) {
      state = state.copyWith(
        notice: 'Every saved climb is already queued for this room.',
        clearErrorMessage: true,
      );
      return;
    }

    try {
      state = state.copyWith(
        actionInFlight: true,
        clearErrorMessage: true,
        clearNotice: true,
      );
      for (final String climbId in climbIds) {
        await _apiClient.addRoomQueueEntry(
          server: _args.serverUri,
          slug: _args.slug,
          sessionToken: session.token,
          climbId: climbId,
        );
      }
      await refresh(silent: true);
      state = state.copyWith(
        actionInFlight: false,
        notice: 'Imported the saved plan seed into the queue.',
      );
    } on ApiFailure catch (error) {
      state = state.copyWith(
        actionInFlight: false,
        errorMessage: error.message,
      );
      if (error.isAuthFailure) {
        await _handleApiFailure(error);
      }
    }
  }

  Future<void> _mutate({
    required Future<dynamic> Function() action,
    String? notice,
  }) async {
    try {
      state = state.copyWith(
        actionInFlight: true,
        clearErrorMessage: true,
        clearNotice: true,
      );
      await action();
      await refresh(silent: true);
      state = state.copyWith(
        actionInFlight: false,
        notice: notice,
      );
    } on ApiFailure catch (error) {
      state = state.copyWith(
        actionInFlight: false,
        errorMessage: error.message,
      );
      if (error.isAuthFailure) {
        await _handleApiFailure(error);
      }
    }
  }

  Future<void> _handleApiFailure(ApiFailure error) async {
    if (error.isAuthFailure) {
      final String reason = error.code == 'session_expired'
          ? 'session_expired'
          : error.code == 'session_invalid'
              ? 'session_invalid'
              : 'session_required';
      await _sessionRepository.clearSession(
          server: _args.serverUri, slug: _args.slug);
      state = state.copyWith(
        joinReason: reason,
        errorMessage: error.message,
        loading: false,
      );
      return;
    }

    state = state.copyWith(
      errorMessage: error.message,
      loading: false,
      refreshing: false,
    );
  }

  Future<AppPrefs> _loadAppPrefs() async {
    return _appPrefsController.state.valueOrNull ??
        await _sessionRepository.loadAppPrefs();
  }

  String _formatReconnectFailure(ApiFailure error) {
    return switch (error.code) {
      'provider_auth_failed' =>
        'Those provider credentials did not validate on this phone. Check them and try again.',
      'runtime_unavailable' =>
        'This server is reachable, but provider auth cannot be refreshed right now.',
      'rate_limited' =>
        'Too many reconnect attempts were sent. Wait a moment and try again.',
      _ => error.message,
    };
  }

  ({
    String selectedParentSurfaceId,
    String selectedChildSurfaceId,
    int selectedAngle
  }) _resolveSurfaceDraft(RoomSnapshot room, AppPrefs prefs) {
    if (room.providerId == 'kilter') {
      final String boardId =
          (room.surface?.meta['board_id'] ?? '').trim().isNotEmpty
              ? room.surface!.meta['board_id']!.trim()
              : (room.surface?.id ?? '').trim().isNotEmpty
                  ? room.surface!.id
                  : prefs.lastKilterBoardId;
      final int angle = int.tryParse(room.surface?.meta['angle'] ?? '') ??
          prefs.lastKilterAngle;
      return (
        selectedParentSurfaceId: boardId,
        selectedChildSurfaceId: '',
        selectedAngle: angle,
      );
    }

    final String parentId =
        (room.surface?.meta['gym_slug'] ?? '').trim().isNotEmpty
            ? room.surface!.meta['gym_slug']!.trim()
            : (room.surface?.parentId ?? '').trim().isNotEmpty
                ? room.surface!.parentId!.trim()
                : prefs.lastCruxGymSlug;
    final String childId = (room.surface?.id ?? '').trim().isNotEmpty
        ? room.surface!.id
        : prefs.lastCruxWallId;
    return (
      selectedParentSurfaceId: parentId,
      selectedChildSurfaceId: childId,
      selectedAngle: state.selectedAngle,
    );
  }

  Future<void> _rememberSnapshotContext(RoomSnapshot room) async {
    await _appPrefsController.rememberRoomVisit(
      server: _args.serverUri,
      room: room,
    );
    await _appPrefsController.rememberLastProvider(room.providerId);

    if (room.providerId == 'kilter') {
      final String boardId =
          (room.surface?.meta['board_id'] ?? '').trim().isNotEmpty
              ? room.surface!.meta['board_id']!.trim()
              : (room.surface?.id ?? '').trim().isNotEmpty
                  ? room.surface!.id
                  : '';
      final int angle =
          int.tryParse(room.surface?.meta['angle'] ?? '') ?? defaultBoardAngle;
      if (boardId.isNotEmpty) {
        await _appPrefsController.rememberLastKilterSurface(
          boardId: boardId,
          angle: angle,
        );
      }
      return;
    }

    final String gymSlug =
        (room.surface?.meta['gym_slug'] ?? '').trim().isNotEmpty
            ? room.surface!.meta['gym_slug']!.trim()
            : (room.surface?.parentId ?? '').trim().isNotEmpty
                ? room.surface!.parentId!.trim()
                : '';
    final String wallId = (room.surface?.id ?? '').trim();
    if (gymSlug.isNotEmpty || wallId.isNotEmpty) {
      await _appPrefsController.rememberLastCruxSurface(
        gymSlug: gymSlug,
        wallId: wallId,
      );
    }
  }

  Future<void> _attachEvents(String sessionToken) async {
    await _subscription?.cancel();
    if (_disposed) return;
    String? ticket;
    try {
      final result = await _apiClient.getSSETicket(
        server: _args.serverUri,
        slug: _args.slug,
        sessionToken: sessionToken,
      );
      ticket = result.ticket;
    } catch (_) {} // fallback to bearer
    _subscription = _sseClient
        .connect(
      uri: _apiClient.getRoomEventsUri(server: _args.serverUri, slug: _args.slug),
      ticket: ticket,
      sessionToken: ticket == null || ticket.isEmpty ? sessionToken : null,
    )
        .listen((SseMessage msg) {
      _onSSEEvent(msg);
    }, onError: (_) {
      _scheduleRefresh();
    });
  }

  void _onSSEEvent(SseMessage msg) {
    try {
      final Map<String, dynamic> payload = jsonDecode(msg.data) as Map<String, dynamic>;
      final int eventVersion = (payload['version'] as num?)?.toInt() ?? 0;
      final int localVersion = state.room?.version ?? 0;
      if (eventVersion > 0 && localVersion >= eventVersion) return;
    } catch (_) {} // non-json or missing version — still refresh
    _scheduleRefresh();
  }

  void _scheduleRefresh() {
    _debounceTimer?.cancel();
    _debounceTimer = Timer(const Duration(milliseconds: 200), () {
      if (_refreshInFlight || _disposed) return;
      _refreshInFlight = true;
      refresh(silent: true).whenComplete(() {
        _refreshInFlight = false;
      });
    });
  }

  Future<void> autoRefillQueue() async {
    final RoomSnapshot? room = state.room;
    final RoomSession? session = state.session;
    if (room == null || session == null) return;
    final Set<String> existingIds = <String>{
      ...room.queue.map((QueueEntry e) => e.climb.id),
      ...room.finalists.map((FinalistEntry e) => e.climb.id),
    };
    final List<MapEntry<String, int>> sorted = room.voteCounts.entries
        .where((MapEntry<String, int> e) => e.value > 0 && !existingIds.contains(e.key))
        .toList(growable: false)
      ..sort((MapEntry<String, int> a, MapEntry<String, int> b) => b.value.compareTo(a.value));
    final List<String> topIds = sorted.take(5).map((MapEntry<String, int> e) => e.key).toList(growable: false);
    if (topIds.isEmpty) {
      state = state.copyWith(notice: 'No voted climbs available to refill the queue.');
      return;
    }
    try {
      state = state.copyWith(actionInFlight: true, clearErrorMessage: true, clearNotice: true);
      for (final String climbId in topIds) {
        await _apiClient.addRoomQueueEntry(
          server: _args.serverUri,
          slug: _args.slug,
          sessionToken: session.token,
          climbId: climbId,
        );
      }
      await refresh(silent: true);
      state = state.copyWith(actionInFlight: false, notice: 'Added ${topIds.length} top-voted climbs to the queue.');
    } on ApiFailure catch (error) {
      state = state.copyWith(actionInFlight: false, errorMessage: error.message);
      if (error.isAuthFailure) {
        await _handleApiFailure(error);
      }
    }
  }

  Future<void> _checkSessionRefresh() async {
    final RoomSession? session = state.session;
    if (session == null || _disposed) return;
    final Duration remaining = session.expiresAt.difference(DateTime.now().toUtc());
    if (remaining > const Duration(hours: 24)) return;
    try {
      final RoomSession refreshed = await _apiClient.refreshSession(
        server: _args.serverUri,
        slug: _args.slug,
        sessionToken: session.token,
      );
      await _sessionRepository.saveSession(
        server: _args.serverUri,
        slug: _args.slug,
        session: refreshed,
      );
      state = state.copyWith(session: refreshed);
      await _proactiveTokenRefresh();
    } on ApiFailure catch (error) {
      if (error.isAuthFailure) {
        await _handleApiFailure(error);
      }
    }
  }

  Future<void> _checkClimbChangeNotification(RoomSnapshot room) async {
    final String? currentClimbId = room.currentClimb?.id;
    if (currentClimbId == null || currentClimbId == _lastCurrentClimbId) {
      _lastCurrentClimbId = currentClimbId;
      return;
    }
    final String? previousId = _lastCurrentClimbId;
    _lastCurrentClimbId = currentClimbId;
    if (previousId == null) return; // first load, skip
    final AppPrefs prefs = await _loadAppPrefs();
    if (!prefs.settings.notifyOnClimbChange) return;
    if (WidgetsBinding.instance.lifecycleState == AppLifecycleState.resumed) return;
    const AndroidNotificationDetails android = AndroidNotificationDetails(
      'climb_change', 'Climb change',
      channelDescription: 'Notifies when the room moves to a new climb',
      importance: Importance.defaultImportance,
      priority: Priority.defaultPriority,
    );
    const DarwinNotificationDetails ios = DarwinNotificationDetails();
    const NotificationDetails details = NotificationDetails(android: android, iOS: ios);
    await _notifications.show(0, 'New climb', room.currentClimb?.name ?? 'Current climb changed', details);
  }

  Future<void> _proactiveTokenRefresh() async {
    final RoomSnapshot? room = state.room;
    if (room == null || _disposed) return;
    final String? expiresAtRaw = room.connection.metadata['token_expires_at'];
    if (expiresAtRaw == null || expiresAtRaw.isEmpty) return;
    final DateTime? expiresAt = DateTime.tryParse(expiresAtRaw);
    if (expiresAt == null) return;
    final Duration remaining = expiresAt.difference(DateTime.now().toUtc());
    if (remaining > const Duration(minutes: 30)) return;
    try {
      final Map<String, String> secret = await _providerSecretRepository.readSecret(
        server: _args.serverUri,
        providerId: room.providerId,
      );
      if (secret.isEmpty) {
        state = state.copyWith(notice: 'Provider token expiring soon. Re-enter credentials to keep the session alive.');
        return;
      }
      await reconnectProvider(secret);
    } catch (_) {
      state = state.copyWith(notice: 'Provider token expiring soon. Re-enter credentials to keep the session alive.');
    }
  }
}
