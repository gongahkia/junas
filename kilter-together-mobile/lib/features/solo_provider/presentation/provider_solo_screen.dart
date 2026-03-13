import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:share_plus/share_plus.dart';

import '../../../core/deep_links/invite_links.dart';
import '../../../core/models/app_prefs_models.dart';
import '../../../core/models/product_models.dart';
import '../../../core/models/provider_models.dart';
import '../../../core/models/session_models.dart';
import '../../../core/network/api_client.dart';
import '../../../core/presentation/climb_media_preview.dart';
import '../../../core/presentation/gradient_scaffold.dart';
import '../../../core/storage/app_prefs_controller.dart';
import '../../../core/storage/provider_secret_repository.dart';
import '../../../core/storage/session_repository.dart';
import '../application/provider_solo_controller.dart';

class ProviderSoloScreen extends ConsumerStatefulWidget {
  const ProviderSoloScreen({
    super.key,
    required this.providerId,
    this.initialServer,
    this.initialParentSurfaceId,
    this.initialChildSurfaceId,
    this.initialQuery,
    this.initialSort,
    this.initialClimbId,
  });

  final String providerId;
  final String? initialServer;
  final String? initialParentSurfaceId;
  final String? initialChildSurfaceId;
  final String? initialQuery;
  final String? initialSort;
  final String? initialClimbId;

  @override
  ConsumerState<ProviderSoloScreen> createState() => _ProviderSoloScreenState();
}

class _ProviderSoloScreenState extends ConsumerState<ProviderSoloScreen> {
  late final TextEditingController _queryController =
      TextEditingController(text: widget.initialQuery ?? '');
  final TextEditingController _planTitleController = TextEditingController();
  final TextEditingController _planNotesController = TextEditingController();
  final Map<String, TextEditingController> _secretControllers =
      <String, TextEditingController>{};

  bool _rememberSecret = false;
  bool _rememberedSecretLoaded = false;

  ProviderSoloRouteArgs get _args => ProviderSoloRouteArgs(
        providerId: widget.providerId,
        initialServer: widget.initialServer,
        initialParentSurfaceId: widget.initialParentSurfaceId,
        initialChildSurfaceId: widget.initialChildSurfaceId,
        initialQuery: widget.initialQuery,
        initialSort: widget.initialSort,
        initialClimbId: widget.initialClimbId,
      );

  @override
  void initState() {
    super.initState();
    ref.read(sessionRepositoryProvider).loadAppPrefs().then((AppPrefs prefs) {
      if (!mounted) {
        return;
      }
      setState(() {
        _rememberSecret =
            prefs.savedCredentials.providers[widget.providerId]?.remember ??
                false;
      });
    });
  }

  @override
  void dispose() {
    _queryController.dispose();
    _planTitleController.dispose();
    _planNotesController.dispose();
    for (final TextEditingController controller in _secretControllers.values) {
      controller.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final ProviderSoloViewState state =
        ref.watch(providerSoloControllerProvider(_args));
    final ProviderSoloController controller =
        ref.read(providerSoloControllerProvider(_args).notifier);
    final AppPrefs prefs = ref.watch(appPrefsControllerProvider).valueOrNull ??
        AppPrefs.defaults();

    final ProviderCapability? capability = state.capability;
    if (capability != null) {
      for (final ProviderAuthField field in capability.authFields) {
        _secretControllers.putIfAbsent(
            field.key, () => TextEditingController());
      }
    }

    if (!_rememberedSecretLoaded &&
        capability != null &&
        state.server != null) {
      _rememberedSecretLoaded = true;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        unawaited(_loadRememberedSecret(state.server!, capability));
      });
    }

