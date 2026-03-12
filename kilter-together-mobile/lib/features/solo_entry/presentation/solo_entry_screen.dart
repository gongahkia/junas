import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/models/app_prefs_models.dart';
import '../../../core/models/board_models.dart';
import '../../../core/models/provider_models.dart';
import '../../../core/models/session_models.dart';
import '../../../core/network/api_client.dart';
import '../../../core/presentation/gradient_scaffold.dart';
import '../../../core/storage/app_prefs_controller.dart';
import '../../../core/storage/session_repository.dart';

final _soloEntryDataProvider =
    FutureProvider.autoDispose<_SoloEntryData>((Ref ref) async {
  final SessionRepository sessionRepository =
      ref.read(sessionRepositoryProvider);
  final ApiClient apiClient = ref.read(apiClientProvider);
  final Uri? server = await sessionRepository.loadActiveServer();
  if (server == null) {
    return const _SoloEntryData(
      boards: <BoardOption>[],
      providers: <ProviderCapability>[],
    );
  }

  final List<BoardOption> boards = await apiClient.getBoards(server);
  final List<ProviderCapability> providers =
      await apiClient.getProviderCapabilities(server);
  return _SoloEntryData(
    server: server,
    boards: boards,
    providers: providers
        .where((ProviderCapability item) => item.soloSupported)
        .toList(growable: false),
  );
});

class SoloEntryScreen extends ConsumerWidget {
  const SoloEntryScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final AsyncValue<_SoloEntryData> entryData =
        ref.watch(_soloEntryDataProvider);
    final AppPrefs prefs = ref.watch(appPrefsControllerProvider).valueOrNull ??
        AppPrefs.defaults();

    return GradientScaffold(
      title: 'Solo Browse',
      subtitle:
          'Pick the Kilter dataset or a provider-backed solo catalog, then keep favorites, shortlist state, and reusable filters on-device.',
      actions: <Widget>[
        IconButton(
          onPressed: () => context.goNamed('settings'),
          icon: const Icon(Icons.tune),
        ),
        IconButton(
          onPressed: () => context.goNamed('landing'),
          icon: const Icon(Icons.close),
        ),
      ],
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          _SavedStateCard(prefs: prefs),
          const SizedBox(height: 14),
          entryData.when(
            data: (_SoloEntryData data) {
              if (data.server == null) {
                return _MissingServerCard(
                  onCreateRoom: () => context.goNamed('create-room'),
                  onJoinRoom: () => context.goNamed('join-room'),
                );
              }

              final Uri server = data.server!;
              final List<BoardOption> boards =
                  data.boards.take(4).toList(growable: false);
              final List<ProviderCapability> alternateProviders = data.providers
                  .where((ProviderCapability item) => item.id != 'kilter')
                  .toList(growable: false);

              return Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  _ServerCard(server: server),
                  const SizedBox(height: 14),
                  if (prefs.soloResume != null &&
                      prefs.soloResume!.boardId.isNotEmpty) ...<Widget>[
                    _ResumeCard(
                      resume: prefs.soloResume!,
                      server: server,
                    ),
                    const SizedBox(height: 14),
                  ],
                  _KilterBoardsCard(
                    boards: boards,
                    server: server,
                    defaultAngle: prefs.lastKilterAngle,
                    defaultSort: prefs.settings.soloDefaultSort,
                  ),
                  if (alternateProviders.isNotEmpty) ...<Widget>[
                    const SizedBox(height: 14),
                    _ProviderCardGrid(
                      providers: alternateProviders,
                      server: server,
                    ),
                  ],
                ],
              );
            },
            error: (Object error, StackTrace stackTrace) {
              return Card(
                child: Padding(
                  padding: const EdgeInsets.all(22),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      Text(
                        'Solo browse is not ready yet',
                        style: Theme.of(context).textTheme.headlineMedium,
                      ),
                      const SizedBox(height: 10),
                      Text('$error'),
                      const SizedBox(height: 18),
                      FilledButton.tonal(
                        onPressed: () => ref.invalidate(_soloEntryDataProvider),
                        child: const Text('Retry'),
                      ),
                    ],
                  ),
                ),
              );
            },
            loading: () {
              return const Card(
                child: Padding(
                  padding: EdgeInsets.all(28),
                  child: Center(child: CircularProgressIndicator()),
                ),
              );
            },
          ),
        ],
      ),
    );
  }
}

