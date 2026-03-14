import 'dart:io';
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/models/app_prefs_models.dart';
import '../../../core/models/board_models.dart';
import '../../../core/models/catalog_models.dart';
import '../../../core/models/provider_models.dart';
import '../../../core/models/session_models.dart';
import '../../../core/network/api_client.dart';
import '../../../core/presentation/flow_guide_sheet.dart';
import '../../../core/presentation/gradient_scaffold.dart';
import '../../../core/storage/app_prefs_controller.dart';
import '../../../core/storage/offline_kilter_catalog_controller.dart';
import '../../../core/storage/offline_kilter_catalog_repository.dart';
import '../../../core/storage/session_repository.dart';

final _soloEntryDataProvider =
    FutureProvider.autoDispose<_SoloEntryData>((Ref ref) async {
  final SessionRepository sessionRepository =
      ref.read(sessionRepositoryProvider);
  final ApiClient apiClient = ref.read(apiClientProvider);
  final OfflineKilterCatalogState catalogState =
      ref.watch(offlineKilterCatalogControllerProvider);
  final OfflineKilterCatalogRepository catalogRepository =
      ref.read(offlineKilterCatalogRepositoryProvider);
  final Uri? server = await sessionRepository.loadActiveServer();
  if (server == null) {
    return const _SoloEntryData(
      boards: <BoardOption>[],
      providers: <ProviderCapability>[],
      boardPreviewPaths: <String, String>{},
    );
  }

  final List<ProviderCapability> providers =
      await apiClient.getProviderCapabilities(server);
  final CatalogStatus catalogStatus = catalogState.status;
  final List<BoardOption> boards = catalogStatus.matchesServer(server)
      ? await catalogRepository.getBoards()
      : const <BoardOption>[];
  final Map<String, String> boardPreviewPaths = <String, String>{};
  for (final BoardOption board in boards) {
    final String? previewPath = await catalogRepository
        .resolveImagePath(board.previewImageFilename ?? '');
    if (previewPath != null) {
      boardPreviewPaths['${board.id}'] = previewPath;
    }
  }
  return _SoloEntryData(
    server: server,
    boards: boards,
    boardPreviewPaths: boardPreviewPaths,
    catalogStatus: catalogStatus,
    providers: providers
        .where((ProviderCapability item) => item.soloSupported)
        .toList(growable: false),
  );
});

const FlowGuideContent _soloEntryGuide = FlowGuideContent(
  eyebrow: 'Solo guide',
  title: 'Plan climbs without opening a room',
  summary:
      'Solo mode is the device-local planning lane. Use it to browse boards, save filters, and build favorites or shortlists before you decide to host a live session.',
  sections: <FlowGuideSection>[
    FlowGuideSection(
      title: 'Start from the active server',
      body:
          'Solo browse reads boards and provider-backed catalogs from the currently remembered self-hosted server, so point the app at the right node first.',
    ),
    FlowGuideSection(
      title: 'Keep planning state on-device',
      body:
          'Favorites, shortlist entries, and saved filters stay local on this phone so you can return later without accounts or cloud sync.',
    ),
    FlowGuideSection(
      title: 'Turn solo work into a room later',
      body:
          'When you are ready to climb with others, reuse the shortlist or saved plan seed to create a room with the same provider and surface context.',
    ),
  ],
  completionLabel: 'Mark solo guide complete',
);

class SoloEntryScreen extends ConsumerStatefulWidget {
  const SoloEntryScreen({super.key});

  @override
  ConsumerState<SoloEntryScreen> createState() => _SoloEntryScreenState();
}

class _SoloEntryScreenState extends ConsumerState<SoloEntryScreen> {
  bool _autoGuideAttempted = false;

  void _maybeAutoOpenGuide(AppPrefs prefs) {
    if (_autoGuideAttempted ||
        !prefs.settings.autoGuidesEnabled ||
        prefs.guidedTour.activeBranch != 'solo' ||
        prefs.guidedTour.soloCompleted) {
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
      content: _soloEntryGuide,
      completed: prefs.guidedTour.soloCompleted,
    );
    if (result != FlowGuideResult.completed || !mounted) {
      return;
    }
    await ref.read(appPrefsControllerProvider.notifier).completeGuideBranch(
          'solo',
        );
  }

