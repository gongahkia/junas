import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:share_plus/share_plus.dart';

import '../../../core/deep_links/invite_links.dart';
import '../../../core/models/app_prefs_models.dart';
import '../../../core/models/product_models.dart';
import '../../../core/models/provider_models.dart';
import '../../../core/presentation/app_surfaces.dart';
import '../../../core/presentation/climbing_loader.dart';
import '../../../core/presentation/gradient_scaffold.dart';
import '../../../core/storage/app_prefs_controller.dart';
import '../../../core/theme/app_theme.dart';
import '../application/plan_controller.dart';

class PlanScreen extends ConsumerWidget {
  const PlanScreen({
    super.key,
    required this.shareId,
  });

  final String shareId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final PlanRouteArgs args =
        PlanRouteArgs(server: 'p2p://local', shareId: shareId);
    final PlanViewState state = ref.watch(planControllerProvider(args));
    final PlanController controller =
        ref.read(planControllerProvider(args).notifier);

    return GradientScaffold(
      title: 'Shared Solo Plan',
      subtitle: 'Shared plan',
      actions: <Widget>[
        IconButton(
          onPressed: state.loading ? null : () => unawaited(controller.load()),
          icon: const Icon(Icons.refresh),
        ),
        IconButton(
          onPressed: state.plan == null
              ? null
              : () => unawaited(
                    Share.share(
                      InviteLink(
                        kind: InviteKind.plan,
                        shareId: state.plan!.shareId,
                      ).toUri().toString(),
                      subject: state.plan!.title,
                    ),
                  ),
          icon: const Icon(Icons.ios_share),
        ),
        IconButton(
          onPressed: () => context.goNamed('session-home'),
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
    final KilterPalette palette = kilterPaletteOf(context);

    if (state.loading && plan == null) {
      return AppPanel(
        accentColor: palette.secondary,
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 28),
          child: Column(
            children: <Widget>[
              Center(child: ClimbingLoader()),
              const SizedBox(height: 16),
              Text(
                'Loading shared plan.',
                style: Theme.of(context).textTheme.titleMedium,
              ),
            ],
          ),
        ),
      );
    }

    if (plan == null) {
      return AppPanel(
        accentColor: const Color(0xFF9B3445),
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
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        AppPanel(
          accentColor: palette.secondary,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: <Widget>[
                  AppBadge(
                    label: plan.providerId.toUpperCase(),
                    icon: Icons.terrain_rounded,
                    color: palette.secondary,
                  ),
                  AppBadge(
                    label: plan.surface.name,
                    icon: Icons.dashboard_outlined,
                    color: palette.primary,
                  ),
                  AppBadge(
                    label: '${plan.climbs.length} climbs',
                    icon: Icons.route_rounded,
                    color: palette.highlight,
                  ),
                  AppBadge(
                    label: MaterialLocalizations.of(context)
                        .formatShortDate(plan.createdAt.toLocal()),
                    icon: Icons.event_note_rounded,
                    color: palette.subtleInk,
                  ),
                ],
              ),
              const SizedBox(height: 18),
              Text(
                plan.title,
                style: Theme.of(context).textTheme.displayLarge,
              ),
              const SizedBox(height: 8),
              Text(
                plan.notes ?? 'No planning note was added to this snapshot.',
              ),
              if (plan.filters.isNotEmpty) ...<Widget>[
                const SizedBox(height: 18),
                Wrap(
                  spacing: 10,
                  runSpacing: 10,
                  children: plan.filters.entries
                      .where(
                        (MapEntry<String, String> item) =>
                            item.value.isNotEmpty,
                      )
                      .map(
                        (MapEntry<String, String> item) => _InfoChip(
                          label: '${item.key}: ${item.value}',
                          color: palette.primary,
                        ),
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
                          : () => _openInSolo(context, plan.openPath!),
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
        const SizedBox(height: 14),
        AppPanel(
          accentColor: palette.highlight,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Text(
                'Planned climbs',
                style: Theme.of(context).textTheme.headlineMedium,
              ),
              const SizedBox(height: 12),
              ...plan.climbs.map(
                (ProviderClimb climb) => _PlanClimbTile(climb: climb),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Future<void> _sharePlan(SoloPlanSnapshot plan) async {
    final Uri shareUri = InviteLink(
      kind: InviteKind.plan,
      shareId: plan.shareId,
    ).toUri();
    await Share.share(shareUri.toString(), subject: plan.title);
  }

  void _openInSolo(BuildContext context, String openPath) {
    final GoRouter router = GoRouter.of(context);
    router.go(openPath);
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
    this.color,
  });

  final String label;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    return AppBadge(label: label, color: color);
  }
}

class _PlanClimbTile extends StatelessWidget {
  const _PlanClimbTile({
    required this.climb,
  });

  final ProviderClimb climb;

  @override
  Widget build(BuildContext context) {
    final KilterPalette palette = kilterPaletteOf(context);

    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: palette.panel.withValues(alpha: 0.9),
          borderRadius: BorderRadius.circular(22),
          border: Border.all(color: palette.stroke),
        ),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Container(
                width: 42,
                height: 42,
                decoration: BoxDecoration(
                  color: palette.highlight.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Icon(
                  Icons.flag_circle_rounded,
                  color: palette.highlight,
                ),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Text(
                      climb.name,
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: 6),
                    Text(
                      [
                        if ((climb.primaryGrade ?? '').isNotEmpty)
                          climb.primaryGrade!,
                        if ((climb.setterName ?? '').isNotEmpty)
                          climb.setterName!,
                        if ((climb.meta['color'] ?? '').isNotEmpty)
                          climb.meta['color']!,
                      ].join(' · '),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
