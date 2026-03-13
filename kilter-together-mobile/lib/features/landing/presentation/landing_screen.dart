import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/models/app_prefs_models.dart';
import '../../../core/models/product_models.dart';
import '../../../core/models/session_models.dart';
import '../../../core/network/api_client.dart';
import '../../../core/presentation/flow_guide_sheet.dart';
import '../../../core/presentation/gradient_scaffold.dart';
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

class LandingScreen extends ConsumerStatefulWidget {
  const LandingScreen({super.key});

  @override
  ConsumerState<LandingScreen> createState() => _LandingScreenState();
}

class _LandingScreenState extends ConsumerState<LandingScreen> {
  bool _autoGuideAttempted = false;

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

  @override
  Widget build(BuildContext context) {
    final AsyncValue<AppPrefs> prefsValue =
        ref.watch(appPrefsControllerProvider);
    final AppPrefs prefs = prefsValue.valueOrNull ?? AppPrefs.defaults();
    final AsyncValue<Uri?> activeServer = ref.watch(_landingServerProvider);
    final AsyncValue<List<SessionSummary>> recentSessions =
        ref.watch(_recentSessionsProvider);
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
        IconButton(
          onPressed: () => context.goNamed('settings'),
          icon: const Icon(Icons.tune),
        ),
      ],
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
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
          _ActionCard(
            title: 'Join a room',
            description:
                'Paste or scan a mobile invite that already includes the self-hosted server address.',
            accent: const Color(0xFF4D7C0F),
            buttonLabel: 'Join invite',
            onPressed: () => unawaited(
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
          const SizedBox(height: 14),
          _ActionCard(
            title: 'Settings',
            description:
                'Adjust local-only defaults for guides, recent rooms, provider memory, and solo behavior.',
            accent: const Color(0xFF7C3AED),
            buttonLabel: 'Open settings',
            onPressed: () => context.goNamed('settings'),
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
                        child: Card(
                          child: ListTile(
                            title: Text(session.roomName ?? session.roomSlug),
                            subtitle: Text(
                              [
                                session.providerId,
                                if ((session.surfaceName ?? '').isNotEmpty)
                                  session.surfaceName!,
                                '${session.participantCount} people',
                              ].join(' · '),
                            ),
                            trailing: session.recapShareId == null
                                ? null
                                : const Icon(Icons.chevron_right),
                            onTap: session.recapShareId == null
                                ? null
                                : () => context.goNamed(
                                      'recap',
                                      queryParameters: <String, String>{
                                        'server':
                                            activeServer.value!.toString(),
                                        'share_id': session.recapShareId!,
                                      },
                                    ),
                          ),
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
    return Card(
      child: ListTile(
        title: Text(room.roomName ?? room.slug),
        subtitle: Text(
          [
            room.providerId,
            if ((room.surfaceName ?? '').isNotEmpty) room.surfaceName!,
            describeServer(normalizeServerUri(room.server)),
          ].join(' · '),
        ),
        trailing: Row(
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
                room.pinned ? Icons.push_pin : Icons.push_pin_outlined,
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
        onTap: onTap ??
            () => context.goNamed(
                  'room',
                  queryParameters: <String, String>{
                    'server': room.server,
                    'slug': room.slug,
                  },
                ),
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
