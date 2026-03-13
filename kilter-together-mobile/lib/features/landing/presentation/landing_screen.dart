import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/models/app_prefs_models.dart';
import '../../../core/models/product_models.dart';
import '../../../core/models/session_models.dart';
import '../../../core/network/api_client.dart';
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

class LandingScreen extends ConsumerWidget {
  const LandingScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final AppPrefs prefs = ref.watch(appPrefsControllerProvider).valueOrNull ??
        AppPrefs.defaults();
    final AsyncValue<Uri?> activeServer = ref.watch(_landingServerProvider);
    final AsyncValue<List<SessionSummary>> recentSessions =
        ref.watch(_recentSessionsProvider);

    return GradientScaffold(
      title: 'Kilter Together',
      subtitle:
          'Host, join, and run collaborative board sessions from a native mobile client.',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          _ActionCard(
            title: 'Create a room',
            description:
                'Authenticate the provider account, open a room, and share the invite from this phone.',
            accent: const Color(0xFF0F766E),
            buttonLabel: 'Host session',
            onPressed: () => context.goNamed('create-room'),
          ),
          const SizedBox(height: 14),
          _ActionCard(
            title: 'Join a room',
            description:
                'Paste or scan a mobile invite that already includes the self-hosted server address.',
            accent: const Color(0xFF4D7C0F),
            buttonLabel: 'Join invite',
            onPressed: () => context.goNamed('join-room'),
          ),
          const SizedBox(height: 14),
          _ActionCard(
            title: 'Solo browse',
            description:
                'Open Kilter or provider-backed solo planning, keep a shortlist, and seed new rooms.',
            accent: const Color(0xFF0369A1),
            buttonLabel: 'Open solo mode',
            onPressed: () => context.goNamed('solo-entry'),
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
          Text(
            'Recent rooms',
            style: Theme.of(context).textTheme.titleLarge,
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
              children: prefs.recentRooms
                  .take(6)
                  .map(
                    (RecentRoom room) => Padding(
                      padding: const EdgeInsets.only(bottom: 10),
                      child: Card(
                        child: ListTile(
                          title: Text(room.roomName ?? room.slug),
                          subtitle: Text(
                            [
                              room.providerId,
                              if ((room.surfaceName ?? '').isNotEmpty)
                                room.surfaceName!,
                              describeServer(normalizeServerUri(room.server)),
                            ].join(' · '),
                          ),
                          trailing: IconButton(
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
                          onTap: () => context.goNamed(
                            'room',
                            queryParameters: <String, String>{
                              'server': room.server,
                              'slug': room.slug,
                            },
                          ),
                        ),
                      ),
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
