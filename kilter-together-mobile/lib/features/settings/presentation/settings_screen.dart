import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/models/app_prefs_models.dart';
import '../../../core/models/catalog_models.dart';
import '../../../core/models/provider_models.dart';
import '../../../core/models/session_models.dart';
import '../../../core/presentation/climbing_loader.dart';
import '../../../core/presentation/gradient_scaffold.dart';
import '../../../core/provider/provider_registry.dart';
import '../../../core/storage/app_prefs_controller.dart';
import '../../../core/storage/offline_kilter_catalog_controller.dart';
import '../../../core/storage/session_repository.dart';

final _settingsActiveServerProvider =
    FutureProvider.autoDispose<Uri?>((Ref ref) {
  return ref.read(sessionRepositoryProvider).loadActiveServer();
});

class SettingsScreen extends ConsumerStatefulWidget {
  const SettingsScreen({super.key});

  @override
  ConsumerState<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends ConsumerState<SettingsScreen> {
  final TextEditingController _displayNameController = TextEditingController();
  final TextEditingController _roomTemplateController = TextEditingController();
  bool _hydrated = false;

  @override
  void dispose() {
    _displayNameController.dispose();
    _roomTemplateController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final AsyncValue<AppPrefs> prefsValue =
        ref.watch(appPrefsControllerProvider);
    final OfflineKilterCatalogState catalogState =
        ref.watch(offlineKilterCatalogControllerProvider);
    final OfflineKilterCatalogController catalogController =
        ref.read(offlineKilterCatalogControllerProvider.notifier);
    final Uri? activeServer =
        ref.watch(_settingsActiveServerProvider).valueOrNull;
    final VoidCallback? downloadCatalogAction;
    final VoidCallback? syncCatalogAction;
    if (activeServer == null) {
      downloadCatalogAction = null;
      syncCatalogAction = null;
    } else {
      final Uri catalogServer = activeServer;
      downloadCatalogAction = () => unawaited(
            _confirmDownloadCatalog(catalogServer),
          );
      syncCatalogAction = () => unawaited(
            catalogController.syncNow(catalogServer),
          );
    }
    final List<ProviderCapability> capabilities = providerRegistry
        .map((ProviderDescriptor descriptor) => descriptor.toCapability())
        .toList(growable: false);

    return GradientScaffold(
      title: 'Settings',
      subtitle:
          'Local-only preferences for display defaults, guidance, recent rooms, saved credentials, and solo behavior.',
      actions: <Widget>[
        IconButton(
          onPressed: () => context.goNamed('about'),
          icon: const Icon(Icons.info_outline),
        ),
      ],
      child: prefsValue.when(
        data: (AppPrefs prefs) {
          if (!_hydrated) {
            _hydrated = true;
            _displayNameController.text = prefs.savedDisplayName;
            _roomTemplateController.text = prefs.hostDefaults.roomNameTemplate;
          }

          final List<ProviderCapability> providerChoices = capabilities;
          final bool hasSavedCredentials =
              prefs.savedCredentials.providers.values.any(
            (SavedCredentialPreference item) => item.remember,
          );

          return Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              if (catalogState.errorMessage != null) ...<Widget>[
                _SettingsMessageCard(
                  message: catalogState.errorMessage!,
                  accent: const Color(0xFF404040),
                ),
                const SizedBox(height: 14),
              ],
              if (catalogState.notice != null) ...<Widget>[
                _SettingsMessageCard(
                  message: catalogState.notice!,
                  accent: const Color(0xFF1A1A1A),
                ),
                const SizedBox(height: 14),
              ],
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(22),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      Text(
                        'Experience',
                        style: Theme.of(context).textTheme.headlineMedium,
                      ),
                      const SizedBox(height: 12),
                      _ToggleTile(
                        label: 'Show onboarding guides automatically',
                        description:
                            'Auto-open the landing, host, guest, and solo help sheets until each branch is marked complete.',
                        value: prefs.settings.autoGuidesEnabled,
                        onChanged: (bool value) => unawaited(
                          ref
                              .read(appPrefsControllerProvider.notifier)
                              .updateSettings(
                                autoGuidesEnabled: value,
                              ),
                        ),
                      ),
                      _ToggleTile(
                        label: 'Enable tap cheers',
                        description:
                            'Let taps on the UI throw short celebratory overlays during active browsing.',
                        value: prefs.settings.clickCheersEnabled,
                        onChanged: (bool value) => unawaited(
                          ref
                              .read(appPrefsControllerProvider.notifier)
                              .updateSettings(
                                clickCheersEnabled: value,
                              ),
                        ),
                      ),
                      _ToggleTile(
                        label: 'Enable playful motion',
                        description:
                            'Allow branded motion and animated transitions across the mobile UI.',
                        value: prefs.settings.playfulMotionEnabled,
                        onChanged: (bool value) => unawaited(
                          ref
                              .read(appPrefsControllerProvider.notifier)
                              .updateSettings(
                                playfulMotionEnabled: value,
                              ),
                        ),
                      ),
                      _ToggleTile(
                        label: 'Save recent rooms',
                        description:
                            'Keep quick-return room cards on the landing page for this device.',
                        value: prefs.settings.recentRoomsEnabled,
                        onChanged: (bool value) => unawaited(
                          ref
                              .read(appPrefsControllerProvider.notifier)
                              .updateSettings(
                                recentRoomsEnabled: value,
                              ),
                        ),
                      ),
                      _ToggleTile(
                        label: 'Notify on current climb change',
                        description:
                            'Show a local notification when the room moves to a new climb while the app is in the background.',
                        value: prefs.settings.notifyOnClimbChange,
                        onChanged: (bool value) => unawaited(
                          ref
                              .read(appPrefsControllerProvider.notifier)
                              .updateSettings(
                                notifyOnClimbChange: value,
                              ),
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
                        'Defaults',
                        style: Theme.of(context).textTheme.headlineMedium,
                      ),
                      const SizedBox(height: 16),
                      TextField(
                        controller: _displayNameController,
                        decoration: const InputDecoration(
                          labelText: 'Preferred display name',
                          hintText: 'Gabriel, Spotter, Session host',
                        ),
                        onChanged: (String value) => unawaited(
                          ref
                              .read(appPrefsControllerProvider.notifier)
                              .rememberDisplayName(value),
                        ),
                      ),
                      const SizedBox(height: 12),
                      DropdownButtonFormField<String>(
                        initialValue: providerChoices.any(
                          (ProviderCapability item) =>
                              item.id == prefs.lastProviderId,
                        )
                            ? prefs.lastProviderId
                            : providerChoices.first.id,
                        decoration: const InputDecoration(
                          labelText: 'Default host provider',
                        ),
                        items: providerChoices
                            .map(
                              (ProviderCapability item) =>
                                  DropdownMenuItem<String>(
                                value: item.id,
                                child: Text(item.label),
                              ),
                            )
                            .toList(growable: false),
                        onChanged: (String? value) {
                          if (value == null) {
                            return;
                          }
                          unawaited(
                            ref
                                .read(appPrefsControllerProvider.notifier)
                                .rememberLastProvider(value),
                          );
                        },
                      ),
                      const SizedBox(height: 12),
                      TextField(
                        controller: _roomTemplateController,
                        decoration: const InputDecoration(
                          labelText: 'Room name template',
                          hintText:
                              'Project Night, {weekday} Crew, {date} Warmup',
                        ),
                        onChanged: (String value) => unawaited(
                          ref
                              .read(appPrefsControllerProvider.notifier)
                              .updateHostDefaults(
                                roomNameTemplate: value,
                              ),
                        ),
                      ),
                      const SizedBox(height: 12),
                      _ToggleTile(
                        label: 'Start new rooms with fist bumps enabled',
                        description:
                            'Use this as the default for host-created rooms. You can still override it on the create-room form.',
                        value: prefs.hostDefaults.defaultFistBumpsEnabled,
                        onChanged: (bool value) => unawaited(
                          ref
                              .read(appPrefsControllerProvider.notifier)
                              .updateHostDefaults(
                                defaultFistBumpsEnabled: value,
                              ),
                        ),
                      ),
                      const SizedBox(height: 12),
                      DropdownButtonFormField<String>(
                        initialValue: prefs.settings.soloDefaultSort,
                        decoration: const InputDecoration(
                          labelText: 'Solo browse default sort',
                        ),
                        items: const <DropdownMenuItem<String>>[
                          DropdownMenuItem<String>(
                            value: 'popular',
                            child: Text('popular'),
                          ),
                          DropdownMenuItem<String>(
                            value: 'newest',
                            child: Text('newest'),
                          ),
                        ],
                        onChanged: (String? value) {
                          if (value == null) {
                            return;
                          }
                          unawaited(
                            ref
                                .read(appPrefsControllerProvider.notifier)
                                .updateSettings(
                                  soloDefaultSort: value,
                                ),
                          );
                        },
                      ),
                      const SizedBox(height: 16),
                      _SurfaceStatusCard(prefs: prefs),
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
                        'Room templates',
                        style: Theme.of(context).textTheme.headlineMedium,
                      ),
                      const SizedBox(height: 12),
                      if (prefs.roomTemplates.isEmpty)
                        const Text('No room templates saved yet.')
                      else
                        ...prefs.roomTemplates.map(
                          (RoomTemplate template) => Padding(
                            padding: const EdgeInsets.only(bottom: 8),
                            child: Container(
                              decoration: BoxDecoration(
                                color: Colors.white,
                                borderRadius: BorderRadius.zero,
                                border:
                                    Border.all(color: const Color(0xFFE2E8F0)),
                              ),
                              padding: const EdgeInsets.all(16),
                              child: Row(
                                children: <Widget>[
                                  Expanded(
                                    child: Column(
                                      crossAxisAlignment:
                                          CrossAxisAlignment.start,
                                      children: <Widget>[
                                        Text(
                                          template.name,
                                          style: Theme.of(context)
                                              .textTheme
                                              .titleMedium,
                                        ),
                                        const SizedBox(height: 4),
                                        Text(
                                          providerChoices
                                                  .where((ProviderCapability
                                                          item) =>
                                                      item.id ==
                                                      template.providerId)
                                                  .map((ProviderCapability
                                                          item) =>
                                                      item.label)
                                                  .firstOrNull ??
                                              template.providerId,
                                        ),
                                      ],
                                    ),
                                  ),
                                  IconButton(
                                    onPressed: () => unawaited(
                                      ref
                                          .read(appPrefsControllerProvider
                                              .notifier)
                                          .deleteRoomTemplate(template.id),
                                    ),
                                    icon: const Icon(Icons.delete_outline),
                                  ),
                                ],
                              ),
                            ),
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
                        'Stored data',
                        style: Theme.of(context).textTheme.headlineMedium,
                      ),
                      const SizedBox(height: 12),
                      _OfflineCatalogSettingsCard(
                        activeServer: activeServer,
                        state: catalogState,
                        onDownload: downloadCatalogAction,
                        onSync: syncCatalogAction,
                        onDelete: () => unawaited(_confirmDeleteCatalog()),
                      ),
                      _ActionTile(
                        label: 'Reset guides',
                        description:
                            'Mark the landing, host, guest, and solo guidance as unfinished so auto-guides can appear again.',
                        actionLabel: 'Reset',
                        onPressed: () => unawaited(
                          ref
                              .read(appPrefsControllerProvider.notifier)
                              .resetGuides(),
                        ),
                      ),
                      _ActionTile(
                        label: 'Clear recent rooms',
                        description:
                            'Forget the ${prefs.recentRooms.length} saved room visit${prefs.recentRooms.length == 1 ? '' : 's'} shown on the landing page.',
                        actionLabel: 'Clear',
                        enabled: prefs.recentRooms.isNotEmpty,
                        onPressed: () => unawaited(
                          ref
                              .read(appPrefsControllerProvider.notifier)
                              .clearRecentRooms(),
                        ),
                      ),
                      _ActionTile(
                        label: 'Clear saved credentials',
                        description:
                            'Remove any remembered provider-auth preferences from this device.',
                        actionLabel: 'Clear',
                        enabled: hasSavedCredentials,
                        onPressed: () => unawaited(
                          ref
                              .read(appPrefsControllerProvider.notifier)
                              .clearSavedCredentialPreferences(),
                        ),
                      ),
                      _ActionTile(
                        label: 'Forget solo resume',
                        description:
                            'Drop the saved board, filters, and selected climb used by Resume solo browse.',
                        actionLabel: 'Forget',
                        enabled: prefs.soloResume != null,
                        onPressed: () => unawaited(
                          ref
                              .read(appPrefsControllerProvider.notifier)
                              .clearSoloResume(),
                        ),
                      ),
                      _ActionTile(
                        label: 'About Kilter Together',
                        description:
                            'Read the short project note about why the app exists and where the repo lives.',
                        actionLabel: 'Open',
                        onPressed: () => context.goNamed('about'),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          );
        },
        loading: () => Card(
          child: Padding(
            padding: const EdgeInsets.all(32),
            child: Center(child: ClimbingLoader()),
          ),
        ),
        error: (Object error, StackTrace stackTrace) => Card(
          child: Padding(
            padding: const EdgeInsets.all(22),
            child: Text('$error'),
          ),
        ),
      ),
    );
  }

  Future<void> _confirmDeleteCatalog() async {
    final CatalogStatus status =
        ref.read(offlineKilterCatalogControllerProvider).status;
    final String details = status.installed
        ? '${status.climbCount} climbs · ${_formatStoredBytes(status.storedBytes)}'
        : 'the downloaded catalog files';
    final bool? confirmed = await showDialog<bool>(
      context: context,
      builder: (BuildContext dialogContext) {
        return AlertDialog(
          title: const Text('Delete offline Kilter catalog?'),
          content: Text(
            'This removes $details from this device. Favorites, shortlist entries, saved filters, room history, and remembered credentials stay intact.',
          ),
          actions: <Widget>[
            TextButton(
              onPressed: () => Navigator.of(dialogContext).pop(false),
              child: const Text('Cancel'),
            ),
            FilledButton.tonal(
              onPressed: () => Navigator.of(dialogContext).pop(true),
              child: const Text('Delete'),
            ),
          ],
        );
      },
    );

    if (confirmed == true && mounted) {
      await ref
          .read(offlineKilterCatalogControllerProvider.notifier)
          .deleteCatalog();
    }
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
}

class _ToggleTile extends StatelessWidget {
  const _ToggleTile({
    required this.label,
    required this.description,
    required this.value,
    required this.onChanged,
  });

  final String label;
  final String description;
  final bool value;
  final ValueChanged<bool> onChanged;

  @override
  Widget build(BuildContext context) {
    return SwitchListTile.adaptive(
      contentPadding: EdgeInsets.zero,
      title: Text(label),
      subtitle: Text(description),
      value: value,
      onChanged: onChanged,
    );
  }
}

class _ActionTile extends StatelessWidget {
  const _ActionTile({
    required this.label,
    required this.description,
    required this.actionLabel,
    required this.onPressed,
    this.enabled = true,
  });

  final String label;
  final String description;
  final String actionLabel;
  final VoidCallback onPressed;
  final bool enabled;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Container(
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.zero,
          border: Border.all(color: const Color(0xFFE2E8F0)),
        ),
        padding: const EdgeInsets.all(16),
        child: Row(
          children: <Widget>[
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Text(
                    label,
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  const SizedBox(height: 4),
                  Text(description),
                ],
              ),
            ),
            const SizedBox(width: 12),
            OutlinedButton(
              onPressed: enabled ? onPressed : null,
              child: Text(actionLabel),
            ),
          ],
        ),
      ),
    );
  }
}

