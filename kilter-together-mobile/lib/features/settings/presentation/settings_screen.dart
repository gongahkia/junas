import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/models/app_prefs_models.dart';
import '../../../core/models/provider_models.dart';
import '../../../core/network/api_client.dart';
import '../../../core/presentation/gradient_scaffold.dart';
import '../../../core/storage/app_prefs_controller.dart';
import '../../../core/storage/session_repository.dart';

final _settingsCapabilitiesProvider =
    FutureProvider.autoDispose<List<ProviderCapability>>((Ref ref) async {
  final Uri? server =
      await ref.read(sessionRepositoryProvider).loadActiveServer();
  if (server == null) {
    return const <ProviderCapability>[];
  }
  final List<ProviderCapability> capabilities =
      await ref.read(apiClientProvider).getProviderCapabilities(server);
  return capabilities
      .where((ProviderCapability item) => item.roomSupported)
      .toList(growable: false);
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
    final List<ProviderCapability> capabilities =
        ref.watch(_settingsCapabilitiesProvider).valueOrNull ??
            const <ProviderCapability>[];

    return GradientScaffold(
      title: 'Settings',
      subtitle:
          'Local-only preferences for display defaults, guides, recent rooms, saved credentials, and solo behavior.',
      actions: <Widget>[
        IconButton(
          onPressed: () => context.goNamed('landing'),
          icon: const Icon(Icons.close),
        ),
      ],
      child: prefsValue.when(
        data: (AppPrefs prefs) {
          if (!_hydrated) {
            _hydrated = true;
            _displayNameController.text = prefs.savedDisplayName;
            _roomTemplateController.text = prefs.hostDefaults.roomNameTemplate;
          }

          final List<ProviderCapability> providerChoices = capabilities.isEmpty
              ? const <ProviderCapability>[
                  ProviderCapability(
                    id: 'kilter',
                    label: 'Kilter',
                    roomSupported: true,
                    soloSupported: true,
                    surfaceHierarchy: 'board',
                    authFields: <ProviderAuthField>[],
                  ),
                  ProviderCapability(
                    id: 'crux',
                    label: 'Crux',
                    roomSupported: true,
                    soloSupported: true,
                    surfaceHierarchy: 'hierarchy',
                    authFields: <ProviderAuthField>[],
                  ),
                ]
              : capabilities;
          final bool hasSavedCredentials =
              prefs.savedCredentials.providers.values.any(
            (SavedCredentialPreference item) => item.remember,
          );

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
                        'Experience',
                        style: Theme.of(context).textTheme.headlineMedium,
                      ),
                      const SizedBox(height: 12),
                      _ToggleTile(
                        label: 'Show cursor encouragement words',
                        description:
                            'Keep the playful click-cheer words enabled on this device.',
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
                        label: 'Show onboarding guides automatically',
                        description:
                            'Replay the landing, room, and solo guides automatically until each branch is completed.',
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
                        'Stored data',
                        style: Theme.of(context).textTheme.headlineMedium,
                      ),
                      const SizedBox(height: 12),
                      _ActionTile(
                        label: 'Reset guides',
                        description:
                            'Replay the onboarding and intro flows the next time automatic guides are allowed.',
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
                    ],
                  ),
                ),
              ),
            ],
          );
        },
        loading: () => const Card(
          child: Padding(
            padding: EdgeInsets.all(32),
            child: Center(child: CircularProgressIndicator()),
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
          borderRadius: BorderRadius.circular(22),
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
        color: const Color(0xFFF8FFFD),
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: const Color(0xFFB7E4DF)),
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
