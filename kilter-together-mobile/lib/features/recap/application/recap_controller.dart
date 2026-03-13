import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/models/product_models.dart';
import '../../../core/models/session_models.dart';
import '../../../core/network/api_client.dart';

class RecapRouteArgs {
  const RecapRouteArgs({
    required this.server,
    required this.shareId,
  });

  final String server;
  final String shareId;

  Uri get serverUri => normalizeServerUri(server);

  @override
  bool operator ==(Object other) {
    return other is RecapRouteArgs &&
        other.server == server &&
        other.shareId == shareId;
  }

  @override
  int get hashCode => Object.hash(server, shareId);
}

class RecapViewState {
  const RecapViewState({
    required this.server,
    required this.shareId,
    this.recap,
    this.loading = true,
    this.errorMessage,
  });

  final Uri server;
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
      server: server,
      shareId: shareId,
      recap: clearRecap ? null : (recap ?? this.recap),
      loading: loading ?? this.loading,
      errorMessage:
          clearErrorMessage ? null : (errorMessage ?? this.errorMessage),
    );
  }
}

final recapControllerProvider = StateNotifierProvider.autoDispose
    .family<RecapController, RecapViewState, RecapRouteArgs>(
  (Ref ref, RecapRouteArgs args) {
    return RecapController(
      args: args,
      apiClient: ref.read(apiClientProvider),
    );
  },
);

class RecapController extends StateNotifier<RecapViewState> {
  RecapController({
    required RecapRouteArgs args,
    required ApiClient apiClient,
  })  : _args = args,
        _apiClient = apiClient,
        super(
          RecapViewState(
            server: args.serverUri,
            shareId: args.shareId,
          ),
        ) {
    unawaited(load());
  }

  final RecapRouteArgs _args;
  final ApiClient _apiClient;

  Future<void> load() async {
    state = state.copyWith(loading: true, clearErrorMessage: true);
    try {
      final RoomRecap recap = await _apiClient.getRoomRecap(
        server: _args.serverUri,
        shareId: _args.shareId,
      );
      state = state.copyWith(
        recap: recap,
        loading: false,
        clearErrorMessage: true,
      );
    } on ApiFailure catch (error) {
      state = state.copyWith(
        clearRecap: true,
        loading: false,
        errorMessage: error.message,
      );
    }
  }
}