    final ProviderSurface? activeSurface = state.activeSurface;
    if (_planTitleController.text.isEmpty && activeSurface != null) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (!mounted || _planTitleController.text.isNotEmpty) {
          return;
        }
        _planTitleController.text = '${activeSurface.name} plan';
      });
    }

    return GradientScaffold(
      title: capability?.label ?? widget.providerId.toUpperCase(),
      subtitle: state.server == null
          ? 'Choose a self-hosted server before opening provider solo browse.'
          : '${describeServer(state.server!)} · ${capability?.label ?? widget.providerId}',
      actions: <Widget>[
        IconButton(
          onPressed:
              state.catalogLoading ? null : () => context.goNamed('solo-entry'),
          icon: const Icon(Icons.arrow_back),
        ),
      ],
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          if (state.errorMessage != null) ...<Widget>[
            _MessageCard(
              title: 'Unable to load provider solo browse',
              message: state.errorMessage!,
              accent: const Color(0xFFB91C1C),
            ),
            const SizedBox(height: 14),
          ],
          if (state.notice != null) ...<Widget>[
            _MessageCard(
              title: 'Updated',
              message: state.notice!,
              accent: const Color(0xFF0F766E),
            ),
            const SizedBox(height: 14),
          ],
          if (state.loading)
            const Card(
              child: Padding(
                padding: EdgeInsets.all(32),
                child: Center(child: CircularProgressIndicator()),
              ),
            )
          else if (state.missingServer)
            _MissingServerCard(onJoin: () => context.goNamed('join-room'))
          else if (capability == null)
            Card(
              child: Padding(
                padding: const EdgeInsets.all(22),
                child: Text(
                  '${widget.providerId} does not expose provider-backed solo browse on this server.',
                ),
              ),
            )
          else
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                _AccessCard(
                  capability: capability,
                  rememberSecret: _rememberSecret,
                  secretControllers: _secretControllers,
                  surfacesLoading: state.surfacesLoading,
                  accessLoaded: state.accessLoaded,
                  onRememberSecretChanged: (bool value) {
                    setState(() {
                      _rememberSecret = value;
                    });
                  },
                  onUnlockCatalog: () => unawaited(
                    _unlockCatalog(
                      controller: controller,
                      state: state,
                      capability: capability,
                    ),
                  ),
                ),
                const SizedBox(height: 14),
                _SurfaceCard(
                  state: state,
                  onParentChanged: (String? value) {
                    if (value == null || value.isEmpty) {
                      return;
                    }
                    unawaited(controller.loadChildSurfaces(value));
                  },
                  onChildChanged: (String? value) {
                    if (value == null) {
                      return;
                    }
                    unawaited(
                      controller.selectChildSurface(
                        value == '__none__' ? '' : value,
                      ),
                    );
                  },
                ),
                const SizedBox(height: 14),
                _PlanCard(
                  state: state,
                  planTitleController: _planTitleController,
                  planNotesController: _planNotesController,
                  actionInFlight: state.actionInFlight,
                  onCreateRoom: () => unawaited(
                    _beginRoomSeed(
                      context: context,
                      controller: controller,
                    ),
                  ),
                  onSharePlan: () => unawaited(
                    _sharePlan(
                      context: context,
                      controller: controller,
                      prefs: prefs,
                    ),
                  ),
                  onRemovePlannedClimb: (String climbId) {
                    final ProviderClimb? climb =
                        state.plannedClimbs.cast<ProviderClimb?>().firstWhere(
                              (ProviderClimb? item) => item?.id == climbId,
                              orElse: () => null,
                            );
                    if (climb != null) {
                      controller.togglePlannedClimb(climb);
                    }
                  },
                ),
                const SizedBox(height: 14),
                _CatalogCard(
                  state: state,
                  queryController: _queryController,
                  onApplyQuery: () => unawaited(
                    controller.updateSearch(query: _queryController.text),
                  ),
                  onSortChanged: (String? value) {
                    if (value == null) {
                      return;
                    }
                    unawaited(controller.updateSearch(sort: value));
                  },
                  onSelectClimb: (ProviderClimb climb) =>
                      unawaited(controller.selectClimb(climb.id)),
                  onTogglePlannedClimb: (ProviderClimb climb) =>
                      controller.togglePlannedClimb(
                    state.selectedClimb?.id == climb.id
                        ? state.selectedClimb!
                        : climb,
                  ),
                  onPreviousPage: state.currentPage <= 1
                      ? null
                      : () => unawaited(controller.previousPage()),
                  onNextPage: state.hasNextPage
                      ? () => unawaited(controller.nextPage())
                      : null,
                ),
                const SizedBox(height: 14),
                _ClimbDetailCard(
                  apiClient: ref.read(apiClientProvider),
                  climb: state.selectedClimb,
                  loading: state.detailLoading,
                  server: state.server,
                  isPlanned: state.selectedClimb != null &&
                      state.plannedClimbs.any(
                        (ProviderClimb item) =>
                            item.id == state.selectedClimb!.id,
                      ),
                  onTogglePlannedClimb: state.selectedClimb == null
                      ? null
                      : () =>
                          controller.togglePlannedClimb(state.selectedClimb!),
                ),
              ],
            ),
        ],
      ),
    );
  }

  Future<void> _loadRememberedSecret(
    Uri server,
    ProviderCapability capability,
  ) async {
    try {
      final Map<String, String> secret =
          await ref.read(providerSecretRepositoryProvider).readSecret(
                server: server,
                providerId: widget.providerId,
              );
      if (!mounted || secret.isEmpty) {
        return;
      }
      setState(() {
        _rememberSecret = true;
        for (final ProviderAuthField field in capability.authFields) {
          _secretControllers[field.key]?.text = secret[field.key] ?? '';
        }
      });
    } catch (_) {
      // Keep provider auth manual if secure storage is unavailable.
    }
  }

  Future<void> _unlockCatalog({
    required ProviderSoloController controller,
    required ProviderSoloViewState state,
    required ProviderCapability capability,
  }) async {
    final Map<String, String> secret = <String, String>{
      for (final ProviderAuthField field in capability.authFields)
        field.key: _secretControllers[field.key]?.text.trim() ?? '',
    };
    if (secret.values.any((String value) => value.trim().isEmpty)) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content:
              Text('Enter the required ${capability.label} credentials first.'),
        ),
      );
      return;
    }

    await controller.unlockCatalog(secret);
    if (!mounted || state.server == null) {
      return;
    }

    final ProviderSoloViewState nextState =
        ref.read(providerSoloControllerProvider(_args));
    if (!nextState.accessLoaded) {
      return;
    }

    if (_rememberSecret) {
      await ref.read(providerSecretRepositoryProvider).saveSecret(
            server: state.server!,
            providerId: widget.providerId,
            secret: secret,
          );
      await ref
          .read(appPrefsControllerProvider.notifier)
          .rememberProviderSecretPreference(
            providerId: widget.providerId,
            remember: true,
          );
    } else {
      await ref.read(providerSecretRepositoryProvider).clearSecret(
            server: state.server!,
            providerId: widget.providerId,
          );
      await ref
          .read(appPrefsControllerProvider.notifier)
          .rememberProviderSecretPreference(
            providerId: widget.providerId,
            remember: false,
          );
    }
  }

  Future<void> _beginRoomSeed({
    required BuildContext context,
    required ProviderSoloController controller,
  }) async {
    final GoRouter router = GoRouter.of(context);
    await controller.beginRoomSeed(title: _planTitleController.text);
    if (!mounted) {
      return;
    }
    router.goNamed('create-room');
  }

  Future<void> _sharePlan({
    required BuildContext context,
    required ProviderSoloController controller,
    required AppPrefs prefs,
  }) async {
    final ProviderSoloViewState state =
        ref.read(providerSoloControllerProvider(_args));
    if (state.server == null) {
      return;
    }

    final SoloPlanSnapshot? plan = await controller.createPlan(
      title: _planTitleController.text,
      notes: _planNotesController.text,
      createdBy: prefs.savedDisplayName,
    );
    if (!mounted || plan == null) {
      return;
    }

    final Uri shareUri = InviteLink(
      kind: InviteKind.plan,
      server: state.server!,
      shareId: plan.shareId,
    ).toUri();
    await Share.share(
      shareUri.toString(),
      subject: plan.title,
    );
  }
}

