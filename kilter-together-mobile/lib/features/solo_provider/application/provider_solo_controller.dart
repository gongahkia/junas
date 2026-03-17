import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/models/app_prefs_models.dart';
import '../../../core/models/board_models.dart';
import '../../../core/models/product_models.dart';
import '../../../core/models/provider_models.dart';
import '../../../core/models/session_models.dart';
import '../../../core/network/api_client.dart';
import '../../../core/storage/app_prefs_controller.dart';
import '../../../core/storage/session_repository.dart';

class ProviderSoloRouteArgs {
  const ProviderSoloRouteArgs({
    required this.providerId,
    this.initialServer,
    this.initialParentSurfaceId,
    this.initialChildSurfaceId,
    this.initialQuery,
    this.initialSort,
    this.initialClimbId,
  });

  final String providerId;
  final String? initialServer;
  final String? initialParentSurfaceId;
  final String? initialChildSurfaceId;
  final String? initialQuery;
  final String? initialSort;
  final String? initialClimbId;

  @override
  bool operator ==(Object other) {
    return other is ProviderSoloRouteArgs &&
        other.providerId == providerId &&
        other.initialServer == initialServer &&
        other.initialParentSurfaceId == initialParentSurfaceId &&
        other.initialChildSurfaceId == initialChildSurfaceId &&
        other.initialQuery == initialQuery &&
        other.initialSort == initialSort &&
        other.initialClimbId == initialClimbId;
  }

  @override
  int get hashCode => Object.hash(
        providerId,
        initialServer,
        initialParentSurfaceId,
        initialChildSurfaceId,
        initialQuery,
        initialSort,
        initialClimbId,
      );
}

class ProviderSoloViewState {
  const ProviderSoloViewState({
    required this.providerId,
    required this.sort,
    this.server,
    this.capability,
    this.parentSurfaces = const <ProviderSurface>[],
    this.childSurfaces = const <ProviderSurface>[],
    this.climbs = const <ProviderClimb>[],
    this.plannedClimbs = const <ProviderClimb>[],
    this.selectedClimb,
    this.selectedParentSurfaceId = '',
    this.selectedChildSurfaceId = '',
    this.query = '',
    this.gradeMin = '',
    this.gradeMax = '',
    this.currentPage = 1,
    this.hasNextPage = false,
    this.accessLoaded = false,
    this.loading = true,
    this.surfacesLoading = false,
    this.catalogLoading = false,
    this.detailLoading = false,
    this.actionInFlight = false,
    this.errorMessage,
    this.notice,
    this.selectedClimbIds = const <String>{},
  });

  final String providerId;
  final Uri? server;
  final ProviderCapability? capability;
  final List<ProviderSurface> parentSurfaces;
  final List<ProviderSurface> childSurfaces;
  final List<ProviderClimb> climbs;
  final List<ProviderClimb> plannedClimbs;
  final ProviderClimb? selectedClimb;
  final String selectedParentSurfaceId;
  final String selectedChildSurfaceId;
  final String query;
  final String gradeMin;
  final String gradeMax;
  final String sort;
  final int currentPage;
  final bool hasNextPage;
  final bool accessLoaded;
  final bool loading;
  final bool surfacesLoading;
  final bool catalogLoading;
  final bool detailLoading;
  final bool actionInFlight;
  final String? errorMessage;
  final String? notice;
  final Set<String> selectedClimbIds;

  ProviderSurface? get selectedParentSurface {
    for (final ProviderSurface item in parentSurfaces) {
      if (item.id == selectedParentSurfaceId) {
        return item;
      }
    }
    return null;
  }

  ProviderSurface? get selectedChildSurface {
    for (final ProviderSurface item in childSurfaces) {
      if (item.id == selectedChildSurfaceId) {
        return item;
      }
    }
    return null;
  }

  ProviderSurface? get activeSurface =>
      selectedChildSurface ?? selectedParentSurface;

  bool get missingServer => server == null;
  bool get supportsNestedSurfaces => capability?.surfaceHierarchy != 'board';

