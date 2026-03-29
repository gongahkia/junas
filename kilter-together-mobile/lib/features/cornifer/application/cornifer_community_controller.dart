import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/community/cornifer_models.dart';
import '../../../core/community/cornifer_session_repository.dart';
import '../../../core/models/product_models.dart';
import '../../../core/models/provider_models.dart';
import '../../../core/network/api_client.dart';

final AutoDisposeStateNotifierProviderFamily<CorniferCommunityController,
        CorniferCommunityState, Uri?> corniferCommunityControllerProvider =
    StateNotifierProvider.autoDispose
        .family<CorniferCommunityController, CorniferCommunityState, Uri?>(
  (Ref ref, Uri? server) {
    return CorniferCommunityController(
      server: server,
      apiClient: ref.read(apiClientProvider),
      sessionRepository: ref.read(corniferSessionRepositoryProvider),
    );
  },
);

class CorniferCommunityState {
  const CorniferCommunityState({
    this.server,
    this.loadingSession = true,
    this.actionInFlight = false,
    this.session,
    this.boardDraft,
    this.errorMessage,
    this.notice,
    this.attemptCounts = const <String, int>{},
    this.ratingSummaries = const <String, Map<String, int>>{},
    this.myRatings = const <String, int>{},
  });

  final Uri? server;
  final bool loadingSession;
  final bool actionInFlight;
  final CorniferSession? session;
  final CorniferBoardDraft? boardDraft;
  final String? errorMessage;
  final String? notice;
  final Map<String, int> attemptCounts;
  final Map<String, Map<String, int>> ratingSummaries;
  final Map<String, int> myRatings;

  CorniferCommunityState copyWith({
    Uri? server,
    bool? loadingSession,
    bool? actionInFlight,
    CorniferSession? session,
    bool clearSession = false,
    CorniferBoardDraft? boardDraft,
    bool clearBoardDraft = false,
    String? errorMessage,
    bool clearErrorMessage = false,
    String? notice,
    bool clearNotice = false,
    Map<String, int>? attemptCounts,
    Map<String, Map<String, int>>? ratingSummaries,
    Map<String, int>? myRatings,
  }) {
    return CorniferCommunityState(
      server: server ?? this.server,
      loadingSession: loadingSession ?? this.loadingSession,
      actionInFlight: actionInFlight ?? this.actionInFlight,
      session: clearSession ? null : (session ?? this.session),
      boardDraft: clearBoardDraft ? null : (boardDraft ?? this.boardDraft),
      errorMessage:
          clearErrorMessage ? null : (errorMessage ?? this.errorMessage),
      notice: clearNotice ? null : (notice ?? this.notice),
      attemptCounts: attemptCounts ?? this.attemptCounts,
      ratingSummaries: ratingSummaries ?? this.ratingSummaries,
      myRatings: myRatings ?? this.myRatings,
    );
  }
}

