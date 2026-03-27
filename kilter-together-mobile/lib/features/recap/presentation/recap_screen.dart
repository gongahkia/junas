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
import '../../../core/presentation/feedback_prompt_card.dart';
import '../../../core/presentation/gradient_scaffold.dart';
import '../../../core/storage/app_prefs_controller.dart';
import '../../../core/theme/app_theme.dart';
import '../application/recap_controller.dart';

class RecapScreen extends ConsumerStatefulWidget {
  const RecapScreen({
    super.key,
    required this.shareId,
  });

  final String shareId;

  @override
  ConsumerState<RecapScreen> createState() => _RecapScreenState();
}

class _RecapScreenState extends ConsumerState<RecapScreen> {
  int _slideIndex = 0;
  bool _feedbackVisible = false;
  bool _feedbackChecked = false;

  RecapRouteArgs get _args =>
      RecapRouteArgs(server: 'p2p://local', shareId: widget.shareId);

  @override
  Widget build(BuildContext context) {
    final RecapViewState state = ref.watch(recapControllerProvider(_args));
    final RecapController controller =
        ref.read(recapControllerProvider(_args).notifier);
    final RoomRecap? recap = state.recap;

    if (recap != null && _slideIndex >= recap.slides.length) {
      _slideIndex = recap.slides.isEmpty ? 0 : recap.slides.length - 1;
    }
    if (recap != null &&
        recap.slides.isNotEmpty &&
        _slideIndex == recap.slides.length - 1 &&
        !_feedbackChecked) {
      _feedbackChecked = true;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        unawaited(_checkFeedbackPrompt());
      });
    }

    return GradientScaffold(
      title: 'Session Recap',
      actions: <Widget>[
        IconButton(
          onPressed: state.loading ? null : () => unawaited(controller.load()),
          icon: const Icon(Icons.refresh),
        ),
        IconButton(
          onPressed: recap == null
              ? null
              : () => unawaited(
                    Share.share(
                      InviteLink(
                        kind: InviteKind.recap,
                        shareId: recap.shareId,
                      ).toUri().toString(),
                      subject: recap.roomName ?? 'Session recap',
                    ),
                  ),
          icon: const Icon(Icons.ios_share),
        ),
        IconButton(
          onPressed: () => context.goNamed('session-home'),
          icon: const Icon(Icons.close),
        ),
      ],
      child: _RecapBody(
        state: state,
        slideIndex: _slideIndex,
        feedbackVisible: _feedbackVisible,
        onDismissFeedback: () => unawaited(_dismissFeedback()),
        onPrevious: recap == null || _slideIndex == 0
            ? null
            : () => setState(() {
                  _slideIndex -= 1;
                  _feedbackChecked = false;
                  _feedbackVisible = false;
                }),
        onNext: recap == null || _slideIndex >= recap.slides.length - 1
            ? null
            : () => setState(() {
                  _slideIndex += 1;
                  _feedbackChecked = false;
                  _feedbackVisible = false;
                }),
        onShare: recap == null
            ? null
            : () => unawaited(
                  Share.share(
                    InviteLink(
                      kind: InviteKind.recap,
                      shareId: recap.shareId,
                    ).toUri().toString(),
                    subject: recap.roomName ?? 'Session recap',
                  ),
                ),
        onStartRematch: recap?.rematchSeed == null
            ? null
            : () => unawaited(
                  _startRematch(
                    context: context,
                    recap: recap!,
                  ),
                ),
        onFeedback: (String sentiment, String? message) => _submitFeedback(
          sentiment: sentiment,
          message: message,
          recap: recap,
        ),
      ),
    );
  }

  Future<void> _checkFeedbackPrompt() async {
    final bool shouldShow = await ref
        .read(appPrefsControllerProvider.notifier)
        .shouldShowFeedbackPrompt('recap_final_slide');
    if (!mounted) {
      return;
    }
    setState(() {
      _feedbackVisible = shouldShow;
    });
  }

  Future<void> _dismissFeedback() async {
    await ref
        .read(appPrefsControllerProvider.notifier)
        .markFeedbackPromptSeen('recap_final_slide');
    if (!mounted) {
      return;
    }
    setState(() {
      _feedbackVisible = false;
    });
  }

  Future<void> _submitFeedback({
    required String sentiment,
    required String? message,
    required RoomRecap? recap,
  }) async {
    if (recap == null) return;
    await ref
        .read(appPrefsControllerProvider.notifier)
        .markFeedbackPromptSeen('recap_final_slide');
    if (!mounted) return;
    setState(() {
      _feedbackVisible = false;
    });
  }

  Future<void> _startRematch({
    required BuildContext context,
    required RoomRecap recap,
  }) async {
    final GoRouter router = GoRouter.of(context);
    final RoomSeed seed = recap.rematchSeed!;
    await ref.read(appPrefsControllerProvider.notifier).setPendingRoomSeed(
          PendingRoomSeed(
            providerId: seed.providerId,
            title: recap.roomName,
            surface: seed.surface,
            climbs: seed.climbs,
            createdAt: DateTime.now().toUtc().toIso8601String(),
          ),
        );
    await ref
        .read(appPrefsControllerProvider.notifier)
        .rememberLastProvider(seed.providerId);
    if (!mounted) {
      return;
    }
    router.goNamed('create-room');
  }
}