  ProviderSoloViewState copyWith({
    Uri? server,
    ProviderCapability? capability,
    bool clearCapability = false,
    List<ProviderSurface>? parentSurfaces,
    List<ProviderSurface>? childSurfaces,
    List<ProviderClimb>? climbs,
    List<ProviderClimb>? plannedClimbs,
    ProviderClimb? selectedClimb,
    bool clearSelectedClimb = false,
    String? selectedParentSurfaceId,
    String? selectedChildSurfaceId,
    String? query,
    String? gradeMin,
    String? gradeMax,
    String? sort,
    int? currentPage,
    bool? hasNextPage,
    bool? accessLoaded,
    bool? loading,
    bool? surfacesLoading,
    bool? catalogLoading,
    bool? detailLoading,
    bool? actionInFlight,
    String? errorMessage,
    bool clearErrorMessage = false,
    String? notice,
    bool clearNotice = false,
    Set<String>? selectedClimbIds,
  }) {
    return ProviderSoloViewState(
      providerId: providerId,
      server: server ?? this.server,
      capability: clearCapability ? null : (capability ?? this.capability),
      parentSurfaces: parentSurfaces ?? this.parentSurfaces,
      childSurfaces: childSurfaces ?? this.childSurfaces,
      climbs: climbs ?? this.climbs,
      plannedClimbs: plannedClimbs ?? this.plannedClimbs,
      selectedClimb:
          clearSelectedClimb ? null : (selectedClimb ?? this.selectedClimb),
      selectedParentSurfaceId:
          selectedParentSurfaceId ?? this.selectedParentSurfaceId,
      selectedChildSurfaceId:
          selectedChildSurfaceId ?? this.selectedChildSurfaceId,
      query: query ?? this.query,
      gradeMin: gradeMin ?? this.gradeMin,
      gradeMax: gradeMax ?? this.gradeMax,
      sort: sort ?? this.sort,
      currentPage: currentPage ?? this.currentPage,
      hasNextPage: hasNextPage ?? this.hasNextPage,
      accessLoaded: accessLoaded ?? this.accessLoaded,
      loading: loading ?? this.loading,
      surfacesLoading: surfacesLoading ?? this.surfacesLoading,
      catalogLoading: catalogLoading ?? this.catalogLoading,
      detailLoading: detailLoading ?? this.detailLoading,
      actionInFlight: actionInFlight ?? this.actionInFlight,
      errorMessage:
          clearErrorMessage ? null : (errorMessage ?? this.errorMessage),
      notice: clearNotice ? null : (notice ?? this.notice),
      selectedClimbIds: selectedClimbIds ?? this.selectedClimbIds,
    );
  }
}

final providerSoloControllerProvider = StateNotifierProvider.autoDispose.family<
    ProviderSoloController, ProviderSoloViewState, ProviderSoloRouteArgs>(
  (Ref ref, ProviderSoloRouteArgs args) {
    return ProviderSoloController(
      args: args,
      apiClient: ref.read(apiClientProvider),
      appPrefsController: ref.read(appPrefsControllerProvider.notifier),
      sessionRepository: ref.read(sessionRepositoryProvider),
    );
  },
);

class ProviderSoloController extends StateNotifier<ProviderSoloViewState> {
  ProviderSoloController({
    required ProviderSoloRouteArgs args,
    required ApiClient apiClient,
    required AppPrefsController appPrefsController,
    required SessionRepository sessionRepository,
  })  : _args = args,
        _apiClient = apiClient,
        _appPrefsController = appPrefsController,
        _sessionRepository = sessionRepository,
        super(
          ProviderSoloViewState(
            providerId: args.providerId,
            sort: args.initialSort ?? defaultClimbSort,
            query: args.initialQuery ?? '',
            selectedParentSurfaceId: args.initialParentSurfaceId ?? '',
            selectedChildSurfaceId: args.initialChildSurfaceId ?? '',
          ),
        ) {
    _cursors[1] = null;
    unawaited(load());
  }

  final ProviderSoloRouteArgs _args;
  final ApiClient _apiClient;
  final AppPrefsController _appPrefsController;
  final SessionRepository _sessionRepository;
  final Map<int, String?> _cursors = <int, String?>{};

  Map<String, String> _secret = const <String, String>{};