  Future<void> _confirmDownloadCatalog(Uri server) async {
    final OfflineKilterCatalogController controller =
        ref.read(offlineKilterCatalogControllerProvider.notifier);
    try {
      final CatalogManifest manifest = await controller.fetchManifest(server);
      if (!mounted) {
        return;
      }
      final bool? confirmed = await showDialog<bool>(
        context: context,
        builder: (BuildContext dialogContext) {
          return AlertDialog(
            title: const Text('Download offline Kilter catalog?'),
            content: Text(
              'This stores about ${_formatStoredBytes(manifest.estimatedBytes)} on this device for ${manifest.climbCount} climbs. The catalog stays in app-managed storage and can be deleted later from Settings.',
            ),
            actions: <Widget>[
              TextButton(
                onPressed: () => Navigator.of(dialogContext).pop(false),
                child: const Text('Cancel'),
              ),
              FilledButton(
                onPressed: () => Navigator.of(dialogContext).pop(true),
                child: const Text('Download'),
              ),
            ],
          );
        },
      );
      if (confirmed == true && mounted) {
        await controller.download(server);
      }
    } catch (error) {
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('$error')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final AsyncValue<_SoloEntryData> entryData =
        ref.watch(_soloEntryDataProvider);
    final AsyncValue<AppPrefs> prefsValue =
        ref.watch(appPrefsControllerProvider);
    final OfflineKilterCatalogState catalogState =
        ref.watch(offlineKilterCatalogControllerProvider);
    final AppPrefs prefs = prefsValue.valueOrNull ?? AppPrefs.defaults();

    if (prefsValue.hasValue) {
      _maybeAutoOpenGuide(prefs);
    }

    return GradientScaffold(
      title: 'Solo Browse',
      subtitle:
          'Pick the Kilter dataset or a provider-backed solo catalog, then keep favorites, shortlist state, and reusable filters on-device.',
      actions: <Widget>[
        IconButton(
          onPressed: () => unawaited(_openGuide()),
          icon: const Icon(Icons.help_outline),
        ),
      ],
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          if (catalogState.errorMessage != null) ...<Widget>[
            _InlineMessageCard(
              title: 'Offline Kilter catalog',
              message: catalogState.errorMessage!,
              accent: const Color(0xFFB91C1C),
            ),
            const SizedBox(height: 14),
          ],
          if (catalogState.notice != null) ...<Widget>[
            _InlineMessageCard(
              title: 'Offline Kilter catalog',
              message: catalogState.notice!,
              accent: const Color(0xFF0F766E),
            ),
            const SizedBox(height: 14),
          ],
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
                  data.boards.toList(growable: false);
              final List<ProviderCapability> alternateProviders = data.providers
                  .where((ProviderCapability item) => item.id != 'kilter')
                  .toList(growable: false);

              return Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  _ServerCard(server: server),
                  const SizedBox(height: 14),
                  if (prefs.soloResume != null &&
                      data.catalogStatus.matchesServer(server) &&
                      prefs.soloResume!.boardId.isNotEmpty) ...<Widget>[
                    _ResumeCard(
                      resume: prefs.soloResume!,
                      server: server,
                    ),
                    const SizedBox(height: 14),
                  ],
                  if (data.catalogStatus.matchesServer(server))
                    _KilterBoardsCard(
                      boards: boards,
                      boardPreviewPaths: data.boardPreviewPaths,
                      server: server,
                      defaultAngle: prefs.lastKilterAngle,
                      defaultSort: prefs.settings.soloDefaultSort,
                    )
                  else
                    _OfflineCatalogGateCard(
                      server: server,
                      status: data.catalogStatus,
                      busy: catalogState.busy,
                      onDownload: () =>
                          unawaited(_confirmDownloadCatalog(server)),
                      onOpenSettings: () => context.goNamed('settings'),
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
    required this.boardPreviewPaths,
    this.catalogStatus = const CatalogStatus(installed: false),
  });

  final Uri? server;
  final List<BoardOption> boards;
  final List<ProviderCapability> providers;
  final Map<String, String> boardPreviewPaths;
  final CatalogStatus catalogStatus;
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
    required this.boardPreviewPaths,
    required this.server,
    required this.defaultAngle,
    required this.defaultSort,
  });

