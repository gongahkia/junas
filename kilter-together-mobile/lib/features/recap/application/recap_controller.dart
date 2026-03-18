import 'dart:async';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/models/product_models.dart';
import '../../../core/storage/local_recap_repository.dart';

class RecapRouteArgs {
  const RecapRouteArgs({
    required this.server,
    required this.shareId,
  });
  final String server;
  final String shareId;
  @override
  bool operator ==(Object other) =>
      other is RecapRouteArgs && other.server == server && other.shareId == shareId;
  @override
  int get hashCode => Object.hash(server, shareId);
}

class RecapViewState {
  const RecapViewState({
    required this.shareId,
    this.recap,
    this.loading = true,
    this.errorMessage,
  });
  final String shareId;
  final RoomRecap? recap;
  final bool loading;
  final String? errorMessage;

  RecapViewState copyWith({
    RoomRecap? recap,
    bool clearRecap = false,
    bool? loading,
    String? errorMessage,
    bool clearErrorMessage = false,
  }) {
    return RecapViewState(
      shareId: shareId,
      recap: clearRecap ? null : (recap ?? this.recap),
      loading: loading ?? this.loading,
      errorMessage: clearErrorMessage ? null : (errorMessage ?? this.errorMessage),
    );
  }
}

final recapControllerProvider = StateNotifierProvider.autoDispose
    .family<RecapController, RecapViewState, RecapRouteArgs>(
  (Ref ref, RecapRouteArgs args) {
    return RecapController(
      args: args,
      recapRepository: ref.read(localRecapRepositoryProvider),
    );
  },
);

class RecapController extends StateNotifier<RecapViewState> {
  RecapController({
    required RecapRouteArgs args,
    required LocalRecapRepository recapRepository,
  })  : _args = args,
        _recapRepository = recapRepository,
        super(RecapViewState(shareId: args.shareId)) {
    unawaited(load());
  }

  final RecapRouteArgs _args;
  final LocalRecapRepository _recapRepository;

  Future<void> load() async {
    state = state.copyWith(loading: true, clearErrorMessage: true);
    try {
      final RoomRecap? recap = await _recapRepository.loadRecap(_args.shareId);
      if (recap != null) {
        state = state.copyWith(recap: recap, loading: false, clearErrorMessage: true);
      } else {
        state = state.copyWith(
          clearRecap: true,
          loading: false,
          errorMessage: 'No recap found for this session.',
        );
      }
    } catch (e) {
      state = state.copyWith(
        clearRecap: true,
        loading: false,
        errorMessage: 'Failed to load recap: $e',
      );
    }
  }
}
