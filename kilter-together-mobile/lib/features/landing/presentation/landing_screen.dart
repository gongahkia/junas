import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/deep_links/invite_links.dart';
import '../../../core/models/app_prefs_models.dart';
import '../../../core/models/provider_models.dart';
import '../../../core/models/product_models.dart';
import '../../../core/models/runtime_models.dart';
import '../../../core/models/session_models.dart';
import '../../../core/network/api_client.dart';
import '../../../core/presentation/flow_guide_sheet.dart';
import '../../../core/presentation/gradient_scaffold.dart';
import '../../../core/presentation/runtime_status_banner.dart';
import '../../../core/storage/app_prefs_controller.dart';
import '../../../core/storage/session_repository.dart';

final _landingServerProvider = FutureProvider.autoDispose<Uri?>((Ref ref) {
  return ref.read(sessionRepositoryProvider).loadActiveServer();
});

final _recentSessionsProvider =
    FutureProvider.autoDispose<List<SessionSummary>>((Ref ref) async {
  final Uri? server = await ref.watch(_landingServerProvider.future);
  if (server == null) {
    return const <SessionSummary>[];
  }
  return ref
      .read(apiClientProvider)
      .getRecentSessions(server: server, limit: 4);
});

final _runtimeStatusProvider =
    FutureProvider.autoDispose<RuntimeStatus?>((Ref ref) async {
  final Uri? server = await ref.watch(_landingServerProvider.future);
  if (server == null) {
    return null;
  }
  try {
    return await ref.read(apiClientProvider).getRuntimeStatus(server: server);
  } on ApiFailure {
    return null;
  }
});

const FlowGuideContent _landingGuide = FlowGuideContent(
  eyebrow: 'Landing guide',
  title: 'How the app is split up',
  summary:
      'Start on landing when you need to decide whether this phone is hosting, joining, or just planning climbs solo.',
  sections: <FlowGuideSection>[
    FlowGuideSection(
      title: 'Create a room',
      body:
          'Use this when the phone belongs to the host. Load providers, authenticate the account, open the room, and share the invite from the same device.',
    ),
    FlowGuideSection(
      title: 'Join a room',
      body:
          'Use this when the phone is a guest device. Paste an invite or scan the host QR code, pick a display name, and rejoin if the saved room session expires.',
    ),
    FlowGuideSection(
      title: 'Solo browse',
      body:
          'Use solo mode to shortlist climbs, save filters, and seed future rooms without needing to open a live session first.',
    ),
  ],
  completionLabel: 'Mark landing guide complete',
);

String _providerLabel(String providerId) {
  return switch (providerId) {
    'kilter' => 'Kilter',
    'crux' => 'Crux',
    _ => providerId,
  };
}

String _formatRelativeTime(String raw) {
  final DateTime? parsed = DateTime.tryParse(raw);
  if (parsed == null) return raw;
  final Duration diff = DateTime.now().toUtc().difference(parsed.toUtc());
  if (diff.inMinutes < 1) return 'just now';
  if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
  if (diff.inHours < 24) return '${diff.inHours}h ago';
  if (diff.inDays < 7) return '${diff.inDays}d ago';
  return '${(diff.inDays / 7).floor()}w ago';
}

class LandingScreen extends ConsumerStatefulWidget {
  const LandingScreen({super.key});

  @override
  ConsumerState<LandingScreen> createState() => _LandingScreenState();
}

class _LandingScreenState extends ConsumerState<LandingScreen> {
  bool _autoGuideAttempted = false;
  final TextEditingController _quickJoinController = TextEditingController();

  @override
  void dispose() {
    _quickJoinController.dispose();
    super.dispose();
  }