class _SoloEntryData {
  const _SoloEntryData({
    this.server,
    required this.boards,
    required this.providers,
  });

  final Uri? server;
  final List<BoardOption> boards;
  final List<ProviderCapability> providers;
}

class _SavedStateCard extends StatelessWidget {
  const _SavedStateCard({
    required this.prefs,
  });

  final AppPrefs prefs;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(22),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              'Saved on this device',
              style: Theme.of(context).textTheme.headlineMedium,
            ),
            const SizedBox(height: 8),
            const Text(
              'Favorites, shortlist entries, and filter presets stay local so you can jump back into planning without accounts or sync.',
            ),
            const SizedBox(height: 18),
            Wrap(
              spacing: 10,
              runSpacing: 10,
              children: <Widget>[
                _CountChip(
                    label: 'Favorites', value: prefs.soloFavorites.length),
                _CountChip(
                    label: 'Shortlist', value: prefs.soloShortlist.length),
                _CountChip(
                    label: 'Saved filters',
                    value: prefs.savedSoloFilters.length),
              ],
            ),
            if (prefs.savedSoloFilters.isNotEmpty ||
                prefs.soloFavorites.isNotEmpty ||
                prefs.soloShortlist.isNotEmpty) ...<Widget>[
              const SizedBox(height: 18),
              Column(
                children: <Widget>[
                  if (prefs.savedSoloFilters.isNotEmpty)
                    _SavedLinkTile(
                      title: prefs.savedSoloFilters.first.label,
                      subtitle: 'Open latest saved filter',
                      onTap: () =>
                          _openPreset(context, prefs.savedSoloFilters.first),
                    ),
                  if (prefs.soloFavorites.isNotEmpty)
                    _SavedLinkTile(
                      title: prefs.soloFavorites.first.climbName,
                      subtitle: 'Open latest favorite',
                      onTap: () =>
                          _openSavedClimb(context, prefs.soloFavorites.first),
                    ),
                  if (prefs.soloShortlist.isNotEmpty)
                    _SavedLinkTile(
                      title: prefs.soloShortlist.first.climbName,
                      subtitle: 'Open latest shortlist entry',
                      onTap: () =>
                          _openSavedClimb(context, prefs.soloShortlist.first),
                    ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }

  void _openPreset(BuildContext context, SoloFilterPreset preset) {
    context.goNamed(
      'solo-board',
      pathParameters: <String, String>{'boardId': preset.boardId},
      queryParameters: <String, String>{
        'angle': '${preset.angle}',
        'sort': preset.sort,
        if ((preset.q ?? '').isNotEmpty) 'q': preset.q!,
        if ((preset.setter ?? '').isNotEmpty) 'setter': preset.setter!,
        if ((preset.grade ?? '').isNotEmpty) 'grade': preset.grade!,
      },
    );
  }

  void _openSavedClimb(BuildContext context, SoloSavedClimb climb) {
    context.goNamed(
      'solo-board',
      pathParameters: <String, String>{'boardId': climb.boardId},
      queryParameters: <String, String>{
        'angle': '${climb.angle}',
        'sort': defaultClimbSort,
        'climb': climb.uuid,
      },
    );
  }
}

class _CountChip extends StatelessWidget {
  const _CountChip({
    required this.label,
    required this.value,
  });

  final String label;
  final int value;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: const Color(0xFFF0FDFA),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: const Color(0xFFB7E4DF)),
      ),
      child: Text('$value $label'),
    );
  }
}

class _SavedLinkTile extends StatelessWidget {
  const _SavedLinkTile({
    required this.title,
    required this.subtitle,
    required this.onTap,
  });

