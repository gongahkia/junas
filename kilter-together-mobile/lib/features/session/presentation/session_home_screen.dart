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
import '../../../core/presentation/gradient_scaffold.dart';
import '../../../core/presentation/runtime_status_banner.dart';
import '../../../core/storage/app_prefs_controller.dart';
import '../../../core/storage/session_repository.dart';

final _sessionServerProvider = FutureProvider.autoDispose<Uri?>((Ref ref) {
  return ref.read(sessionRepositoryProvider).loadActiveServer();
});

final _recentSessionsProvider =
    FutureProvider.autoDispose<List<SessionSummary>>((Ref ref) async {
  final Uri? server = await ref.watch(_sessionServerProvider.future);
  if (server == null) {
    return const <SessionSummary>[];
  }
  return ref
      .read(apiClientProvider)
      .getRecentSessions(server: server, limit: 4);
});

final _runtimeStatusProvider =
    FutureProvider.autoDispose<RuntimeStatus?>((Ref ref) async {
  final Uri? server = await ref.watch(_sessionServerProvider.future);
  if (server == null) {
    return null;
  }
  try {
    return await ref.read(apiClientProvider).getRuntimeStatus(server: server);
  } on ApiFailure {
    return null;
  }
});

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

class SessionHomeScreen extends ConsumerStatefulWidget {
  const SessionHomeScreen({super.key});
  @override
  ConsumerState<SessionHomeScreen> createState() => _SessionHomeScreenState();
}

class _SessionHomeScreenState extends ConsumerState<SessionHomeScreen> {
  final TextEditingController _quickJoinController = TextEditingController();

