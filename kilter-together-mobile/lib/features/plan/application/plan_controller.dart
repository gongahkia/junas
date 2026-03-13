import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/models/product_models.dart';
import '../../../core/models/session_models.dart';
import '../../../core/network/api_client.dart';

class PlanRouteArgs {
  const PlanRouteArgs({
    required this.server,
    required this.shareId,
  });

  final String server;
  final String shareId;

  Uri get serverUri => normalizeServerUri(server);

  @override
  bool operator ==(Object other) {
    return other is PlanRouteArgs &&
        other.server == server &&
        other.shareId == shareId;
  }

  @override
  int get hashCode => Object.hash(server, shareId);
}

class PlanViewState {
  const PlanViewState({
    required this.server,
    required this.shareId,
    this.plan,
    this.loading = true,
    this.errorMessage,
  });

  final Uri server;
  final String shareId;
  final SoloPlanSnapshot? plan;
  final bool loading;
  final String? errorMessage;

  PlanViewState copyWith({
    SoloPlanSnapshot? plan,
    bool clearPlan = false,
    bool? loading,
    String? errorMessage,
    bool clearErrorMessage = false,
  }) {
    return PlanViewState(
      server: server,
      shareId: shareId,
      plan: clearPlan ? null : (plan ?? this.plan),
      loading: loading ?? this.loading,
      errorMessage:
          clearErrorMessage ? null : (errorMessage ?? this.errorMessage),
    );
  }
}

final planControllerProvider = StateNotifierProvider.autoDispose
    .family<PlanController, PlanViewState, PlanRouteArgs>(
  (Ref ref, PlanRouteArgs args) {
    return PlanController(
      args: args,
      apiClient: ref.read(apiClientProvider),
    );
  },
);

class PlanController extends StateNotifier<PlanViewState> {
  PlanController({
    required PlanRouteArgs args,
    required ApiClient apiClient,
  })  : _args = args,
        _apiClient = apiClient,
        super(
          PlanViewState(
            server: args.serverUri,
            shareId: args.shareId,
          ),
        ) {
    unawaited(load());
  }

  final PlanRouteArgs _args;
  final ApiClient _apiClient;

  Future<void> load() async {
    state = state.copyWith(loading: true, clearErrorMessage: true);
    try {
      final SoloPlanSnapshot plan = await _apiClient.getSoloPlan(
        server: _args.serverUri,
        shareId: _args.shareId,
      );
      state = state.copyWith(
        plan: plan,
        loading: false,
        clearErrorMessage: true,
      );
    } on ApiFailure catch (error) {
      state = state.copyWith(
        clearPlan: true,
        loading: false,
        errorMessage: error.message,
      );
    }
  }
}