  final List<BoardOption> boards;
  final Map<String, String> boardPreviewPaths;
  final Uri server;
  final int defaultAngle;
  final String defaultSort;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
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
              'Browse every Kilter board from this server at $defaultAngle° by default. The board detail screen handles filters, shortlisted climbs, plan sharing, and room seeding.',
            ),
            if (boards.isNotEmpty) ...<Widget>[
              const SizedBox(height: 6),
              Text(
                '${boards.length} boards available on this server.',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
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
                                    child:
                                        boardPreviewPaths['${board.id}'] == null
                                            ? Container(
                                                color: const Color(0xFFE2E8F0),
                                                child: const Icon(
                                                    Icons.landscape_outlined),
                                              )
                                            : Image.file(
                                                File(boardPreviewPaths[
                                                    '${board.id}']!),
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

class _OfflineCatalogGateCard extends StatelessWidget {
  const _OfflineCatalogGateCard({
    required this.server,
    required this.status,
    required this.busy,
    required this.onDownload,
    required this.onOpenSettings,
  });

  final Uri server;
  final CatalogStatus status;
  final bool busy;
  final VoidCallback onDownload;
  final VoidCallback onOpenSettings;

  @override
  Widget build(BuildContext context) {
    final bool wrongServer =
        status.installed && status.sourceServer != server.toString();
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(22),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              'Offline Kilter catalog',
              style: Theme.of(context).textTheme.headlineMedium,
            ),
            const SizedBox(height: 8),
            Text(
              wrongServer
                  ? 'An offline Kilter catalog already exists for ${status.sourceServer}. Re-download it for ${describeServer(server)} before using Kilter solo browse here.'
                  : 'Download the Kilter catalog once to keep every climb on-device. After that, Kilter Together will only poll for new climbs while the app is in the foreground.',
            ),
            const SizedBox(height: 12),
            Text(
              status.estimatedBytes > 0
                  ? 'Estimated download: ${_formatBytes(status.estimatedBytes)}'
                  : 'The download size will appear once the catalog metadata is available.',
              style: Theme.of(context).textTheme.bodySmall,
            ),
            const SizedBox(height: 16),
            Row(
              children: <Widget>[
                Expanded(
                  child: FilledButton(
                    onPressed: busy ? null : onDownload,
                    child: Text(busy ? 'Downloading...' : 'Download catalog'),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: OutlinedButton(
                    onPressed: onOpenSettings,
                    child: const Text('Open settings'),
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

class _InlineMessageCard extends StatelessWidget {
  const _InlineMessageCard({
    required this.title,
    required this.message,
    required this.accent,
  });

  final String title;
  final String message;
  final Color accent;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Icon(Icons.circle, size: 12, color: accent),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Text(
                    title,
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  const SizedBox(height: 4),
                  Text(message),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

String _formatBytes(int bytes) {
  if (bytes <= 0) {
    return '0 B';
  }

  const List<String> units = <String>['B', 'KB', 'MB', 'GB'];
  double value = bytes.toDouble();
  int unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  final String formatted = value >= 10 || unitIndex == 0
      ? value.toStringAsFixed(0)
      : value.toStringAsFixed(1);
  return '$formatted ${units[unitIndex]}';
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

String _formatStoredBytes(int bytes) {
  if (bytes <= 0) {
    return '0 B';
  }

  const List<String> units = <String>['B', 'KB', 'MB', 'GB'];
  double value = bytes.toDouble();
  int unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  final String formatted = value >= 10 || unitIndex == 0
      ? value.toStringAsFixed(0)
      : value.toStringAsFixed(1);
  return '$formatted ${units[unitIndex]}';
}