  void _maybeAutoOpenGuide(AppPrefs prefs) {
    if (_autoGuideAttempted ||
        !prefs.settings.autoGuidesEnabled ||
        prefs.guidedTour.landingCompleted) {
      return;
    }
    _autoGuideAttempted = true;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) {
        return;
      }
      unawaited(_openGuide());
    });
  }

  Future<void> _openGuide() async {
    final AppPrefs prefs =
        ref.read(appPrefsControllerProvider).valueOrNull ?? AppPrefs.defaults();
    final FlowGuideResult? result = await showFlowGuideSheet(
      context: context,
      content: _landingGuide,
      completed: prefs.guidedTour.landingCompleted,
    );
    if (result != FlowGuideResult.completed || !mounted) {
      return;
    }
    await ref.read(appPrefsControllerProvider.notifier).completeLandingGuide();
  }

  Future<void> _startBranch({
    required String branch,
    required String routeName,
  }) async {
    await ref
        .read(appPrefsControllerProvider.notifier)
        .queueGuideBranch(branch);
    if (!mounted) {
      return;
    }
    context.goNamed(routeName);
  }

  Future<void> _showRecentRoomsSheet() {
    return showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (BuildContext context) {
        return const _RecentRoomsSheet();
      },
    );
  }

  Future<void> _startQuickJoin(Uri? activeServer) async {
    final String rawValue = _quickJoinController.text.trim();
    if (rawValue.isEmpty) {
      _showSnack('Paste a room invite, web join link, or room slug first.');
      return;
    }

    final InviteLink? invite = InviteLink.parse(rawValue);
    if (invite != null && invite.kind != InviteKind.join) {
      final String destination = switch (invite.kind) {
        InviteKind.join => 'room invite',
        InviteKind.recap => 'recap',
        InviteKind.plan => 'plan',
      };
      _showSnack(
        'That link opens a $destination, not a room invite. Open it from the matching flow instead.',
      );
      return;
    }

    final RoomJoinTarget? joinTarget = parseRoomJoinTarget(
      rawValue,
      fallbackServer: activeServer,
    );
    if (joinTarget == null) {
      _showSnack(
        'Paste a room invite, web join link, or room slug to continue.',
      );
      return;
    }

    await ref
        .read(appPrefsControllerProvider.notifier)
        .queueGuideBranch('guest');
    if (!mounted) {
      return;
    }
    context.goNamed(
      'join-room',
      queryParameters: <String, String>{
        'slug': joinTarget.slug,
        if (joinTarget.server != null) 'server': joinTarget.server.toString(),
      },
    );
  }

  void _showSnack(String message) {
    ScaffoldMessenger.of(context)
        .showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  Widget build(BuildContext context) {
    final AsyncValue<AppPrefs> prefsValue =
        ref.watch(appPrefsControllerProvider);
    final AppPrefs prefs = prefsValue.valueOrNull ?? AppPrefs.defaults();
    final AsyncValue<Uri?> activeServer = ref.watch(_landingServerProvider);
    final AsyncValue<List<SessionSummary>> recentSessions =
        ref.watch(_recentSessionsProvider);
    final RuntimeStatus? runtimeStatus =
        ref.watch(_runtimeStatusProvider).valueOrNull;
    final List<RecentRoom> previewRecentRooms =
        prefs.recentRooms.take(3).toList(growable: false);

    if (prefsValue.hasValue) {
      _maybeAutoOpenGuide(prefs);
    }

    return GradientScaffold(
      title: 'Kilter Together',
      subtitle:
          'Host, join, and run collaborative board sessions from a native mobile client.',
      actions: <Widget>[
        IconButton(
          onPressed: () => unawaited(_openGuide()),
          icon: const Icon(Icons.help_outline),
        ),
        IconButton(
          onPressed: () => context.goNamed('about'),
          icon: const Icon(Icons.info_outline),
        ),
      ],
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          if (runtimeStatus != null) ...<Widget>[
            RuntimeStatusBanner(status: runtimeStatus),
            const SizedBox(height: 14),
          ],
          _ActionCard(
            title: 'Create a room',
            description:
                'Authenticate the provider account, open a room, and share the invite from this phone.',
            accent: const Color(0xFF0F766E),
            buttonLabel: 'Host session',
            onPressed: () => unawaited(
              _startBranch(branch: 'host', routeName: 'create-room'),
            ),
          ),
          const SizedBox(height: 14),
          _JoinActionCard(
            controller: _quickJoinController,
            accent: const Color(0xFF4D7C0F),
            activeServer: activeServer.valueOrNull,
            onQuickJoin: () =>
                unawaited(_startQuickJoin(activeServer.valueOrNull)),
            onOpenJoinFlow: () => unawaited(
              _startBranch(branch: 'guest', routeName: 'join-room'),
            ),
          ),
          const SizedBox(height: 14),
          _ActionCard(
            title: 'Solo browse',
            description:
                'Open Kilter or provider-backed solo planning, keep a shortlist, and seed new rooms.',
            accent: const Color(0xFF0369A1),
            buttonLabel: 'Open solo mode',
            onPressed: () => unawaited(
              _startBranch(branch: 'solo', routeName: 'solo-entry'),
            ),
          ),
          const SizedBox(height: 20),
          Row(
            children: <Widget>[
              Expanded(
                child: Text(
                  'Recent rooms',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
              ),
              if (prefs.recentRooms.length > 3)
                TextButton(
                  onPressed: () => unawaited(_showRecentRoomsSheet()),
                  child: Text('View all (${prefs.recentRooms.length})'),
                ),
            ],
          ),
          const SizedBox(height: 12),
          if (!prefs.settings.recentRoomsEnabled)
            const Card(
              child: Padding(
                padding: EdgeInsets.all(20),
                child: Text('Recent rooms are disabled in settings.'),
              ),
            )
          else if (prefs.recentRooms.isEmpty)
            const Card(
              child: Padding(
                padding: EdgeInsets.all(20),
                child: Text(
                  'No recent rooms saved on this device yet. Your next room visit will appear here.',
                ),
              ),
            )
          else
            Column(
              children: previewRecentRooms
                  .map(
                    (RecentRoom room) => Padding(
                      padding: const EdgeInsets.only(bottom: 10),
                      child: _RecentRoomTile(room: room),
                    ),
                  )
                  .toList(growable: false),
            ),
          const SizedBox(height: 20),
          Text(
            'Server context',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 12),
          activeServer.when(
            data: (Uri? server) {
              if (server == null) {
                return const Card(
                  child: Padding(
                    padding: EdgeInsets.all(20),
                    child: Text(
                      'No active server remembered yet. Create or join a room to bind the app to a self-hosted node.',
                    ),
                  ),
                );
              }
              return Card(
                child: ListTile(
                  title: Text(describeServer(server)),
                  subtitle: Text(server.toString()),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () => context.goNamed(
                    'join-room',
                    queryParameters: <String, String>{
                      'server': server.toString()
                    },
                  ),
                ),
              );
            },
            error: (Object error, StackTrace stackTrace) => Card(
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: Text('$error'),
              ),
            ),
            loading: () => const Card(
              child: Padding(
                padding: EdgeInsets.all(20),
                child: LinearProgressIndicator(),
              ),
            ),
          ),
          const SizedBox(height: 20),
          Text(
            'Recent sessions from the active server',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 12),
          recentSessions.when(
            data: (List<SessionSummary> sessions) {
              if (sessions.isEmpty) {
                return const Card(
                  child: Padding(
                    padding: EdgeInsets.all(20),
                    child: Text(
                      'No recent sessions were returned for the active server yet.',
                    ),
                  ),
                );
              }
              return Column(
                children: sessions
                    .map(
                      (SessionSummary session) => Padding(
                        padding: const EdgeInsets.only(bottom: 10),
                        child: _RecentSessionTile(
                          session: session,
                          server: activeServer.valueOrNull,
                        ),
                      ),
                    )
                    .toList(growable: false),
              );
            },
            error: (Object error, StackTrace stackTrace) => Card(
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: Text('$error'),
              ),
            ),
            loading: () => const Card(
              child: Padding(
                padding: EdgeInsets.all(20),
                child: LinearProgressIndicator(),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _ActionCard extends StatelessWidget {
  const _ActionCard({
    required this.title,
    required this.description,
    required this.accent,
    required this.buttonLabel,
    required this.onPressed,
  });

  final String title;
  final String description;
  final Color accent;
  final String buttonLabel;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Container(
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(28),
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: <Color>[
              accent.withValues(alpha: 0.14),
              Colors.white,
            ],
          ),
        ),
        padding: const EdgeInsets.all(22),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              title,
              style: Theme.of(context).textTheme.headlineMedium,
            ),
            const SizedBox(height: 10),
            Text(description),
            const SizedBox(height: 18),
            FilledButton.tonal(
              onPressed: onPressed,
              child: Text(buttonLabel),
            ),
          ],
        ),
      ),
    );
  }
}

