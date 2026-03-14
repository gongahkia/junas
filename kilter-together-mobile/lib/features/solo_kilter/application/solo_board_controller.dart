import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/models/app_prefs_models.dart';
import '../../../core/models/board_models.dart';
import '../../../core/models/catalog_models.dart';
import '../../../core/models/product_models.dart';
import '../../../core/models/provider_models.dart';
import '../../../core/models/session_models.dart';
import '../../../core/network/api_client.dart';
import '../../../core/storage/app_prefs_controller.dart';
import '../../../core/storage/offline_kilter_catalog_repository.dart';
import '../../../core/storage/session_repository.dart';

class SoloBoardRouteArgs {
  const SoloBoardRouteArgs({
    required this.boardId,
    this.initialServer,
    this.initialAngle,
    this.initialSort,
    this.initialQuery,
    this.initialSetter,
    this.initialGrade,
    this.initialClimbUuid,
  });

  final String boardId;
  final String? initialServer;
  final int? initialAngle;
  final String? initialSort;
  final String? initialQuery;
  final String? initialSetter;
  final String? initialGrade;
  final String? initialClimbUuid;

  @override
  bool operator ==(Object other) {
    return other is SoloBoardRouteArgs &&
        other.boardId == boardId &&
        other.initialServer == initialServer &&
        other.initialAngle == initialAngle &&
        other.initialSort == initialSort &&
        other.initialQuery == initialQuery &&
        other.initialSetter == initialSetter &&
        other.initialGrade == initialGrade &&
        other.initialClimbUuid == initialClimbUuid;
  }

  @override
  int get hashCode => Object.hash(
        boardId,
        initialServer,
        initialAngle,
        initialSort,
        initialQuery,
        initialSetter,
        initialGrade,
        initialClimbUuid,
      );
}

class SoloBoardViewState {
  const SoloBoardViewState({
    required this.boardId,
    required this.angle,
    required this.sort,
    this.server,
    this.boards = const <BoardOption>[],
    this.board,
    this.climbs = const <BoardClimb>[],
    this.selectedClimb,
    this.query = '',
    this.setter = '',
    this.grade = '',
    this.currentPage = 1,
    this.hasNextPage = false,
    this.loading = true,
    this.pageLoading = false,
    this.actionInFlight = false,
    this.errorMessage,
    this.notice,
  });

  final Uri? server;
  final String boardId;
  final List<BoardOption> boards;
  final BoardOption? board;
  final List<BoardClimb> climbs;
  final BoardClimb? selectedClimb;
  final int angle;
  final String sort;
  final String query;
  final String setter;
  final String grade;
  final int currentPage;
  final bool hasNextPage;
  final bool loading;
  final bool pageLoading;
  final bool actionInFlight;
  final String? errorMessage;
  final String? notice;

  bool get missingServer => server == null;

  SoloBoardViewState copyWith({
    Uri? server,
    List<BoardOption>? boards,
    BoardOption? board,
    bool clearBoard = false,
    List<BoardClimb>? climbs,
    BoardClimb? selectedClimb,
    bool clearSelectedClimb = false,
    int? angle,
    String? sort,
    String? query,
    String? setter,
    String? grade,
    int? currentPage,
    bool? hasNextPage,
    bool? loading,
    bool? pageLoading,
    bool? actionInFlight,
    String? errorMessage,
    bool clearErrorMessage = false,
    String? notice,
    bool clearNotice = false,
  }) {
    return SoloBoardViewState(
      server: server ?? this.server,
      boardId: boardId,
      boards: boards ?? this.boards,
      board: clearBoard ? null : (board ?? this.board),
      climbs: climbs ?? this.climbs,
      selectedClimb:
          clearSelectedClimb ? null : (selectedClimb ?? this.selectedClimb),
      angle: angle ?? this.angle,
      sort: sort ?? this.sort,
      query: query ?? this.query,
      setter: setter ?? this.setter,
      grade: grade ?? this.grade,
      currentPage: currentPage ?? this.currentPage,
      hasNextPage: hasNextPage ?? this.hasNextPage,
      loading: loading ?? this.loading,
      pageLoading: pageLoading ?? this.pageLoading,
      actionInFlight: actionInFlight ?? this.actionInFlight,
      errorMessage:
          clearErrorMessage ? null : (errorMessage ?? this.errorMessage),
      notice: clearNotice ? null : (notice ?? this.notice),
    );
  }
}

final soloBoardControllerProvider = StateNotifierProvider.autoDispose
    .family<SoloBoardController, SoloBoardViewState, SoloBoardRouteArgs>(
  (Ref ref, SoloBoardRouteArgs args) {
    return SoloBoardController(
      args: args,
      apiClient: ref.read(apiClientProvider),
      appPrefsController: ref.read(appPrefsControllerProvider.notifier),
      catalogRepository: ref.read(offlineKilterCatalogRepositoryProvider),
      sessionRepository: ref.read(sessionRepositoryProvider),
    );
  },
);