class _RecapBody extends StatelessWidget {
  const _RecapBody({
    required this.state,
    required this.slideIndex,
    required this.feedbackVisible,
    required this.onDismissFeedback,
    required this.onPrevious,
    required this.onNext,
    required this.onShare,
    required this.onStartRematch,
    required this.onFeedback,
  });

  final RecapViewState state;
  final int slideIndex;
  final bool feedbackVisible;
  final VoidCallback onDismissFeedback;
  final VoidCallback? onPrevious;
  final VoidCallback? onNext;
  final VoidCallback? onShare;
  final VoidCallback? onStartRematch;
  final Future<void> Function(String sentiment, String? message) onFeedback;

  @override
  Widget build(BuildContext context) {
    final RoomRecap? recap = state.recap;
    final KilterPalette palette = kilterPaletteOf(context);

    if (state.loading && recap == null) {
      return AppPanel(
        accentColor: palette.secondary,
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 28),
          child: Column(
            children: <Widget>[
              Center(child: ClimbingLoader()),
              const SizedBox(height: 16),
              Text(
                'Loading recap deck.',
                style: Theme.of(context).textTheme.titleMedium,
              ),
            ],
          ),
        ),
      );
    }

    if (recap == null) {
      return AppPanel(
        accentColor: const Color(0xFF9B3445),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              'Recap unavailable',
              style: Theme.of(context).textTheme.headlineMedium,
            ),
            const SizedBox(height: 8),
            Text(
              state.errorMessage ??
                  'The recap link may be invalid or the server no longer has this snapshot.',
            ),
          ],
        ),
      );
    }

    final RecapSlide slide = recap.slides[slideIndex];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        AppPanel(
          accentColor: palette.primary,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: <Widget>[
                  _InfoChip(
                    label: recap.providerId.toUpperCase(),
                    color: palette.primary,
                  ),
                  if ((recap.surfaceName ?? '').isNotEmpty)
                    _InfoChip(
                      label: recap.surfaceName!,
                      color: palette.secondary,
                    ),
                  _InfoChip(
                    label: 'Slide ${slideIndex + 1} / ${recap.slides.length}',
                    color: palette.highlight,
                  ),
                ],
              ),
              const SizedBox(height: 18),
              Text(
                recap.roomName ?? 'Session recap',
                style: Theme.of(context).textTheme.displayLarge,
              ),
              const SizedBox(height: 18),
              Row(
                children: <Widget>[
                  Expanded(
                    child: FilledButton(
                      onPressed: onShare,
                      child: const Text('Share recap'),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: FilledButton.tonal(
                      onPressed: onStartRematch,
                      child: const Text('Start rematch'),
                    ),
                  ),
                ],
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
              AppBadge(
                label: slide.eyebrow,
                icon: Icons.insights_rounded,
                color: palette.highlight,
              ),
              const SizedBox(height: 12),
              Text(
                slide.title,
                style: Theme.of(context).textTheme.headlineMedium,
              ),
              const SizedBox(height: 10),
              Text(slide.description),
              if (slide.stats.isNotEmpty) ...<Widget>[
                const SizedBox(height: 18),
                Wrap(
                  spacing: 10,
                  runSpacing: 10,
                  children: slide.stats
                      .map(
                        (RecapStat stat) => _InfoChip(
                          label: '${stat.label}: ${stat.value}',
                          color: palette.primary,
                        ),
                      )
                      .toList(growable: false),
                ),
              ],
              if (slide.featuredClimb != null) ...<Widget>[
                const SizedBox(height: 18),
                _RecapClimbTile(
                  label: 'Featured climb',
                  climb: slide.featuredClimb!,
                ),
              ],
              if (slide.climbs.isNotEmpty) ...<Widget>[
                const SizedBox(height: 12),
                ...slide.climbs.map(
                  (SessionSummaryClimb item) => _RecapClimbTile(
                    climb: item.climb,
                    detail: [
                      if ((item.voteCount ?? 0) > 0)
                        '${item.voteCount} fist bump${item.voteCount == 1 ? '' : 's'}',
                      if ((item.status ?? '').isNotEmpty) item.status!,
                    ].join(' · '),
                  ),
                ),
              ],
              if (slide.participants.isNotEmpty) ...<Widget>[
                const SizedBox(height: 12),
                Wrap(
                  spacing: 10,
                  runSpacing: 10,
                  children: slide.participants
                      .map(
                        (String name) =>
                            _InfoChip(label: name, color: palette.secondary),
                      )
                      .toList(growable: false),
                ),
              ],
            ],
          ),
        ),
        const SizedBox(height: 14),
        AppPanel(
          accentColor: palette.secondary,
          padding: const EdgeInsets.all(18),
          child: Row(
            children: <Widget>[
              Expanded(
                child: FilledButton.tonal(
                  onPressed: onPrevious,
                  child: const Text('Previous'),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: FilledButton(
                  onPressed: onNext,
                  child: const Text('Next'),
                ),
              ),
            ],
          ),
        ),
        if (feedbackVisible) ...<Widget>[
          const SizedBox(height: 14),
          FeedbackPromptCard(
            title: 'How did this recap feel?',
            description:
                'A quick signal helps tune the next recap deck without keeping analytics infrastructure around.',
            onDismiss: onDismissFeedback,
            onSubmit: onFeedback,
          ),
        ],
      ],
    );
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

class _RecapClimbTile extends StatelessWidget {
  const _RecapClimbTile({
    required this.climb,
    this.label,
    this.detail,
  });

  final ProviderClimb climb;
  final String? label;
  final String? detail;

  @override
  Widget build(BuildContext context) {
    final KilterPalette palette = kilterPaletteOf(context);

    final String subtitle = <String>[
      if ((climb.primaryGrade ?? '').isNotEmpty) climb.primaryGrade!,
      if ((climb.setterName ?? '').isNotEmpty) climb.setterName!,
      if ((detail ?? '').trim().isNotEmpty) detail!.trim(),
    ].join(' · ');

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
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              if ((label ?? '').trim().isNotEmpty) ...<Widget>[
                AppBadge(
                  label: label!.trim(),
                  icon: Icons.workspace_premium_outlined,
                  color: palette.highlight,
                ),
                const SizedBox(height: 10),
              ],
              Text(
                climb.name,
                style: Theme.of(context).textTheme.titleMedium,
              ),
              if (subtitle.isNotEmpty) ...<Widget>[
                const SizedBox(height: 6),
                Text(subtitle),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