  Future<void> load() async {
    state = state.copyWith(
      loading: true,
      clearErrorMessage: true,
      clearNotice: true,
    );

    final Uri? server = await _resolveServer();
    if (server == null) {
      state = state.copyWith(
        loading: false,
        errorMessage:
            'Choose or join a self-hosted server before opening provider solo browse.',
      );
      return;
    }

    try {
      final List<ProviderCapability> capabilities =
          await _apiClient.getProviderCapabilities(server);
      final ProviderCapability? capability =
          capabilities.cast<ProviderCapability?>().firstWhere(
                (ProviderCapability? item) =>
                    item?.id == _args.providerId &&
                    item!.soloSupported &&
                    item.surfaceHierarchy != 'board',
                orElse: () => null,
              );
      if (capability == null) {
        state = state.copyWith(
          server: server,
          loading: false,
          errorMessage:
              '${_args.providerId} does not expose provider-backed solo browse on this server.',
        );
        return;
      }

      state = state.copyWith(
        server: server,
        capability: capability,
        loading: false,
        clearErrorMessage: true,
      );
    } on ApiFailure catch (error) {
      state = state.copyWith(
        server: server,
        loading: false,
        errorMessage: error.message,
      );
    }
  }

  Future<void> unlockCatalog(Map<String, String> secret) async {
    final Uri? server = state.server;
    final ProviderCapability? capability = state.capability;
    if (server == null || capability == null) {
      return;
    }

    state = state.copyWith(
      surfacesLoading: true,
      clearErrorMessage: true,
      clearNotice: true,
    );

    try {
      final List<ProviderSurface> parentSurfaces =
          await _apiClient.getSoloProviderSurfaces(
        server: server,
        providerId: state.providerId,
        secret: secret,
      );
      _secret = Map<String, String>.from(secret);

      final AppPrefs prefs = await _sessionRepository.loadAppPrefs();
      final String preferredParentId =
          _args.initialParentSurfaceId?.trim().isNotEmpty == true
              ? _args.initialParentSurfaceId!.trim()
              : state.providerId == 'crux'
                  ? prefs.lastCruxGymSlug
                  : '';
      final ProviderSurface? selectedParent = parentSurfaces
          .cast<ProviderSurface?>()
          .firstWhere(
            (ProviderSurface? item) => item?.id == preferredParentId,
            orElse: () => parentSurfaces.isEmpty ? null : parentSurfaces.first,
          );

      state = state.copyWith(
        parentSurfaces: parentSurfaces,
        childSurfaces: const <ProviderSurface>[],
        selectedParentSurfaceId: selectedParent?.id ?? '',
        selectedChildSurfaceId: '',
        accessLoaded: true,
        surfacesLoading: false,
      );
      await _appPrefsController.rememberLastProvider(state.providerId);

      if (selectedParent != null) {
        await loadChildSurfaces(selectedParent.id);
      } else {
        await loadCatalog(page: 1);
      }
    } on ApiFailure catch (error) {
      state = state.copyWith(
        accessLoaded: false,
        surfacesLoading: false,
        parentSurfaces: const <ProviderSurface>[],
        childSurfaces: const <ProviderSurface>[],
        climbs: const <ProviderClimb>[],
        clearSelectedClimb: true,
        errorMessage: error.message,
      );
    }
  }

  Future<void> loadChildSurfaces(String parentSurfaceId) async {
    final Uri? server = state.server;
    if (server == null || _secret.isEmpty) {
      return;
    }

    state = state.copyWith(
      surfacesLoading: true,
      selectedParentSurfaceId: parentSurfaceId,
      selectedChildSurfaceId: '',
      clearErrorMessage: true,
      clearNotice: true,
    );

    try {
      final List<ProviderSurface> childSurfaces =
          await _apiClient.getSoloProviderSurfaces(
        server: server,
        providerId: state.providerId,
        secret: _secret,
        parentId: parentSurfaceId,
      );
      final String preferredChildId =
          _args.initialChildSurfaceId?.trim().isNotEmpty == true
              ? _args.initialChildSurfaceId!.trim()
              : '';
      final ProviderSurface? selectedChild = childSurfaces
          .cast<ProviderSurface?>()
          .firstWhere(
            (ProviderSurface? item) => item?.id == preferredChildId,
            orElse: () => childSurfaces.isEmpty ? null : childSurfaces.first,
          );

      state = state.copyWith(
        childSurfaces: childSurfaces,
        selectedChildSurfaceId: selectedChild?.id ?? '',
        surfacesLoading: false,
      );
      await _rememberSurfaceSelection();
      await loadCatalog(page: 1);
    } on ApiFailure catch (error) {
      state = state.copyWith(
        childSurfaces: const <ProviderSurface>[],
        selectedChildSurfaceId: '',
        surfacesLoading: false,
        errorMessage: error.message,
      );
    }
  }