  final String title;
  final String subtitle;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      contentPadding: EdgeInsets.zero,
      title: Text(title),
      subtitle: Text(subtitle),
      trailing: const Icon(Icons.chevron_right),
      onTap: onTap,
    );
  }
}

class _MissingServerCard extends StatelessWidget {
  const _MissingServerCard({
    required this.onCreateRoom,
    required this.onJoinRoom,
  });

  final VoidCallback onCreateRoom;
  final VoidCallback onJoinRoom;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(22),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              'Pick a server first',
              style: Theme.of(context).textTheme.headlineMedium,
            ),
            const SizedBox(height: 8),
            const Text(
              'Solo browse needs the active self-hosted server because the board dataset, images, recap snapshots, and provider catalogs all come from that node.',
            ),
            const SizedBox(height: 18),
            Row(
              children: <Widget>[
                Expanded(
                  child: FilledButton(
                    onPressed: onCreateRoom,
                    child: const Text('Create room'),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: FilledButton.tonal(
                    onPressed: onJoinRoom,
                    child: const Text('Join room'),
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

class _ServerCard extends StatelessWidget {
  const _ServerCard({
    required this.server,
  });

  final Uri server;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(22),
        child: Row(
          children: <Widget>[
            Container(
              width: 46,
              height: 46,
              decoration: BoxDecoration(
                color: const Color(0xFF0F766E).withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(16),
              ),
              child: const Icon(Icons.dns, color: Color(0xFF0F766E)),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Text(
                    'Active server',
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                  const SizedBox(height: 4),
                  Text(describeServer(server)),
                  Text(
                    server.toString(),
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ResumeCard extends StatelessWidget {
  const _ResumeCard({
    required this.resume,
    required this.server,
  });

  final SoloResumeState resume;
  final Uri server;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(22),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              'Resume solo browse',
              style: Theme.of(context).textTheme.headlineMedium,
            ),
            const SizedBox(height: 8),
            Text(
              'Board ${resume.boardId} at ${resume.angle}°. Reopen the last selected filters and climb on ${describeServer(server)}.',
            ),
            const SizedBox(height: 18),
            FilledButton.tonal(
              onPressed: () => context.goNamed(
                'solo-board',
                pathParameters: <String, String>{'boardId': resume.boardId},
                queryParameters: <String, String>{
                  'server': server.toString(),
                  'angle': '${resume.angle}',
                  'sort': resume.sort,
                  if ((resume.q ?? '').isNotEmpty) 'q': resume.q!,
                  if ((resume.setter ?? '').isNotEmpty)
                    'setter': resume.setter!,
                  if ((resume.grade ?? '').isNotEmpty) 'grade': resume.grade!,
                  if ((resume.climb ?? '').isNotEmpty) 'climb': resume.climb!,
                },
              ),
              child: const Text('Resume'),
            ),
          ],
        ),
      ),
    );
  }
}

class _KilterBoardsCard extends ConsumerWidget {
  const _KilterBoardsCard({
    required this.boards,
    required this.server,
    required this.defaultAngle,
    required this.defaultSort,
  });

  final List<BoardOption> boards;
  final Uri server;
  final int defaultAngle;
  final String defaultSort;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final ApiClient apiClient = ref.read(apiClientProvider);

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(22),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              'Kilter boards',
              style: Theme.of(context).textTheme.headlineMedium,
            ),
            const SizedBox(height: 8),
            Text(
              'Open the local dataset at $defaultAngle° by default. The board detail screen handles filters, shortlisted climbs, plan sharing, and room seeding.',
            ),
            const SizedBox(height: 18),
            if (boards.isEmpty)
              const Text('No Kilter boards were returned by the server.')
            else
              Column(
                children: boards
                    .map(
                      (BoardOption board) => Padding(
                        padding: const EdgeInsets.only(bottom: 12),
                        child: InkWell(
                          borderRadius: BorderRadius.circular(24),
                          onTap: () => context.goNamed(
                            'solo-board',
                            pathParameters: <String, String>{
                              'boardId': '${board.id}'
                            },
                            queryParameters: <String, String>{
                              'server': server.toString(),
                              'angle': '$defaultAngle',
                              'sort': defaultSort,
                            },
                          ),
                          child: Ink(
                            decoration: BoxDecoration(
                              color: const Color(0xFFF8FFFD),
                              borderRadius: BorderRadius.circular(24),
                              border:
                                  Border.all(color: const Color(0xFFD1FAE5)),
                            ),
                            padding: const EdgeInsets.all(16),
                            child: Row(
                              children: <Widget>[
                                ClipRRect(
                                  borderRadius: BorderRadius.circular(18),
                                  child: SizedBox(
                                    width: 92,
                                    height: 64,
                                    child: board.previewImageFilename == null
                                        ? Container(
                                            color: const Color(0xFFE2E8F0),
                                            child: const Icon(
                                                Icons.landscape_outlined),
                                          )
                                        : Image.network(
                                            apiClient.getImageUrl(
                                              server: server,
                                              filename:
                                                  board.previewImageFilename!,
                                            ),
                                            fit: BoxFit.cover,
                                          ),
                                  ),
                                ),
                                const SizedBox(width: 14),
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: <Widget>[
                                      Text(
                                        board.kilterName,
                                        style: Theme.of(context)
                                            .textTheme
                                            .titleLarge,
                                      ),
                                      const SizedBox(height: 4),
                                      Text(board.name),
                                      const SizedBox(height: 4),
                                      Text(
                                        '${board.climbCount ?? 0} climbs',
                                        style: Theme.of(context)
                                            .textTheme
                                            .bodySmall,
                                      ),
                                    ],
                                  ),
                                ),
                                const Icon(Icons.chevron_right),
                              ],
                            ),
                          ),
                        ),
                      ),
                    )
                    .toList(growable: false),
              ),
          ],
        ),
      ),
    );
  }
}