class _JoinActionCard extends StatelessWidget {
  const _JoinActionCard({
    required this.controller,
    required this.accent,
    required this.activeServer,
    required this.onQuickJoin,
    required this.onOpenJoinFlow,
  });

  final TextEditingController controller;
  final Color accent;
  final Uri? activeServer;
  final VoidCallback onQuickJoin;
  final VoidCallback onOpenJoinFlow;

  @override
  Widget build(BuildContext context) {
    final Uri? resolvedServer = activeServer;

    return Card(
      child: Container(
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(28),
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: <Color>[
              accent.withValues(alpha: 0.14),
              Colors.white,
            ],
          ),
        ),
        padding: const EdgeInsets.all(22),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              'Join a room',
              style: Theme.of(context).textTheme.headlineMedium,
            ),
            const SizedBox(height: 10),
            Text(
              activeServer == null
                  ? 'Paste a room invite or web join link. If you only have the slug, the join screen will still ask for the self-hosted server.'
                  : 'Paste a room invite, web join link, or room slug to jump into the guest join flow without leaving landing first.',
            ),
            const SizedBox(height: 16),
            TextField(
              controller: controller,
              decoration: const InputDecoration(
                labelText: 'Invite or room slug',
                hintText:
                    'kiltertogether://join?... / https://.../join/... / room-slug',
              ),
              textInputAction: TextInputAction.go,
              onSubmitted: (_) => onQuickJoin(),
            ),
            const SizedBox(height: 10),
            if (activeServer != null)
              Text(
                'Active server: ${describeServer(resolvedServer!)}',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            const SizedBox(height: 18),
            Row(
              children: <Widget>[
                Expanded(
                  child: FilledButton.tonal(
                    onPressed: onQuickJoin,
                    child: const Text('Quick join'),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: OutlinedButton(
                    onPressed: onOpenJoinFlow,
                    child: const Text('Open join flow'),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _RecentRoomTile extends ConsumerWidget {
  const _RecentRoomTile({
    required this.room,
    this.showRemove = false,
    this.onTap,
  });

  final RecentRoom room;
  final bool showRemove;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final String roomLabel = room.roomName ?? 'Room ${room.slug}';
    final String providerLabel = _providerLabel(room.providerId);
    final String surfaceLabel = (room.surfaceName ?? '').trim().isEmpty
        ? 'Surface not chosen yet'
        : room.surfaceName!;
    final String lastSeen = _formatRelativeTime(room.lastVisitedAt);

    return Card(
      child: InkWell(
        borderRadius: BorderRadius.circular(28),
        onTap: onTap ??
            () => context.goNamed(
                  'room',
                  queryParameters: <String, String>{
                    'server': room.server,
                    'slug': room.slug,
                  },
                ),
        child: Padding(
          padding: const EdgeInsets.all(18),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Wrap(
                          spacing: 8,
                          runSpacing: 8,
                          crossAxisAlignment: WrapCrossAlignment.center,
                          children: <Widget>[
                            Text(
                              roomLabel,
                              style: Theme.of(context).textTheme.titleLarge,
                            ),
                            if (room.pinned)
                              Container(
                                padding: const EdgeInsets.symmetric(
                                  horizontal: 10,
                                  vertical: 4,
                                ),
                                decoration: BoxDecoration(
                                  color: const Color(0xFFCCFBF1),
                                  borderRadius: BorderRadius.circular(999),
                                ),
                                child: Row(
                                  mainAxisSize: MainAxisSize.min,
                                  children: const <Widget>[
                                    Icon(
                                      Icons.push_pin,
                                      size: 12,
                                      color: Color(0xFF115E59),
                                    ),
                                    SizedBox(width: 4),
                                    Text(
                                      'Pinned',
                                      style: TextStyle(
                                        fontSize: 11,
                                        fontWeight: FontWeight.w600,
                                        color: Color(0xFF115E59),
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                          ],
                        ),
                        const SizedBox(height: 6),
                        Text(
                          '$providerLabel · ${room.slug}',
                          style:
                              Theme.of(context).textTheme.bodySmall?.copyWith(
                                    letterSpacing: 0.4,
                                  ),
                        ),
                      ],
                    ),
                  ),
                  Row(
                    mainAxisSize: MainAxisSize.min,
                    children: <Widget>[
                      IconButton(
                        onPressed: () => unawaited(
                          ref
                              .read(appPrefsControllerProvider.notifier)
                              .togglePinnedRecentRoom(
                                server: normalizeServerUri(room.server),
                                slug: room.slug,
                              ),
                        ),
                        icon: Icon(
                          room.pinned
                              ? Icons.push_pin
                              : Icons.push_pin_outlined,
                        ),
                      ),
                      if (showRemove)
                        IconButton(
                          onPressed: () => unawaited(
                            ref
                                .read(appPrefsControllerProvider.notifier)
                                .removeRecentRoom(
                                  server: normalizeServerUri(room.server),
                                  slug: room.slug,
                                ),
                          ),
                          icon: const Icon(Icons.delete_outline),
                        ),
                    ],
                  ),
                ],
              ),
              const SizedBox(height: 12),
              Wrap(
                spacing: 8,
                runSpacing: 6,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: <Widget>[
                  Text(surfaceLabel),
                  if (room.angle != null)
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                      decoration: BoxDecoration(
                        color: const Color(0xFFE0F2FE),
                        borderRadius: BorderRadius.circular(999),
                      ),
                      child: Text('@ ${room.angle}°', style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: Color(0xFF0369A1))),
                    ),
                  if (room.climbCount != null && room.climbCount! > 0)
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                      decoration: BoxDecoration(
                        color: const Color(0xFFF0FDF4),
                        borderRadius: BorderRadius.circular(999),
                      ),
                      child: Text('${room.climbCount} climbs', style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: Color(0xFF166534))),
                    ),
                ],
              ),
              const SizedBox(height: 4),
              Text(
                describeServer(normalizeServerUri(room.server)),
                style: Theme.of(context).textTheme.bodySmall,
              ),
              const SizedBox(height: 14),
              Row(
                children: <Widget>[
                  Expanded(
                    child: Text(
                      'Last seen $lastSeen',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ),
                  if (room.rematchConfig != null) ...<Widget>[
                    const SizedBox(width: 8),
                    OutlinedButton(
                      onPressed: () {
                        final Map<String, dynamic> cfg = room.rematchConfig!;
                        final ProviderSurface surface = ProviderSurface.fromJson(
                          (cfg['surface'] as Map<String, dynamic>?) ?? <String, dynamic>{},
                        );
                        final PendingRoomSeed seed = PendingRoomSeed(
                          providerId: cfg['provider_id'] as String? ?? room.providerId,
                          surface: surface,
                          climbs: const <ProviderClimb>[],
                          createdAt: DateTime.now().toUtc().toIso8601String(),
                          title: cfg['room_name'] as String?,
                        );
                        unawaited(ref.read(appPrefsControllerProvider.notifier).setPendingRoomSeed(seed));
                        context.goNamed('create-room');
                      },
                      child: const Text('Rematch'),
                    ),
                  ],
                  const SizedBox(width: 8),
                  OutlinedButton(
                    onPressed: onTap ??
                        () => context.goNamed(
                              'room',
                              queryParameters: <String, String>{
                                'server': room.server,
                                'slug': room.slug,
                              },
                            ),
                    child: const Text('Open room'),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _RecentSessionTile extends StatelessWidget {
  const _RecentSessionTile({
    required this.session,
    required this.server,
  });

  final SessionSummary session;
  final Uri? server;

  @override
  Widget build(BuildContext context) {
    final SessionSummaryClimb? topClimb =
        session.topVoted.isEmpty ? null : session.topVoted.first;
    final int topVotes = topClimb?.voteCount ?? 0;

    return Card(
      child: InkWell(
        borderRadius: BorderRadius.circular(28),
        onTap: server == null || session.recapShareId == null
            ? null
            : () => context.goNamed(
                  'recap',
                  queryParameters: <String, String>{
                    'server': server.toString(),
                    'share_id': session.recapShareId!,
                  },
                ),
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Row(
                children: <Widget>[
                  Expanded(
                    child: Text(
                      session.roomName ?? session.roomSlug,
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                  ),
                  if (session.recapShareId != null)
                    const Icon(Icons.chevron_right),
                ],
              ),
              const SizedBox(height: 6),
              Text(
                [
                  session.providerId,
                  if ((session.surfaceName ?? '').isNotEmpty)
                    session.surfaceName!,
                  '${session.participantCount} people',
                ].join(' · '),
              ),
              const SizedBox(height: 14),
              Row(
                children: <Widget>[
                  Expanded(
                    child: _SessionStatCard(
                      title: 'Top fist-bumped',
                      value: topClimb?.climb.name ?? 'No fist bumps recorded',
                      supportingText: topVotes > 0
                          ? '$topVotes fist bump${topVotes == 1 ? '' : 's'}'
                          : 'No fist bumps captured',
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: _SessionStatCard(
                      title: 'Wrap-up',
                      value:
                          '${session.finalQueue.length} queued · ${session.finalists.length} finalists',
                      supportingText:
                          'Closed ${MaterialLocalizations.of(context).formatShortDate(session.closedAt.toLocal())}',
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _SessionStatCard extends StatelessWidget {
  const _SessionStatCard({
    required this.title,
    required this.value,
    required this.supportingText,
  });

  final String title;
  final String value;
  final String supportingText;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: const Color(0xFFF8FAFC),
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: const Color(0xFFE2E8F0)),
      ),
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(
            title,
            style: Theme.of(context).textTheme.bodySmall,
          ),
          const SizedBox(height: 6),
          Text(
            value,
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 4),
          Text(supportingText),
        ],
      ),
    );
  }
}

class _RecentRoomsSheet extends ConsumerWidget {
  const _RecentRoomsSheet();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final AppPrefs prefs = ref.watch(appPrefsControllerProvider).valueOrNull ??
        AppPrefs.defaults();

    return SafeArea(
      top: false,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              'Recent rooms',
              style: Theme.of(context).textTheme.displayLarge,
            ),
            const SizedBox(height: 8),
            Text(
              'Showing up to the latest ${prefs.recentRooms.length} saved room visits on this device.',
              style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                    color: const Color(0xFF3E5A57),
                  ),
            ),
            const SizedBox(height: 16),
            Flexible(
              child: ListView(
                shrinkWrap: true,
                children: prefs.recentRooms
                    .map(
                      (RecentRoom room) => Padding(
                        padding: const EdgeInsets.only(bottom: 10),
                        child: _RecentRoomTile(
                          room: room,
                          showRemove: true,
                          onTap: () {
                            Navigator.of(context).pop();
                            context.goNamed(
                              'room',
                              queryParameters: <String, String>{
                                'server': room.server,
                                'slug': room.slug,
                              },
                            );
                          },
                        ),
                      ),
                    )
                    .toList(growable: false),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
