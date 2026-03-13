import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:share_plus/share_plus.dart';

import '../../../core/deep_links/invite_links.dart';
import '../../../core/models/app_prefs_models.dart';
import '../../../core/models/product_models.dart';
import '../../../core/models/provider_models.dart';
import '../../../core/presentation/gradient_scaffold.dart';
import '../../../core/storage/app_prefs_controller.dart';
import '../application/plan_controller.dart';

class PlanScreen extends ConsumerWidget {
  const PlanScreen({
    super.key,
    required this.server,
    required this.shareId,
  });

  final String server;
  final String shareId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final PlanRouteArgs args = PlanRouteArgs(server: server, shareId: shareId);
    final PlanViewState state = ref.watch(planControllerProvider(args));
    final PlanController controller =
        ref.read(planControllerProvider(args).notifier);

    return GradientScaffold(
      title: 'Shared Solo Plan',
      subtitle: server,
      actions: <Widget>[
        IconButton(
          onPressed: state.loading ? null : () => unawaited(controller.load()),
          icon: const Icon(Icons.refresh),
        ),
        IconButton(
          onPressed: () => context.goNamed('landing'),
          icon: const Icon(Icons.close),
        ),
      ],
      child: _PlanBody(state: state),
    );
  }
}

class _PlanBody extends ConsumerWidget {
  const _PlanBody({
    required this.state,
  });

  final PlanViewState state;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final SoloPlanSnapshot? plan = state.plan;

    if (state.loading && plan == null) {
      return const Card(
        child: Padding(
          padding: EdgeInsets.all(32),
          child: Center(child: CircularProgressIndicator()),
        ),
      );
    }

    if (plan == null) {
      return Card(
        child: Padding(
          padding: const EdgeInsets.all(22),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Text(
                'Plan unavailable',
                style: Theme.of(context).textTheme.headlineMedium,
              ),
              const SizedBox(height: 8),
              Text(
                state.errorMessage ??
                    'The shared plan link may be invalid or the snapshot is no longer available.',
              ),
            ],
          ),
        ),
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Card(
          child: Padding(
            padding: const EdgeInsets.all(22),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(
                  plan.title,
                  style: Theme.of(context).textTheme.displayLarge,
                ),
                const SizedBox(height: 8),
                Text(
                  plan.notes ?? 'No planning note was added to this snapshot.',
                ),
                const SizedBox(height: 18),
                Wrap(
                  spacing: 10,
                  runSpacing: 10,
                  children: <Widget>[
                    _InfoChip(label: plan.providerId.toUpperCase()),
                    _InfoChip(label: plan.surface.name),
                    _InfoChip(label: '${plan.climbs.length} climbs'),
                    _InfoChip(
                      label: MaterialLocalizations.of(context)
                          .formatShortDate(plan.createdAt.toLocal()),
                    ),
                  ],
                ),
                if (plan.filters.isNotEmpty) ...<Widget>[
                  const SizedBox(height: 18),
                  Wrap(
                    spacing: 10,
                    runSpacing: 10,
                    children: plan.filters.entries
                        .where((MapEntry<String, String> item) =>
                            item.value.isNotEmpty)
                        .map(
                          (MapEntry<String, String> item) =>
                              _InfoChip(label: '${item.key}: ${item.value}'),
                        )
                        .toList(growable: false),
                  ),
                ],
                const SizedBox(height: 18),
                Row(
                  children: <Widget>[
                    Expanded(
                      child: FilledButton(
                        onPressed: () => unawaited(_sharePlan(plan)),
                        child: const Text('Share link'),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: FilledButton.tonal(
                        onPressed: plan.openPath == null
                            ? null
                            : () => _openInSolo(
                                context, state.server, plan.openPath!),
                        child: const Text('Open in solo'),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                SizedBox(
                  width: double.infinity,
                  child: OutlinedButton(
                    onPressed: () => unawaited(
                      _startRoomFromPlan(
                        context: context,
                        ref: ref,
                        plan: plan,
                      ),
                    ),
                    child: const Text('Start room from plan'),
                  ),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 14),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(22),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(
                  'Planned climbs',
                  style: Theme.of(context).textTheme.headlineMedium,
                ),
                const SizedBox(height: 12),
                ...plan.climbs.map(
                  (ProviderClimb climb) => ListTile(
                    contentPadding: EdgeInsets.zero,
                    title: Text(climb.name),
                    subtitle: Text(
                      [
                        if ((climb.primaryGrade ?? '').isNotEmpty)
                          climb.primaryGrade!,
                        if ((climb.setterName ?? '').isNotEmpty)
                          climb.setterName!,
                        if ((climb.meta['color'] ?? '').isNotEmpty)
                          climb.meta['color']!,
                      ].join(' · '),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }

  Future<void> _sharePlan(SoloPlanSnapshot plan) async {
    final Uri shareUri = InviteLink(
      kind: InviteKind.plan,
      server: state.server,
      shareId: plan.shareId,
    ).toUri();
    await Share.share(
      shareUri.toString(),
      subject: plan.title,
    );
  }

  void _openInSolo(BuildContext context, Uri server, String openPath) {
    final GoRouter router = GoRouter.of(context);
    final Uri path = Uri.parse(openPath);
    final Map<String, String> queryParameters =
        Map<String, String>.from(path.queryParameters);
    queryParameters.putIfAbsent('server', () => server.toString());
    router.go(
      path.replace(queryParameters: queryParameters).toString(),
    );
  }

  Future<void> _startRoomFromPlan({
    required BuildContext context,
    required WidgetRef ref,
    required SoloPlanSnapshot plan,
  }) async {
    final GoRouter router = GoRouter.of(context);
    await ref.read(appPrefsControllerProvider.notifier).setPendingRoomSeed(
          PendingRoomSeed(
            providerId: plan.providerId,
            title: plan.title,
            surface: plan.surface,
            climbs: plan.climbs,
            openPath: plan.openPath,
            createdAt: plan.createdAt.toUtc().toIso8601String(),
          ),
        );
    await ref
        .read(appPrefsControllerProvider.notifier)
        .rememberLastProvider(plan.providerId);
    if (!context.mounted) {
      return;
    }
    router.goNamed('create-room');
  }
}

class _InfoChip extends StatelessWidget {
  const _InfoChip({
    required this.label,
  });

  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: const Color(0xFFF0FDFA),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFFB7E4DF)),
      ),
      child: Text(label),
    );
  }
}