class _SurfaceStatusCard extends StatelessWidget {
  const _SurfaceStatusCard({
    required this.prefs,
  });

  final AppPrefs prefs;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: const Color(0xFFF5F5F5),
        borderRadius: BorderRadius.zero,
        border: Border.all(color: const Color(0xFFD4D4D4)),
      ),
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(
            'Saved surfaces',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 10),
          Text(
            prefs.lastKilterBoardId.isEmpty
                ? 'Kilter preset: none saved yet'
                : 'Kilter preset: Board ${prefs.lastKilterBoardId} at ${prefs.lastKilterAngle}°',
          ),
          const SizedBox(height: 6),
          Text(
            prefs.lastCruxGymSlug.isEmpty && prefs.lastCruxWallId.isEmpty
                ? 'Crux preset: none saved yet'
                : 'Crux preset: ${prefs.lastCruxGymSlug.isEmpty ? 'gym unset' : prefs.lastCruxGymSlug} / ${prefs.lastCruxWallId.isEmpty ? 'wall unset' : prefs.lastCruxWallId}',
          ),
        ],
      ),
    );
  }
}

class _OfflineCatalogSettingsCard extends StatelessWidget {
  const _OfflineCatalogSettingsCard({
    required this.activeServer,
    required this.state,
    required this.onDownload,
    required this.onSync,
    required this.onDelete,
  });