class _ProviderCardGrid extends StatelessWidget {
  const _ProviderCardGrid({
    required this.providers,
    required this.server,
  });

  final List<ProviderCapability> providers;
  final Uri server;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(22),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              'Other solo providers',
              style: Theme.of(context).textTheme.headlineMedium,
            ),
            const SizedBox(height: 8),
            const Text(
              'Use live provider catalogs when you want gym and wall context instead of the local Kilter dataset.',
            ),
            const SizedBox(height: 18),
            Column(
              children: providers
                  .map(
                    (ProviderCapability provider) => Padding(
                      padding: const EdgeInsets.only(bottom: 12),
                      child: InkWell(
                        borderRadius: BorderRadius.circular(24),
                        onTap: () => context.goNamed(
                          'solo-provider',
                          pathParameters: <String, String>{
                            'providerId': provider.id
                          },
                          queryParameters: <String, String>{
                            'server': server.toString(),
                          },
                        ),
                        child: Ink(
                          decoration: BoxDecoration(
                            color: Colors.white,
                            borderRadius: BorderRadius.circular(24),
                            border: Border.all(color: const Color(0xFFE2E8F0)),
                          ),
                          padding: const EdgeInsets.all(18),
                          child: Row(
                            children: <Widget>[
                              Container(
                                width: 42,
                                height: 42,
                                decoration: BoxDecoration(
                                  color: const Color(0xFFE0F2FE),
                                  borderRadius: BorderRadius.circular(14),
                                ),
                                child: const Icon(Icons.travel_explore,
                                    color: Color(0xFF0369A1)),
                              ),
                              const SizedBox(width: 14),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: <Widget>[
                                    Text(
                                      provider.label,
                                      style: Theme.of(context)
                                          .textTheme
                                          .titleLarge,
                                    ),
                                    const SizedBox(height: 4),
                                    Text(
                                        'Hierarchy: ${provider.surfaceHierarchy}'),
                                  ],
                                ),
                              ),
                              const Icon(Icons.chevron_right),
                            ],
                          ),
                        ),
                      ),
                    ),
                  )
                  .toList(growable: false),
            ),
          ],
        ),
      ),
    );
  }
}