class _AccessCard extends StatelessWidget {
  const _AccessCard({
    required this.capability,
    required this.rememberSecret,
    required this.secretControllers,
    required this.surfacesLoading,
    required this.accessLoaded,
    required this.onRememberSecretChanged,
    required this.onUnlockCatalog,
  });

  final ProviderCapability capability;
  final bool rememberSecret;
  final Map<String, TextEditingController> secretControllers;
  final bool surfacesLoading;
  final bool accessLoaded;
  final ValueChanged<bool> onRememberSecretChanged;
  final VoidCallback onUnlockCatalog;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(22),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              'Unlock ${capability.label} catalog',
              style: Theme.of(context).textTheme.headlineMedium,
            ),
            const SizedBox(height: 8),
            const Text(
              'Credentials are sent only to your own Kilter Together backend for provider requests. Solo browse can remember the secret on this device if you want faster returns.',
            ),
            const SizedBox(height: 16),
            ...capability.authFields.map(
              (ProviderAuthField field) => Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: TextField(
                  controller: secretControllers[field.key],
                  obscureText: field.type == 'password',
                  decoration: InputDecoration(
                    labelText: field.label,
                    hintText: field.placeholder,
                  ),
                ),
              ),
            ),
            SwitchListTile.adaptive(
              contentPadding: EdgeInsets.zero,
              title: const Text('Remember this provider secret on the device'),
              value: rememberSecret,
              onChanged: onRememberSecretChanged,
            ),
            const SizedBox(height: 8),
            Row(
              children: <Widget>[
                Expanded(
                  child: FilledButton(
                    onPressed: surfacesLoading ? null : onUnlockCatalog,
                    child: Text(
                      surfacesLoading ? 'Loading catalog...' : 'Load catalog',
                    ),
                  ),
                ),
                if (accessLoaded) ...<Widget>[
                  const SizedBox(width: 12),
                  const Chip(label: Text('Catalog unlocked')),
                ],
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _SurfaceCard extends StatelessWidget {
  const _SurfaceCard({
    required this.state,
    required this.onParentChanged,
    required this.onChildChanged,
  });

  final ProviderSoloViewState state;
  final ValueChanged<String?> onParentChanged;
  final ValueChanged<String?> onChildChanged;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(22),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              'Surface context',
              style: Theme.of(context).textTheme.headlineMedium,
            ),
            const SizedBox(height: 8),
            Text(
              state.providerId == 'crux'
                  ? 'Pick a gym first, then optionally keep a wall selected as the room handoff context.'
                  : 'Pick the provider surface you want to browse and carry forward into room creation.',
            ),
            const SizedBox(height: 16),
            DropdownButtonFormField<String>(
              initialValue: state.selectedParentSurfaceId.isEmpty
                  ? null
                  : state.selectedParentSurfaceId,
              decoration: const InputDecoration(labelText: 'Primary surface'),
              items: state.parentSurfaces
                  .map(
                    (ProviderSurface item) => DropdownMenuItem<String>(
                      value: item.id,
                      child: Text(item.name),
                    ),
                  )
                  .toList(growable: false),
              onChanged: state.accessLoaded && !state.surfacesLoading
                  ? onParentChanged
                  : null,
            ),
            const SizedBox(height: 12),
            DropdownButtonFormField<String>(
              initialValue: state.selectedChildSurfaceId.isEmpty
                  ? '__none__'
                  : state.selectedChildSurfaceId,
              decoration: const InputDecoration(labelText: 'Secondary surface'),
              items: <DropdownMenuItem<String>>[
                const DropdownMenuItem<String>(
                  value: '__none__',
                  child: Text('No secondary surface'),
                ),
                ...state.childSurfaces.map(
                  (ProviderSurface item) => DropdownMenuItem<String>(
                    value: item.id,
                    child: Text(item.name),
                  ),
                ),
              ],
              onChanged: state.accessLoaded && !state.surfacesLoading
                  ? onChildChanged
                  : null,
            ),
            const SizedBox(height: 16),
            Wrap(
              spacing: 10,
              runSpacing: 10,
              children: <Widget>[
                if (state.selectedParentSurface != null)
                  _InfoChip(label: state.selectedParentSurface!.name),
                if (state.selectedChildSurface != null)
                  _InfoChip(label: state.selectedChildSurface!.name),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _PlanCard extends StatelessWidget {
  const _PlanCard({
    required this.state,
    required this.planTitleController,
    required this.planNotesController,
    required this.actionInFlight,
    required this.onCreateRoom,
    required this.onSharePlan,
    required this.onRemovePlannedClimb,
  });

  final ProviderSoloViewState state;
  final TextEditingController planTitleController;
  final TextEditingController planNotesController;
  final bool actionInFlight;
  final VoidCallback onCreateRoom;
  final VoidCallback onSharePlan;
  final ValueChanged<String> onRemovePlannedClimb;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(22),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              'Plan and room seed',
              style: Theme.of(context).textTheme.headlineMedium,
            ),
            const SizedBox(height: 8),
            Text(
              'Build a shortlist from the live provider catalog, then either share it as an immutable solo plan or hand it into room creation.',
            ),
            const SizedBox(height: 16),
            TextField(
              controller: planTitleController,
              decoration: const InputDecoration(labelText: 'Plan title'),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: planNotesController,
              decoration: const InputDecoration(labelText: 'Plan notes'),
              minLines: 2,
              maxLines: 3,
            ),
            const SizedBox(height: 16),
            if (state.plannedClimbs.isEmpty)
              const Text('No climbs are in the provider shortlist yet.')
            else
              Column(
                children: state.plannedClimbs
                    .map(
                      (ProviderClimb climb) => ListTile(
                        contentPadding: EdgeInsets.zero,
                        title: Text(climb.name),
                        subtitle: Text(
                          [
                            if ((climb.primaryGrade ?? '').isNotEmpty)
                              climb.primaryGrade!,
                            if ((climb.setterName ?? '').isNotEmpty)
                              climb.setterName!,
                          ].join(' · '),
                        ),
                        trailing: IconButton(
                          onPressed: () => onRemovePlannedClimb(climb.id),
                          icon: const Icon(Icons.remove_circle_outline),
                        ),
                      ),
                    )
                    .toList(growable: false),
              ),
            const SizedBox(height: 12),
            Row(
              children: <Widget>[
                Expanded(
                  child: FilledButton(
                    onPressed: actionInFlight ? null : onSharePlan,
                    child: const Text('Share plan'),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: OutlinedButton(
                    onPressed: actionInFlight ? null : onCreateRoom,
                    child: const Text('Start room'),
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

class _CatalogCard extends StatelessWidget {
  const _CatalogCard({
    required this.state,
    required this.queryController,
    required this.onApplyQuery,
    required this.onSortChanged,
    required this.onSelectClimb,
    required this.onTogglePlannedClimb,
    required this.onPreviousPage,
    required this.onNextPage,
  });

  final ProviderSoloViewState state;
  final TextEditingController queryController;
  final VoidCallback onApplyQuery;
  final ValueChanged<String?> onSortChanged;
  final ValueChanged<ProviderClimb> onSelectClimb;
  final ValueChanged<ProviderClimb> onTogglePlannedClimb;
  final VoidCallback? onPreviousPage;
  final VoidCallback? onNextPage;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(22),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              'Browse climbs',
              style: Theme.of(context).textTheme.headlineMedium,
            ),
            const SizedBox(height: 8),
            const Text(
              'Search the live provider catalog, then inspect the richer detail view below before adding a climb to the shortlist.',
            ),
            const SizedBox(height: 16),
            TextField(
              controller: queryController,
              decoration: const InputDecoration(
                labelText: 'Search climbs',
                hintText: 'Search by name',
              ),
              textInputAction: TextInputAction.search,
              onSubmitted: (_) => onApplyQuery(),
            ),
            const SizedBox(height: 12),
            DropdownButtonFormField<String>(
              initialValue: state.sort,
              decoration: const InputDecoration(labelText: 'Sort'),
              items: const <DropdownMenuItem<String>>[
                DropdownMenuItem<String>(
                    value: 'popular', child: Text('popular')),
                DropdownMenuItem<String>(
                    value: 'newest', child: Text('newest')),
              ],
              onChanged: onSortChanged,
            ),
            const SizedBox(height: 12),
            FilledButton.tonal(
              onPressed: state.accessLoaded && !state.catalogLoading
                  ? onApplyQuery
                  : null,
              child:
                  Text(state.catalogLoading ? 'Refreshing...' : 'Apply search'),
            ),
            const SizedBox(height: 16),
            if (!state.accessLoaded)
              const Text('Unlock the provider catalog first.')
            else if (state.catalogLoading && state.climbs.isEmpty)
              const Center(child: CircularProgressIndicator())
            else if (state.climbs.isEmpty)
              const Text('No climbs match the current provider filters.')
            else
              Column(
                children: state.climbs
                    .map(
                      (ProviderClimb climb) => Padding(
                        padding: const EdgeInsets.only(bottom: 10),
                        child: InkWell(
                          borderRadius: BorderRadius.circular(20),
                          onTap: () => onSelectClimb(climb),
                          child: Ink(
                            decoration: BoxDecoration(
                              borderRadius: BorderRadius.circular(20),
                              border: Border.all(
                                color: state.selectedClimb?.id == climb.id
                                    ? const Color(0xFF0F766E)
                                    : const Color(0xFFE2E8F0),
                              ),
                              color: state.selectedClimb?.id == climb.id
                                  ? const Color(0xFFF0FDFA)
                                  : Colors.white,
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
                                        climb.name,
                                        style: Theme.of(context)
                                            .textTheme
                                            .titleLarge,
                                      ),
                                      const SizedBox(height: 4),
                                      Text(
                                        [
                                          if ((climb.primaryGrade ?? '')
                                              .isNotEmpty)
                                            climb.primaryGrade!,
                                          if ((climb.setterName ?? '')
                                              .isNotEmpty)
                                            climb.setterName!,
                                          if ((climb.meta['color'] ?? '')
                                              .isNotEmpty)
                                            climb.meta['color']!,
                                        ].join(' · '),
                                        style: Theme.of(context)
                                            .textTheme
                                            .bodySmall,
                                      ),
                                    ],
                                  ),
                                ),
                                IconButton(
                                  onPressed: () => onTogglePlannedClimb(climb),
                                  icon: Icon(
                                    state.plannedClimbs.any(
                                      (ProviderClimb item) =>
                                          item.id == climb.id,
                                    )
                                        ? Icons.playlist_add_check_circle
                                        : Icons.playlist_add,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                      ),
                    )
                    .toList(growable: false),
              ),
            const SizedBox(height: 8),
            Row(
              children: <Widget>[
                Expanded(
                  child: FilledButton.tonal(
                    onPressed: onPreviousPage,
                    child: const Text('Previous page'),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: FilledButton(
                    onPressed: onNextPage,
                    child: const Text('Next page'),
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

class _ClimbDetailCard extends StatelessWidget {
  const _ClimbDetailCard({
    required this.apiClient,
    required this.climb,
    required this.loading,
    required this.server,
    required this.isPlanned,
    required this.onTogglePlannedClimb,
  });

  final ApiClient apiClient;
  final ProviderClimb? climb;
  final bool loading;
  final Uri? server;
  final bool isPlanned;
  final VoidCallback? onTogglePlannedClimb;

  @override
  Widget build(BuildContext context) {
    if (loading) {
      return const Card(
        child: Padding(
          padding: EdgeInsets.all(24),
          child: Center(child: CircularProgressIndicator()),
        ),
      );
    }

    if (climb == null) {
      return const Card(
        child: Padding(
          padding: EdgeInsets.all(22),
          child: Text('Choose a provider climb to inspect the detail view.'),
        ),
      );
    }

    final List<String> imageUrls = server == null
        ? const <String>[]
        : climb!.media
            .where((ProviderClimbMedia item) => item.kind == 'image')
            .map(
              (ProviderClimbMedia item) =>
                  apiClient.resolveMediaUrl(server: server!, url: item.url),
            )
            .toList(growable: false);

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(22),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              climb!.name,
              style: Theme.of(context).textTheme.headlineMedium,
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 10,
              runSpacing: 10,
              children: <Widget>[
                if ((climb!.primaryGrade ?? '').isNotEmpty)
                  _InfoChip(label: climb!.primaryGrade!),
                if ((climb!.setterName ?? '').isNotEmpty)
                  _InfoChip(label: climb!.setterName!),
                if ((climb!.meta['source_label'] ?? '').isNotEmpty)
                  _InfoChip(label: climb!.meta['source_label']!),
                if ((climb!.meta['color'] ?? '').isNotEmpty)
                  _InfoChip(label: climb!.meta['color']!),
              ],
            ),
            if ((climb!.description ?? '').isNotEmpty) ...<Widget>[
              const SizedBox(height: 12),
              Text(climb!.description!),
            ],
            const SizedBox(height: 18),
            ClimbMediaPreview(
              imageUrls: imageUrls,
              highlightedHolds: climb!.highlightedHolds,
              emptyMessage: server == null
                  ? 'No provider image available'
                  : 'No provider images available for this climb',
              errorMessage: 'Unable to load provider image',
            ),
            const SizedBox(height: 16),
            FilledButton.tonalIcon(
              onPressed: onTogglePlannedClimb,
              icon: Icon(
                isPlanned
                    ? Icons.playlist_add_check_circle
                    : Icons.playlist_add,
              ),
              label: Text(isPlanned ? 'In shortlist' : 'Add to shortlist'),
            ),
          ],
        ),
      ),
    );
  }
}

class _MessageCard extends StatelessWidget {
  const _MessageCard({
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
      child: Container(
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(28),
          gradient: LinearGradient(
            colors: <Color>[
              accent.withValues(alpha: 0.14),
              Colors.white,
            ],
          ),
        ),
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(title, style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 6),
            Text(message),
          ],
        ),
      ),
    );
  }
}

class _MissingServerCard extends StatelessWidget {
  const _MissingServerCard({
    required this.onJoin,
  });

  final VoidCallback onJoin;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(22),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              'No active server',
              style: Theme.of(context).textTheme.headlineMedium,
            ),
            const SizedBox(height: 8),
            const Text(
              'Join or host a room first so the app knows which self-hosted node should proxy provider requests for solo browse.',
            ),
            const SizedBox(height: 18),
            FilledButton(
              onPressed: onJoin,
              child: const Text('Open join flow'),
            ),
          ],
        ),
      ),
    );
  }
}

class _InfoChip extends StatelessWidget {
  const _InfoChip({
    required this.label,
  });

  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: const Color(0xFFF0FDFA),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFFB7E4DF)),
      ),
      child: Text(label),
    );
  }
}