class CorniferCommunityController
    extends StateNotifier<CorniferCommunityState> {
  CorniferCommunityController({
    required Uri? server,
    required ApiClient apiClient,
    required CorniferSessionRepository sessionRepository,
  })  : _server = server,
        _apiClient = apiClient,
        _sessionRepository = sessionRepository,
        super(
          CorniferCommunityState(
            server: server,
            loadingSession: server != null,
          ),
        ) {
    unawaited(loadSession());
  }

  final Uri? _server;
  final ApiClient _apiClient;
  final CorniferSessionRepository _sessionRepository;

  Future<void> loadSession() async {
    final Uri? server = _server;
    if (server == null) {
      state = state.copyWith(loadingSession: false, clearSession: true);
      return;
    }

    final CorniferSession? saved = await _sessionRepository.load(server);
    if (saved == null) {
      state = state.copyWith(loadingSession: false, clearSession: true);
      return;
    }

    try {
      final CorniferSession session = await _apiClient.fetchCorniferMe(
        server: server,
        token: saved.token,
      );
      state = state.copyWith(
        loadingSession: false,
        session: session,
        clearErrorMessage: true,
      );
    } on ApiFailure {
      await _sessionRepository.clear(server);
      state = state.copyWith(
        loadingSession: false,
        clearSession: true,
      );
    }
  }

  Future<void> register({
    required String username,
    required String password,
  }) async {
    final Uri? server = _requireServer();
    if (server == null) {
      return;
    }
    final String normalizedUsername = username.trim().toLowerCase();
    if (normalizedUsername.isEmpty || password.trim().isEmpty) {
      state = state.copyWith(
        errorMessage:
            'Enter a username and password to create a Cornifer account.',
        clearNotice: true,
      );
      return;
    }

    try {
      state = state.copyWith(
        actionInFlight: true,
        clearErrorMessage: true,
        clearNotice: true,
      );
      final CorniferSession session = await _apiClient.registerCornifer(
        server: server,
        username: normalizedUsername,
        password: password,
      );
      await _sessionRepository.save(server, session);
      state = state.copyWith(
        actionInFlight: false,
        session: session,
        notice:
            'Cornifer account ready. You can publish boards and climbs now.',
      );
    } on ApiFailure catch (error) {
      state = state.copyWith(
        actionInFlight: false,
        errorMessage: error.message,
      );
    }
  }

  Future<void> login({
    required String username,
    required String password,
  }) async {
    final Uri? server = _requireServer();
    if (server == null) {
      return;
    }
    final String normalizedUsername = username.trim().toLowerCase();
    if (normalizedUsername.isEmpty || password.trim().isEmpty) {
      state = state.copyWith(
        errorMessage: 'Enter a username and password to sign in to Cornifer.',
        clearNotice: true,
      );
      return;
    }

    try {
      state = state.copyWith(
        actionInFlight: true,
        clearErrorMessage: true,
        clearNotice: true,
      );
      final CorniferSession session = await _apiClient.loginCornifer(
        server: server,
        username: normalizedUsername,
        password: password,
      );
      await _sessionRepository.save(server, session);
      state = state.copyWith(
        actionInFlight: false,
        session: session,
        notice: 'Cornifer community session restored.',
      );
    } on ApiFailure catch (error) {
      state = state.copyWith(
        actionInFlight: false,
        errorMessage: error.message,
      );
    }
  }

  Future<void> logout() async {
    final CorniferSession? session = state.session;
    final Uri? server = _server;
    if (session == null) {
      return;
    }

    state = state.copyWith(
      actionInFlight: true,
      clearErrorMessage: true,
      clearNotice: true,
    );

    try {
      if (server != null) {
        await _apiClient.logoutCornifer(server: server, token: session.token);
      }
    } on ApiFailure {
      // Continue clearing local state even if the server-side logout fails.
    }

    if (server != null) {
      await _sessionRepository.clear(server);
    }
    state = state.copyWith(
      actionInFlight: false,
      clearSession: true,
      notice: 'Cornifer session cleared from this device.',
    );
  }

  Future<CorniferBoardDraft?> createBoard({
    required String name,
    required String location,
    required String description,
    required String imagePath,
  }) async {
    final Uri? server = _requireServer();
    final CorniferSession? session = _requireSession();
    if (server == null || session == null) {
      return null;
    }
    if (name.trim().isEmpty ||
        location.trim().isEmpty ||
        imagePath.trim().isEmpty) {
      state = state.copyWith(
        errorMessage:
            'Pick a board image and enter both a board name and location first.',
        clearNotice: true,
      );
      return null;
    }

    try {
      state = state.copyWith(
        actionInFlight: true,
        clearErrorMessage: true,
        clearNotice: true,
      );
      final CorniferBoardDraft draft = await _apiClient.createCorniferBoard(
        server: server,
        token: session.token,
        name: name.trim(),
        location: location.trim(),
        description: description.trim(),
        imagePath: imagePath.trim(),
      );
      state = state.copyWith(
        actionInFlight: false,
        boardDraft: draft,
        notice:
            'Board draft created. Run hold detection, review it, then publish the board.',
      );
      return draft;
    } on ApiFailure catch (error) {
      state = state.copyWith(
        actionInFlight: false,
        errorMessage: error.message,
      );
      return null;
    }
  }

  Future<CorniferBoardDraft?> detectHolds() async {
    final Uri? server = _requireServer();
    final CorniferSession? session = _requireSession();
    final CorniferBoardDraft? draft = state.boardDraft;
    if (server == null || session == null || draft == null) {
      return null;
    }

    try {
      state = state.copyWith(
        actionInFlight: true,
        clearErrorMessage: true,
        clearNotice: true,
      );
      final CorniferBoardDraft updated =
          await _apiClient.detectCorniferBoardHolds(
        server: server,
        token: session.token,
        boardId: draft.id,
      );
      state = state.copyWith(
        actionInFlight: false,
        boardDraft: updated,
        notice: updated.holds.isEmpty
            ? 'No holds were detected. Add them manually before publishing.'
            : 'Hold detection finished. Review the hold map before publishing.',
      );
      return updated;
    } on ApiFailure catch (error) {
      state = state.copyWith(
        actionInFlight: false,
        errorMessage: error.message,
      );
      return null;
    }
  }

  Future<CorniferBoardDraft?> updateBoardHolds(
    List<CorniferBoardHold> holds, {
    bool publish = false,
  }) async {
    final Uri? server = _requireServer();
    final CorniferSession? session = _requireSession();
    final CorniferBoardDraft? draft = state.boardDraft;
    if (server == null || session == null || draft == null) {
      return null;
    }
    if (holds.isEmpty) {
      state = state.copyWith(
        errorMessage: 'Confirm at least one hold before publishing the board.',
        clearNotice: true,
      );
      return null;
    }

    final List<CorniferBoardHold> normalized = _normalizeHolds(holds);
    try {
      state = state.copyWith(
        actionInFlight: true,
        clearErrorMessage: true,
        clearNotice: true,
      );
      final CorniferBoardDraft updated =
          await _apiClient.confirmCorniferBoardHolds(
        server: server,
        token: session.token,
        boardId: draft.id,
        holds: normalized,
        publish: publish,
      );
      state = state.copyWith(
        actionInFlight: false,
        boardDraft: updated,
        notice: publish
            ? 'Board published. It is now part of the Cornifer catalog.'
            : 'Hold review saved. Publish the board when the map looks correct.',
      );
      return updated;
    } on ApiFailure catch (error) {
      state = state.copyWith(
        actionInFlight: false,
        errorMessage: error.message,
      );
      return null;
    }
  }

  Future<ProviderClimb?> createClimb({
    required String boardId,
    required String name,
    required String grade,
    required String description,
    required List<CorniferClimbSelection> holds,
  }) async {
    final Uri? server = _requireServer();
    final CorniferSession? session = _requireSession();
    if (server == null || session == null) {
      return null;
    }
    if (name.trim().isEmpty || grade.trim().isEmpty || holds.isEmpty) {
      state = state.copyWith(
        errorMessage:
            'Enter a climb name, grade, and at least one hold role before publishing.',
        clearNotice: true,
      );
      return null;
    }

    try {
      state = state.copyWith(
        actionInFlight: true,
        clearErrorMessage: true,
        clearNotice: true,
      );
      final ProviderCatalogClimbResponse response =
          await _apiClient.createCorniferClimb(
        server: server,
        token: session.token,
        boardId: boardId,
        name: name.trim(),
        grade: grade.trim(),
        description: description.trim(),
        holds: holds,
      );
      state = state.copyWith(
        actionInFlight: false,
        notice: 'Climb published to Cornifer.',
      );
      return response.climb;
    } on ApiFailure catch (error) {
      state = state.copyWith(
        actionInFlight: false,
        errorMessage: error.message,
      );
      return null;
    }
  }

  Future<int?> submitAttempt({
    required String climbId,
    required int tries,
  }) async {
    final Uri? server = _requireServer();
    final CorniferSession? session = _requireSession();
    if (server == null || session == null) {
      return null;
    }
    if (tries <= 0) {
      state = state.copyWith(
        errorMessage: 'Tries used must be at least 1.',
        clearNotice: true,
      );
      return null;
    }

    try {
      state = state.copyWith(
        actionInFlight: true,
        clearErrorMessage: true,
        clearNotice: true,
      );
      final int count = await _apiClient.submitCorniferAttempt(
        server: server,
        token: session.token,
        climbId: climbId,
        tries: tries,
      );
      state = state.copyWith(
        actionInFlight: false,
        attemptCounts: <String, int>{
          ...state.attemptCounts,
          climbId: count,
        },
        notice: 'Cornifer tries logged.',
      );
      return count;
    } on ApiFailure catch (error) {
      state = state.copyWith(
        actionInFlight: false,
        errorMessage: error.message,
      );
      return null;
    }
  }

  Future<Map<String, int>?> rateClimb({
    required String climbId,
    required int value,
  }) async {
    final Uri? server = _requireServer();
    final CorniferSession? session = _requireSession();
    if (server == null || session == null) {
      return null;
    }
    if (value != -1 && value != 1) {
      state = state.copyWith(
        errorMessage: 'Cornifer ratings must be either up or down.',
        clearNotice: true,
      );
      return null;
    }

    try {
      state = state.copyWith(
        actionInFlight: true,
        clearErrorMessage: true,
        clearNotice: true,
      );
      final Map<String, int> summary = await _apiClient.rateCorniferClimb(
        server: server,
        token: session.token,
        climbId: climbId,
        value: value,
      );
      state = state.copyWith(
        actionInFlight: false,
        ratingSummaries: <String, Map<String, int>>{
          ...state.ratingSummaries,
          climbId: summary,
        },
        myRatings: <String, int>{
          ...state.myRatings,
          climbId: value,
        },
        notice:
            value > 0 ? 'Cornifer upvote saved.' : 'Cornifer downvote saved.',
      );
      return summary;
    } on ApiFailure catch (error) {
      state = state.copyWith(
        actionInFlight: false,
        errorMessage: error.message,
      );
      return null;
    }
  }

  void clearNotice() {
    state = state.copyWith(clearNotice: true);
  }

  void clearError() {
    state = state.copyWith(clearErrorMessage: true);
  }

  Uri? _requireServer() {
    if (_server != null) {
      return _server;
    }
    state = state.copyWith(
      errorMessage:
          'Choose an active self-hosted server before using Cornifer.',
      clearNotice: true,
    );
    return null;
  }

  CorniferSession? _requireSession() {
    final CorniferSession? session = state.session;
    if (session != null) {
      return session;
    }
    state = state.copyWith(
      errorMessage:
          'Sign in to your Cornifer community account before creating, attempting, or rating.',
      clearNotice: true,
    );
    return null;
  }

  List<CorniferBoardHold> _normalizeHolds(List<CorniferBoardHold> holds) {
    final List<CorniferBoardHold> sorted = List<CorniferBoardHold>.from(holds)
      ..sort(
        (CorniferBoardHold a, CorniferBoardHold b) =>
            a.position.compareTo(b.position),
      );
    return sorted
        .asMap()
        .entries
        .map(
          (MapEntry<int, CorniferBoardHold> entry) => CorniferBoardHold(
            id: entry.value.id,
            position: entry.key,
            centroidX: entry.value.centroidX,
            centroidY: entry.value.centroidY,
            contour: entry.value.contour,
          ),
        )
        .toList(growable: false);
  }
}