  Future<void> selectChildSurface(String? childSurfaceId) async {
    state = state.copyWith(
      selectedChildSurfaceId: childSurfaceId ?? '',
      clearErrorMessage: true,
    );
    await _rememberSurfaceSelection();
    await loadCatalog(page: 1);
  }

  Future<void> updateSearch({
    String? query,
    String? sort,
    String? gradeMin,
    String? gradeMax,
  }) async {
    state = state.copyWith(
      query: query ?? state.query,
      sort: sort ?? state.sort,
      gradeMin: gradeMin ?? state.gradeMin,
      gradeMax: gradeMax ?? state.gradeMax,
      currentPage: 1,
      clearErrorMessage: true,
      clearNotice: true,
    );
    _cursors
      ..clear()
      ..[1] = null;
    await loadCatalog(page: 1);
  }

  Future<void> nextPage() async {
    if (!state.hasNextPage || !_cursors.containsKey(state.currentPage + 1)) {
      return;
    }
    await loadCatalog(page: state.currentPage + 1);
  }

  Future<void> previousPage() async {
    if (state.currentPage <= 1) {
      return;
    }
    await loadCatalog(page: state.currentPage - 1);
  }

  Future<void> loadCatalog({
    required int page,
  }) async {
    final Uri? server = state.server;
    if (server == null ||
        _secret.isEmpty ||
        state.selectedParentSurfaceId.isEmpty) {
      return;
    }

    state = state.copyWith(
      catalogLoading: true,
      currentPage: page,
      clearErrorMessage: true,
      clearNotice: true,
    );

    try {
      final ProviderCatalogClimbsResponse response =
          await _apiClient.getSoloProviderClimbs(
        server: server,
        providerId: state.providerId,
        secret: _secret,
        surfaceId: state.selectedChildSurfaceId.isNotEmpty
            ? state.selectedChildSurfaceId
            : state.selectedParentSurfaceId,
        context: _requestContext(),
        q: state.query.trim().isEmpty ? null : state.query.trim(),
        sort: state.sort,
        cursor: _cursors[page],
        gradeMin: state.gradeMin.trim().isEmpty ? null : state.gradeMin.trim(),
        gradeMax: state.gradeMax.trim().isEmpty ? null : state.gradeMax.trim(),
        pageSize: 10,
      );
      _cursors[page + 1] = response.nextCursor;

      ProviderClimb? selectedClimb;
      final String preferredClimbId =
          state.selectedClimb?.id ?? _args.initialClimbId ?? '';
      if (preferredClimbId.isNotEmpty) {
        selectedClimb = response.climbs.cast<ProviderClimb?>().firstWhere(
              (ProviderClimb? item) => item?.id == preferredClimbId,
              orElse: () => null,
            );
      }
      selectedClimb ??= response.climbs.isEmpty ? null : response.climbs.first;

      state = state.copyWith(
        climbs: response.climbs,
        selectedClimb: selectedClimb,
        clearSelectedClimb: selectedClimb == null,
        currentPage: page,
        hasNextPage: response.hasMore,
        catalogLoading: false,
      );

      if (selectedClimb != null) {
        await selectClimb(selectedClimb.id);
      }
    } on ApiFailure catch (error) {
      state = state.copyWith(
        catalogLoading: false,
        errorMessage: error.message,
      );
    }
  }

