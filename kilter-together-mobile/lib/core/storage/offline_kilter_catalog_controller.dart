import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/catalog_models.dart';
import 'offline_kilter_catalog_repository.dart';
import 'session_repository.dart';

class OfflineKilterCatalogState {
  const OfflineKilterCatalogState({
    required this.status,
    this.busy = false,
    this.errorMessage,
    this.notice,
  });

  final CatalogStatus status;
  final bool busy;
  final String? errorMessage;
  final String? notice;

  OfflineKilterCatalogState copyWith({
    CatalogStatus? status,
    bool? busy,
    String? errorMessage,
    bool clearErrorMessage = false,
    String? notice,
    bool clearNotice = false,
  }) {
    return OfflineKilterCatalogState(
      status: status ?? this.status,
      busy: busy ?? this.busy,
      errorMessage:
          clearErrorMessage ? null : (errorMessage ?? this.errorMessage),
      notice: clearNotice ? null : (notice ?? this.notice),
    );
  }
}

final StateNotifierProvider<OfflineKilterCatalogController,
        OfflineKilterCatalogState> offlineKilterCatalogControllerProvider =
    StateNotifierProvider<OfflineKilterCatalogController,
        OfflineKilterCatalogState>((Ref ref) {
  return OfflineKilterCatalogController(
    repository: ref.read(offlineKilterCatalogRepositoryProvider),
    sessionRepository: ref.read(sessionRepositoryProvider),
  );
});

class OfflineKilterCatalogController
    extends StateNotifier<OfflineKilterCatalogState> {
  OfflineKilterCatalogController({
    required OfflineKilterCatalogRepository repository,
    required SessionRepository sessionRepository,
  })  : _repository = repository,
        _sessionRepository = sessionRepository,
        super(
          OfflineKilterCatalogState(status: CatalogStatus.empty()),
        ) {
    unawaited(refresh());
  }

  final OfflineKilterCatalogRepository _repository;
  final SessionRepository _sessionRepository;

  Future<void> refresh() async {
    final CatalogStatus status = await _repository.getStatus();
    state = state.copyWith(
      status: status,
      busy: false,
      clearErrorMessage: true,
    );
  }

  Future<CatalogManifest> fetchManifest(Uri server) {
    return _repository.getManifest(server);
  }

  Future<void> download(Uri server) async {
    state = state.copyWith(
      busy: true,
      clearErrorMessage: true,
      clearNotice: true,
    );
    try {
      await _repository.downloadCatalog(server);
      state = state.copyWith(
        status: await _repository.getStatus(),
        busy: false,
        notice: 'Downloaded offline Kilter catalog.',
      );
    } catch (error) {
      state = state.copyWith(
        busy: false,
        errorMessage: '$error',
      );
    }
  }

  Future<void> syncNow(Uri server) async {
    state = state.copyWith(
      busy: true,
      clearErrorMessage: true,
      clearNotice: true,
    );
    try {
      final CatalogSyncResult result =
          await _repository.syncCatalog(server, allowFullResync: true);
      state = state.copyWith(
        status: result.status,
        busy: false,
        notice: result.performedSync
            ? 'Offline Kilter catalog synced.'
            : 'Offline Kilter catalog is already up to date.',
      );
    } catch (error) {
      state = state.copyWith(
        busy: false,
        errorMessage: '$error',
      );
    }
  }

  Future<void> deleteCatalog() async {
    state = state.copyWith(
      busy: true,
      clearErrorMessage: true,
      clearNotice: true,
    );
    try {
      await _repository.deleteCatalog();
      state = state.copyWith(
        status: CatalogStatus.empty(),
        busy: false,
        notice: 'Deleted offline Kilter catalog.',
      );
    } catch (error) {
      state = state.copyWith(
        busy: false,
        errorMessage: '$error',
      );
    }
  }

  Future<void> autoSyncIfNeeded() async {
    final Uri? activeServer = await _sessionRepository.loadActiveServer();
    if (activeServer == null) {
      return;
    }

    final CatalogStatus status = await _repository.getStatus();
    state = state.copyWith(status: status);
    if (!status.matchesServer(activeServer)) {
      return;
    }

    final DateTime? lastPollAt = status.lastPollAt == null
        ? null
        : DateTime.tryParse(status.lastPollAt!);
    if (lastPollAt != null &&
        DateTime.now().toUtc().difference(lastPollAt.toUtc()) <
            const Duration(hours: 1)) {
      return;
    }

    try {
      final CatalogSyncResult result =
          await _repository.syncCatalog(activeServer, allowFullResync: false);
      state = state.copyWith(
        status: result.status,
        clearErrorMessage: true,
      );
    } catch (error) {
      state = state.copyWith(errorMessage: '$error');
    }
  }

  void clearMessages() {
    state = state.copyWith(
      clearErrorMessage: true,
      clearNotice: true,
    );
  }
}