  final Uri? activeServer;
  final OfflineKilterCatalogState state;
  final VoidCallback? onDownload;
  final VoidCallback? onSync;
  final VoidCallback onDelete;

  @override
  Widget build(BuildContext context) {
    final bool installed = state.status.installed;
    final bool matchesServer = state.status.matchesServer(activeServer);
    final bool canDownload = activeServer != null && !state.busy;
    final bool canSync =
        activeServer != null && installed && matchesServer && !state.busy;
    final bool canDelete = installed && !state.busy;

    final String description;
    if (activeServer == null) {
      description =
          'Choose or join a self-hosted server first. The offline Kilter download is tied to the active server.';
    } else if (!installed) {
      description =
          'No offline Kilter catalog is installed for ${describeServer(activeServer!)}.';
    } else if (!matchesServer) {
      description =
          'A catalog is installed for ${state.status.sourceServer}, not ${describeServer(activeServer!)}.';
    } else if (state.status.updateAvailable &&
        state.status.requiresFullResync) {
      description =
          'A catalog update is available and needs a full refresh from ${describeServer(activeServer!)}.';
    } else {
      description =
          'Installed for ${describeServer(activeServer!)}. Kilter solo browse now reads this device-local copy.';
    }

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(
        color: const Color(0xFFF5F5F5),
        borderRadius: BorderRadius.zero,
        border: Border.all(color: const Color(0xFFD4D4D4)),
      ),
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(
            'Offline Kilter catalog',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 4),
          Text(description),
          const SizedBox(height: 10),
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: <Widget>[
              if ((state.status.sourceServer ?? '').isNotEmpty)
                _CatalogChip(
                  label:
                      'Server: ${_describeCatalogServer(state.status.sourceServer!)}',
                ),
              _CatalogChip(
                label: installed
                    ? '${state.status.climbCount} climbs'
                    : 'Not installed',
              ),
              _CatalogChip(
                label: installed
                    ? _formatStoredBytes(state.status.storedBytes)
                    : state.status.estimatedBytes > 0
                        ? 'About ${_formatStoredBytes(state.status.estimatedBytes)}'
                        : 'Size unknown',
              ),
              if (installed)
                _CatalogChip(label: '${state.status.imageCount} images'),
            ],
          ),
          const SizedBox(height: 12),
          if ((state.status.lastFullSyncAt ?? '').isNotEmpty)
            Text(
              'Last sync: ${state.status.lastFullSyncAt}',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          const SizedBox(height: 12),
          Row(
            children: <Widget>[
              Expanded(
                child: FilledButton(
                  onPressed: canDownload ? onDownload : null,
                  child: Text(
                    installed
                        ? 'Re-download'
                        : state.busy
                            ? 'Working...'
                            : 'Download',
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: OutlinedButton(
                  onPressed: canSync ? onSync : null,
                  child: const Text('Sync now'),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: OutlinedButton(
                  onPressed: canDelete ? onDelete : null,
                  child: const Text('Delete'),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _CatalogChip extends StatelessWidget {
  const _CatalogChip({
    required this.label,
  });

  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.zero,
        border: Border.all(color: const Color(0xFFD4D4D4)),
      ),
      child: Text(label),
    );
  }
}

class _SettingsMessageCard extends StatelessWidget {
  const _SettingsMessageCard({
    required this.message,
    required this.accent,
  });

  final String message;
  final Color accent;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Row(
          children: <Widget>[
            Icon(Icons.circle, size: 12, color: accent),
            const SizedBox(width: 12),
            Expanded(child: Text(message)),
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

String _describeCatalogServer(String rawServer) {
  final Uri? parsed = Uri.tryParse(rawServer);
  if (parsed == null || (parsed.host.isEmpty && parsed.path.isEmpty)) {
    return rawServer;
  }
  if (parsed.host.isEmpty) {
    return parsed.toString();
  }
  return describeServer(parsed);
}