  Future<void> selectClimb(String climbId) async {
    final Uri? server = state.server;
    if (server == null ||
        _secret.isEmpty ||
        state.selectedParentSurfaceId.isEmpty) {
      return;
    }

    final ProviderClimb? catalogClimb =
        state.climbs.cast<ProviderClimb?>().firstWhere(
              (ProviderClimb? item) => item?.id == climbId,
              orElse: () => null,
            );
    if (catalogClimb != null) {
      state =
          state.copyWith(selectedClimb: catalogClimb, clearErrorMessage: true);
    }

    try {
      state = state.copyWith(detailLoading: true, clearErrorMessage: true);
      final ProviderCatalogClimbResponse response =
          await _apiClient.getSoloProviderClimb(
        server: server,
        providerId: state.providerId,
        climbId: climbId,
        secret: _secret,
        surfaceId: state.selectedChildSurfaceId.isNotEmpty
            ? state.selectedChildSurfaceId
            : state.selectedParentSurfaceId,
        context: _requestContext(),
      );
      final ProviderClimb detail = response.climb;
      state = state.copyWith(
        detailLoading: false,
        selectedClimb: detail,
        plannedClimbs: state.plannedClimbs
            .map((ProviderClimb item) =>
                item.id == detail.id ? _mergeClimb(item, detail) : item)
            .toList(growable: false),
      );
    } on ApiFailure catch (error) {
      state = state.copyWith(
        detailLoading: false,
        errorMessage: error.message,
      );
    }
  }

  void togglePlannedClimb(ProviderClimb climb) {
    final bool exists =
        state.plannedClimbs.any((ProviderClimb item) => item.id == climb.id);
    final List<ProviderClimb> planned = exists
        ? state.plannedClimbs
            .where((ProviderClimb item) => item.id != climb.id)
            .toList(growable: false)
        : <ProviderClimb>[
            _mergeClimb(
              climb,
              ProviderClimb(
                id: climb.id,
                externalId: climb.externalId,
                providerId: climb.providerId,
                surfaceId: climb.surfaceId,
                name: climb.name,
                setterName: climb.setterName,
                description: climb.description,
                primaryGrade: climb.primaryGrade,
                secondaryGrade: climb.secondaryGrade,
                createdAt: climb.createdAt,
                popularity: climb.popularity,
                media: climb.media,
                highlightedHolds: climb.highlightedHolds,
                meta: <String, String>{
                  ...climb.meta,
                  ..._requestContext(),
                },
              ),
            ),
            ...state.plannedClimbs,
          ];
    state = state.copyWith(plannedClimbs: planned, clearErrorMessage: true);
  }

  Future<SoloPlanSnapshot?> createPlan({
    required String title,
    String? notes,
    String? createdBy,
  }) async {
    final Uri? server = state.server;
    final ProviderSurface? surface = state.activeSurface;
    if (server == null || surface == null || state.plannedClimbs.isEmpty) {
      state = state.copyWith(
        errorMessage:
            'Pick a provider surface and add at least one climb before sharing a plan.',
      );
      return null;
    }

    try {
      state = state.copyWith(
        actionInFlight: true,
        clearErrorMessage: true,
        clearNotice: true,
      );
      final SoloPlanSnapshot plan = await _apiClient.createSoloPlan(
        server: server,
        providerId: state.providerId,
        title: title.trim().isEmpty ? '${surface.name} plan' : title.trim(),
        notes: notes?.trim().isEmpty == true ? null : notes?.trim(),
        surface: surface,
        context: _requestContext(),
        filters: <String, String>{
          'q': state.query,
          'sort': state.sort,
          if (state.selectedParentSurfaceId.isNotEmpty)
            'gym': state.selectedParentSurfaceId,
          if (state.selectedChildSurfaceId.isNotEmpty)
            'wall': state.selectedChildSurfaceId,
        },
        climbs: state.plannedClimbs,
        openPath: buildOpenPath(),
        createdBy: createdBy?.trim().isEmpty == true ? null : createdBy?.trim(),
      );
      state = state.copyWith(
        actionInFlight: false,
        notice: 'Shared provider plan created.',
      );
      return plan;
    } on ApiFailure catch (error) {
      state = state.copyWith(
        actionInFlight: false,
        errorMessage: error.message,
      );
      return null;
    }
  }

  Future<void> beginRoomSeed({String? title}) async {
    final ProviderSurface? surface = state.activeSurface;
    if (surface == null) {
      state = state.copyWith(
        errorMessage: 'Choose a provider surface before seeding a room.',
      );
      return;
    }

    await _appPrefsController.setPendingRoomSeed(
      PendingRoomSeed(
        providerId: state.providerId,
        title: title?.trim().isEmpty == true ? null : title?.trim(),
        surface: surface,
        climbs: state.plannedClimbs,
        openPath: buildOpenPath(),
        createdAt: DateTime.now().toUtc().toIso8601String(),
      ),
    );
    await _appPrefsController.rememberLastProvider(state.providerId);
    await _rememberSurfaceSelection();
    state = state.copyWith(
      notice: state.plannedClimbs.isEmpty
          ? 'Saved the provider surface for room creation.'
          : 'Saved the provider shortlist for room creation.',
      clearErrorMessage: true,
    );
  }