  @override
  void dispose() {
    _quickJoinController.dispose();
    super.dispose();
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
    if (!mounted) return;
    context.goNamed(
      'join-room',
      queryParameters: <String, String>{
        'slug': joinTarget.slug,
        if (joinTarget.server != null) 'server': joinTarget.server.toString(),
      },
    );
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

  void _showSnack(String message) {
    ScaffoldMessenger.of(context)
        .showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  Widget build(BuildContext context) {
    final AsyncValue<AppPrefs> prefsValue =
        ref.watch(appPrefsControllerProvider);
    final AppPrefs prefs = prefsValue.valueOrNull ?? AppPrefs.defaults();
    final AsyncValue<Uri?> activeServer = ref.watch(_sessionServerProvider);
    final AsyncValue<List<SessionSummary>> recentSessions =
        ref.watch(_recentSessionsProvider);
    final RuntimeStatus? runtimeStatus =
        ref.watch(_runtimeStatusProvider).valueOrNull;
    final List<RecentRoom> previewRecentRooms =
        prefs.recentRooms.take(3).toList(growable: false);

    return GradientScaffold(
      title: 'Session',
      subtitle: 'Host or join a collaborative climbing session.',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          if (runtimeStatus != null) ...<Widget>[
            RuntimeStatusBanner(status: runtimeStatus),
            const SizedBox(height: 14),
          ],
          // host / join action buttons
          Row(
            children: <Widget>[
              Expanded(
                child: FilledButton.icon(
                  onPressed: () async {
                    await ref
                        .read(appPrefsControllerProvider.notifier)
                        .queueGuideBranch('host');
                    if (!mounted) return;
                    context.goNamed('create-room');
                  },
                  icon: const Icon(Icons.add),
                  label: const Text('Host'),
                  style: FilledButton.styleFrom(
                    shape: const RoundedRectangleBorder(
                      borderRadius: BorderRadius.zero,
                    ),
                    backgroundColor: const Color(0xFF1A1A1A),
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: () async {
                    await ref
                        .read(appPrefsControllerProvider.notifier)
                        .queueGuideBranch('guest');
                    if (!mounted) return;
                    context.goNamed('join-room');
                  },
                  icon: const Icon(Icons.qr_code_scanner_rounded),
                  label: const Text('Join'),
                  style: OutlinedButton.styleFrom(
                    shape: const RoundedRectangleBorder(
                      borderRadius: BorderRadius.zero,
                    ),
                    side: const BorderSide(color: Color(0xFFD4D4D4)),
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          // quick join text field
          Container(
            decoration: BoxDecoration(
              color: const Color(0xFFF5F5F5),
              border: Border.all(color: const Color(0xFFD4D4D4)),
              borderRadius: BorderRadius.zero,
            ),
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                TextField(
                  controller: _quickJoinController,
                  decoration: const InputDecoration(
                    labelText: 'Invite or room slug',
                    hintText:
                        'kiltertogether://join?... / https://.../join/... / room-slug',
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.zero,
                    ),
                    enabledBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.zero,
                      borderSide: BorderSide(color: Color(0xFFD4D4D4)),
                    ),
                    focusedBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.zero,
                      borderSide: BorderSide(color: Color(0xFF525252)),
                    ),
                  ),
                  textInputAction: TextInputAction.go,
                  onSubmitted: (_) =>
                      unawaited(_startQuickJoin(activeServer.valueOrNull)),
                ),
                const SizedBox(height: 12),
                Row(
                  children: <Widget>[
                    Expanded(
                      child: FilledButton(
                        onPressed: () => unawaited(
                          _startQuickJoin(activeServer.valueOrNull),
                        ),
                        style: FilledButton.styleFrom(
                          shape: const RoundedRectangleBorder(
                            borderRadius: BorderRadius.zero,
                          ),
                          backgroundColor: const Color(0xFF525252),
                        ),
                        child: const Text('Quick join'),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: OutlinedButton.icon(
                        onPressed: () async {
                          await ref
                              .read(appPrefsControllerProvider.notifier)
                              .queueGuideBranch('guest');
                          if (!mounted) return;
                          context.goNamed('join-room');
                        },
                        icon: const Icon(Icons.qr_code_scanner_rounded,
                            size: 16),
                        label: const Text('Scan QR'),
                        style: OutlinedButton.styleFrom(
                          shape: const RoundedRectangleBorder(
                            borderRadius: BorderRadius.zero,
                          ),
                          side: const BorderSide(color: Color(0xFFD4D4D4)),
                        ),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(height: 24),
          // recent rooms section
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
            Container(
              width: double.infinity,
              decoration: BoxDecoration(
                color: const Color(0xFFF5F5F5),
                border: Border.all(color: const Color(0xFFD4D4D4)),
                borderRadius: BorderRadius.zero,
              ),
              padding: const EdgeInsets.all(20),
              child: const Text('Recent rooms are disabled in settings.'),
            )
          else if (prefs.recentRooms.isEmpty)
            Container(
              width: double.infinity,
              decoration: BoxDecoration(
                color: const Color(0xFFF5F5F5),
                border: Border.all(color: const Color(0xFFD4D4D4)),
                borderRadius: BorderRadius.zero,
              ),
              padding: const EdgeInsets.all(20),
              child: const Text(
                'No recent rooms saved on this device yet. Your next room visit will appear here.',
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
          const SizedBox(height: 24),
          // recent sessions section
          Text(
            'Recent sessions',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 12),
          recentSessions.when(
            data: (List<SessionSummary> sessions) {
              if (sessions.isEmpty) {
                return Container(
                  width: double.infinity,
                  decoration: BoxDecoration(
                    color: const Color(0xFFF5F5F5),
                    border: Border.all(color: const Color(0xFFD4D4D4)),
                    borderRadius: BorderRadius.zero,
                  ),
                  padding: const EdgeInsets.all(20),
                  child: const Text(
                    'No recent sessions were returned for the active server yet.',
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
            error: (Object error, StackTrace stackTrace) => Container(
              width: double.infinity,
              decoration: BoxDecoration(
                color: const Color(0xFFF5F5F5),
                border: Border.all(color: const Color(0xFFD4D4D4)),
                borderRadius: BorderRadius.zero,
              ),
              padding: const EdgeInsets.all(20),
              child: Text('$error'),
            ),
            loading: () => Container(
              width: double.infinity,
              decoration: BoxDecoration(
                color: const Color(0xFFF5F5F5),
                border: Border.all(color: const Color(0xFFD4D4D4)),
                borderRadius: BorderRadius.zero,
              ),
              padding: const EdgeInsets.all(20),
              child: const LinearProgressIndicator(),
            ),
          ),
        ],
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

    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        border: Border.all(color: const Color(0xFFD4D4D4)),
        borderRadius: BorderRadius.zero,
      ),
      child: InkWell(
        borderRadius: BorderRadius.zero,
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
                                decoration: const BoxDecoration(
                                  color: Color(0xFFE5E5E5),
                                  borderRadius: BorderRadius.zero,
                                ),
                                child: Row(
                                  mainAxisSize: MainAxisSize.min,
                                  children: const <Widget>[
                                    Icon(
                                      Icons.push_pin,
                                      size: 12,
                                      color: Color(0xFF525252),
                                    ),
                                    SizedBox(width: 4),
                                    Text(
                                      'Pinned',
                                      style: TextStyle(
                                        fontSize: 11,
                                        fontWeight: FontWeight.w600,
                                        color: Color(0xFF525252),
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                          ],
                        ),
                        const SizedBox(height: 6),
                        Text(
                          '$providerLabel \u00b7 ${room.slug}',
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
                      padding: const EdgeInsets.symmetric(
                          horizontal: 8, vertical: 2),
                      decoration: const BoxDecoration(
                        color: Color(0xFFE5E5E5),
                        borderRadius: BorderRadius.zero,
                      ),
                      child: Text('@ ${room.angle}\u00b0',
                          style: const TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.w600,
                              color: Color(0xFF525252))),
                    ),
                  if (room.climbCount != null && room.climbCount! > 0)
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 8, vertical: 2),
                      decoration: const BoxDecoration(
                        color: Color(0xFFE5E5E5),
                        borderRadius: BorderRadius.zero,
                      ),
                      child: Text('${room.climbCount} climbs',
                          style: const TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.w600,
                              color: Color(0xFF525252))),
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
                        final ProviderSurface surface =
                            ProviderSurface.fromJson(
                          (cfg['surface'] as Map<String, dynamic>?) ??
                              <String, dynamic>{},
                        );
                        final PendingRoomSeed seed = PendingRoomSeed(
                          providerId: cfg['provider_id'] as String? ??
                              room.providerId,
                          surface: surface,
                          climbs: const <ProviderClimb>[],
                          createdAt:
                              DateTime.now().toUtc().toIso8601String(),
                          title: cfg['room_name'] as String?,
                        );
                        unawaited(ref
                            .read(appPrefsControllerProvider.notifier)
                            .setPendingRoomSeed(seed));
                        context.goNamed('create-room');
                      },
                      style: OutlinedButton.styleFrom(
                        shape: const RoundedRectangleBorder(
                          borderRadius: BorderRadius.zero,
                        ),
                        side: const BorderSide(color: Color(0xFFD4D4D4)),
                      ),
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
                    style: OutlinedButton.styleFrom(
                      shape: const RoundedRectangleBorder(
                        borderRadius: BorderRadius.zero,
                      ),
                      side: const BorderSide(color: Color(0xFFD4D4D4)),
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

    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        border: Border.all(color: const Color(0xFFD4D4D4)),
        borderRadius: BorderRadius.zero,
      ),
      child: InkWell(
        borderRadius: BorderRadius.zero,
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
                ].join(' \u00b7 '),
              ),
              const SizedBox(height: 14),
              Row(
                children: <Widget>[
                  Expanded(
                    child: _SessionStatCard(
                      title: 'Top fist-bumped',
                      value:
                          topClimb?.climb.name ?? 'No fist bumps recorded',
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
                          '${session.finalQueue.length} queued \u00b7 ${session.finalists.length} finalists',
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
        color: const Color(0xFFF5F5F5),
        borderRadius: BorderRadius.zero,
        border: Border.all(color: const Color(0xFFD4D4D4)),
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
                    color: const Color(0xFF737373),
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