class SoloBoardController extends StateNotifier<SoloBoardViewState> {
  SoloBoardController({
    required SoloBoardRouteArgs args,
    required ApiClient apiClient,
    required AppPrefsController appPrefsController,
    required OfflineKilterCatalogRepository catalogRepository,
    required SessionRepository sessionRepository,
  })  : _args = args,
        _apiClient = apiClient,
        _appPrefsController = appPrefsController,
        _catalogRepository = catalogRepository,
        _sessionRepository = sessionRepository,
        super(
          SoloBoardViewState(
            boardId: args.boardId,
            angle: args.initialAngle ?? defaultBoardAngle,
            sort: args.initialSort ?? defaultClimbSort,
            query: args.initialQuery ?? '',
            setter: args.initialSetter ?? '',
            grade: args.initialGrade ?? '',
          ),
        ) {
    unawaited(load());
  }

  final SoloBoardRouteArgs _args;
  final ApiClient _apiClient;
  final AppPrefsController _appPrefsController;
  final OfflineKilterCatalogRepository _catalogRepository;
  final SessionRepository _sessionRepository;

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
            'Choose or join a self-hosted server before opening solo browse.',
      );
      return;
    }

    try {
      final CatalogStatus status = await _catalogRepository.getStatus();
      if (!status.matchesServer(server)) {
        final String message = status.installed
            ? 'Offline Kilter catalog belongs to a different server. Re-download it in Settings for ${describeServer(server)}.'
            : 'Download the offline Kilter catalog for ${describeServer(server)} before opening solo browse.';
        state = state.copyWith(
          server: server,
          loading: false,
          errorMessage: message,
        );
        return;
      }

      final List<BoardOption> boards = await _catalogRepository.getBoards();
      final BoardOption board = boards.firstWhere(
        (BoardOption item) => '${item.id}' == state.boardId,
        orElse: () => boards.isEmpty
            ? const BoardOption(id: 0, name: '', kilterName: '')
            : boards.first,
      );
      if (board.id == 0) {
        state = state.copyWith(
          server: server,
          boards: boards,
          loading: false,
          errorMessage: 'No Kilter boards were returned by the server.',
        );
        return;
      }

      state = state.copyWith(
        server: server,
        boards: boards,
        board: board,
      );
      await _appPrefsController.rememberLastKilterSurface(
        boardId: '${board.id}',
        angle: state.angle,
      );
      await _loadPage(page: 1);
    } on ApiFailure catch (error) {
      state = state.copyWith(
        server: server,
        loading: false,
        errorMessage: error.message,
      );
    }
  }

  Future<void> refresh() => _loadPage(page: state.currentPage, refresh: true);

  Future<void> selectClimb(String uuid) async {
    final BoardClimb? climb = state.climbs.cast<BoardClimb?>().firstWhere(
          (BoardClimb? item) => item?.uuid == uuid,
          orElse: () => null,
        );
    if (climb == null) {
      return;
    }
    state = state.copyWith(
      selectedClimb: climb,
      clearErrorMessage: true,
    );
    await _rememberResume(climb: climb);
  }

  Future<void> updateBoardContext({
    int? angle,
    String? sort,
    String? query,
    String? setter,
    String? grade,
  }) async {
    final int nextAngle = angle ?? state.angle;
    final String nextSort = sort ?? state.sort;
    final String nextQuery = query ?? state.query;
    final String nextSetter = setter ?? state.setter;
    final String nextGrade = grade ?? state.grade;

    state = state.copyWith(
      angle: nextAngle,
      sort: nextSort,
      query: nextQuery,
      setter: nextSetter,
      grade: nextGrade,
      currentPage: 1,
      clearErrorMessage: true,
      clearNotice: true,
    );
    if (state.board != null) {
      await _appPrefsController.rememberLastKilterSurface(
        boardId: '${state.board!.id}',
        angle: nextAngle,
      );
    }
    await _loadPage(page: 1);
  }

  Future<void> nextPage() async {
    if (!state.hasNextPage) {
      return;
    }
    await _loadPage(page: state.currentPage + 1);
  }

  Future<void> previousPage() async {
    if (state.currentPage <= 1) {
      return;
    }
    await _loadPage(page: state.currentPage - 1);
  }

  Future<SoloPlanSnapshot?> createPlan({
    required String title,
    String? notes,
    required List<ProviderClimb> climbs,
    String? createdBy,
  }) async {
    final Uri? server = state.server;
    final BoardOption? board = state.board;
    if (server == null || board == null || climbs.isEmpty) {
      state = state.copyWith(
        errorMessage:
            'Add at least one climb before creating a shared solo plan.',
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
        providerId: 'kilter',
        title: title.trim().isEmpty ? '${board.kilterName} plan' : title.trim(),
        notes: notes?.trim().isEmpty == true ? null : notes?.trim(),
        surface: ProviderSurface(
          id: '${board.id}',
          kind: 'board',
          name: board.kilterName,
          meta: <String, String>{
            'board_id': '${board.id}',
            'angle': '${state.angle}',
          },
        ),
        filters: _filters(),
        climbs: climbs,
        openPath: buildOpenPath(),
        createdBy: createdBy?.trim().isEmpty == true ? null : createdBy?.trim(),
      );
      state = state.copyWith(
        actionInFlight: false,
        notice: 'Shared solo plan created.',
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

  Future<void> beginRoomSeed({
    required List<ProviderClimb> climbs,
    String? title,
  }) async {
    final BoardOption? board = state.board;
    if (board == null) {
      return;
    }

    final PendingRoomSeed seed = PendingRoomSeed(
      providerId: 'kilter',
      title: title?.trim().isEmpty == true ? null : title?.trim(),
      surface: ProviderSurface(
        id: '${board.id}',
        kind: 'board',
        name: board.kilterName,
        meta: <String, String>{
          'board_id': '${board.id}',
          'angle': '${state.angle}',
        },
      ),
      climbs: climbs,
      openPath: buildOpenPath(),
      createdAt: DateTime.now().toUtc().toIso8601String(),
    );

    await _appPrefsController.setPendingRoomSeed(seed);
    await _appPrefsController.rememberLastProvider('kilter');
    state = state.copyWith(
      notice: climbs.isEmpty
          ? 'Saved the current board context for room creation.'
          : 'Saved a shortlist seed for room creation.',
      clearErrorMessage: true,
    );
  }

  String buildOpenPath() {
    final Map<String, String> queryParameters = <String, String>{
      'angle': '${state.angle}',
      'sort': state.sort,
      if (state.query.trim().isNotEmpty) 'q': state.query.trim(),
      if (state.setter.trim().isNotEmpty) 'setter': state.setter.trim(),
      if (state.grade.trim().isNotEmpty) 'grade': state.grade.trim(),
      if (state.selectedClimb != null) 'climb': state.selectedClimb!.uuid,
    };
    return Uri(
      path: '/solo/boards/${Uri.encodeComponent(state.boardId)}',
      queryParameters: queryParameters,
    ).toString();
  }

  Future<Uri?> _resolveServer() async {
    if (_args.initialServer != null && _args.initialServer!.trim().isNotEmpty) {
      return normalizeServerUri(_args.initialServer!);
    }
    return _sessionRepository.loadActiveServer();
  }

  Future<void> _loadPage({
    required int page,
    bool refresh = false,
  }) async {
    final Uri? server = state.server;
    if (server == null) {
      return;
    }

    try {
      state = state.copyWith(
        loading: !refresh && page == 1,
        pageLoading: refresh || page != 1,
        currentPage: page,
        clearErrorMessage: true,
        clearNotice: true,
      );
      final PaginatedBoardClimbsResponse response =
          await _catalogRepository.queryClimbs(
        OfflineCatalogQuery(
          boardId: state.boardId,
          angle: state.angle,
          page: page,
          pageSize: 10,
          name: state.query.trim().isEmpty ? null : state.query.trim(),
          setter: state.setter.trim().isEmpty ? null : state.setter.trim(),
          grade: state.grade.trim().isEmpty ? null : state.grade.trim(),
          sort: state.sort,
        ),
      );

      BoardClimb? selectedClimb;
      final String preferredUuid =
          state.selectedClimb?.uuid ?? _args.initialClimbUuid ?? '';
      if (preferredUuid.isNotEmpty) {
        selectedClimb = response.climbs.cast<BoardClimb?>().firstWhere(
              (BoardClimb? item) => item?.uuid == preferredUuid,
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
        loading: false,
        pageLoading: false,
      );
      await _rememberResume(climb: selectedClimb);
    } on ApiFailure catch (error) {
      state = state.copyWith(
        loading: false,
        pageLoading: false,
        errorMessage: error.message,
      );
    }
  }

  Future<void> _rememberResume({BoardClimb? climb}) async {
    await _appPrefsController.rememberSoloResume(
      SoloResumeState(
        boardId: state.boardId,
        angle: state.angle,
        sort: state.sort,
        q: state.query.trim().isEmpty ? null : state.query.trim(),
        setter: state.setter.trim().isEmpty ? null : state.setter.trim(),
        grade: state.grade.trim().isEmpty ? null : state.grade.trim(),
        climb: climb?.uuid,
      ),
    );
  }

  Map<String, String> _filters() {
    return <String, String>{
      'angle': '${state.angle}',
      'sort': state.sort,
      if (state.query.trim().isNotEmpty) 'q': state.query.trim(),
      if (state.setter.trim().isNotEmpty) 'setter': state.setter.trim(),
      if (state.grade.trim().isNotEmpty) 'grade': state.grade.trim(),
    };
  }
}