  void toggleMultiSelect(String id) {
    final Set<String> next = Set<String>.from(state.selectedClimbIds);
    if (next.contains(id)) {
      next.remove(id);
    } else {
      next.add(id);
    }
    state = state.copyWith(selectedClimbIds: next);
  }

  void clearMultiSelect() {
    state = state.copyWith(selectedClimbIds: const <String>{});
  }

  void addSelectedToPlannedClimbs() {
    final int count = state.selectedClimbIds.length;
    final List<ProviderClimb> planned = List<ProviderClimb>.from(state.plannedClimbs);
    for (final String climbId in state.selectedClimbIds) {
      if (planned.any((ProviderClimb item) => item.id == climbId)) {
        continue; // already planned
      }
      final ProviderClimb? climb =
          state.climbs.cast<ProviderClimb?>().firstWhere(
                (ProviderClimb? item) => item?.id == climbId,
                orElse: () => null,
              );
      if (climb == null) {
        continue;
      }
      planned.insert(0, climb);
    }
    state = state.copyWith(
      plannedClimbs: planned,
      selectedClimbIds: const <String>{},
      notice: '$count climbs added to shortlist.',
      clearErrorMessage: true,
    );
  }

  String buildOpenPath() {
    final Map<String, String> queryParameters = <String, String>{
      if (state.server != null) 'server': state.server!.toString(),
      if (state.selectedParentSurfaceId.isNotEmpty)
        'gym': state.selectedParentSurfaceId,
      if (state.selectedChildSurfaceId.isNotEmpty)
        'wall': state.selectedChildSurfaceId,
      if (state.query.trim().isNotEmpty) 'q': state.query.trim(),
      'sort': state.sort,
      if (state.selectedClimb != null) 'climb': state.selectedClimb!.id,
    };
    return Uri(
      path: '/solo/providers/${Uri.encodeComponent(state.providerId)}',
      queryParameters: queryParameters,
    ).toString();
  }

  Future<Uri?> _resolveServer() async {
    if (_args.initialServer != null && _args.initialServer!.trim().isNotEmpty) {
      return normalizeServerUri(_args.initialServer!);
    }
    return _sessionRepository.loadActiveServer();
  }

  Future<void> _rememberSurfaceSelection() async {
    if (state.providerId == 'crux' &&
        state.selectedParentSurfaceId.isNotEmpty) {
      await _appPrefsController.rememberLastCruxSurface(
        gymSlug: state.selectedParentSurfaceId,
        wallId: state.selectedChildSurfaceId,
      );
    }
  }

  Map<String, String> _requestContext() {
    return <String, String>{
      if (state.selectedParentSurfaceId.isNotEmpty)
        'gym_slug': state.selectedParentSurfaceId,
      if (state.selectedChildSurfaceId.isNotEmpty)
        'wall_id': state.selectedChildSurfaceId,
    };
  }

  ProviderClimb _mergeClimb(ProviderClimb base, ProviderClimb detail) {
    return ProviderClimb(
      id: detail.id,
      externalId: detail.externalId,
      providerId: detail.providerId,
      surfaceId: detail.surfaceId,
      name: detail.name,
      description: detail.description ?? base.description,
      setterName: detail.setterName ?? base.setterName,
      primaryGrade: detail.primaryGrade ?? base.primaryGrade,
      secondaryGrade: detail.secondaryGrade ?? base.secondaryGrade,
      createdAt: detail.createdAt ?? base.createdAt,
      popularity: detail.popularity ?? base.popularity,
      media: detail.media.isNotEmpty ? detail.media : base.media,
      highlightedHolds: detail.highlightedHolds.isNotEmpty
          ? detail.highlightedHolds
          : base.highlightedHolds,
      meta: <String, String>{
        ...base.meta,
        ...detail.meta,
      },
    );
  }
}
