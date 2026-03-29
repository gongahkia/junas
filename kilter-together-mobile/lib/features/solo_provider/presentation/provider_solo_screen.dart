import 'dart:io';
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';
import 'package:share_plus/share_plus.dart';

import '../../../core/community/cornifer_models.dart';
import '../../../core/deep_links/invite_links.dart';
import '../../../core/models/app_prefs_models.dart';
import '../../../core/models/product_models.dart';
import '../../../core/models/provider_models.dart';
import '../../../core/models/session_models.dart';
import '../../../core/network/api_client.dart';
import '../../../core/presentation/climb_media_preview.dart';
import '../../../core/presentation/climbing_loader.dart';
import '../../../core/presentation/gradient_scaffold.dart';
import '../../../core/storage/app_prefs_controller.dart';
import '../../../core/storage/provider_secret_repository.dart';
import '../../../core/storage/session_repository.dart';
import '../../cornifer/application/cornifer_community_controller.dart';
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
  final TextEditingController _gradeMinController = TextEditingController();
  final TextEditingController _gradeMaxController = TextEditingController();
  final TextEditingController _planTitleController = TextEditingController();
  final TextEditingController _planNotesController = TextEditingController();
  final TextEditingController _corniferUsernameController =
      TextEditingController();
  final TextEditingController _corniferPasswordController =
      TextEditingController();
  final TextEditingController _corniferBoardNameController =
      TextEditingController();
  final TextEditingController _corniferBoardLocationController =
      TextEditingController();
  final TextEditingController _corniferBoardDescriptionController =
      TextEditingController();
  final TextEditingController _corniferClimbNameController =
      TextEditingController();
  final TextEditingController _corniferClimbGradeController =
      TextEditingController();
  final TextEditingController _corniferClimbDescriptionController =
      TextEditingController();
  final TextEditingController _corniferAttemptController =
      TextEditingController(text: '1');
  final Map<String, TextEditingController> _secretControllers =
      <String, TextEditingController>{};
  final Map<String, String> _corniferHoldRoles = <String, String>{};
  final ImagePicker _imagePicker = ImagePicker();

  bool _rememberSecret = false;
  bool _rememberedSecretLoaded = false;
  String? _corniferImagePath;

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
    _gradeMinController.dispose();
    _gradeMaxController.dispose();
    _planTitleController.dispose();
    _planNotesController.dispose();
    _corniferUsernameController.dispose();
    _corniferPasswordController.dispose();
    _corniferBoardNameController.dispose();
    _corniferBoardLocationController.dispose();
    _corniferBoardDescriptionController.dispose();
    _corniferClimbNameController.dispose();
    _corniferClimbGradeController.dispose();
    _corniferClimbDescriptionController.dispose();
    _corniferAttemptController.dispose();
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
    final CorniferCommunityState? corniferState =
        widget.providerId == 'cornifer'
            ? ref.watch(corniferCommunityControllerProvider(state.server))
            : null;

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
    if (widget.providerId == 'cornifer' &&
        _corniferBoardLocationController.text.isEmpty &&
        state.selectedParentSurface != null) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (!mounted || _corniferBoardLocationController.text.isNotEmpty) {
          return;
        }
        _corniferBoardLocationController.text =
            state.selectedParentSurface!.name;
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
              accent: const Color(0xFF404040),
            ),
            const SizedBox(height: 14),
          ],
          if (state.notice != null) ...<Widget>[
            _MessageCard(
              title: 'Updated',
              message: state.notice!,
              accent: const Color(0xFF1A1A1A),
            ),
            const SizedBox(height: 14),
          ],
          if (corniferState?.errorMessage != null) ...<Widget>[
            _MessageCard(
              title: 'Cornifer community',
              message: corniferState!.errorMessage!,
              accent: const Color(0xFF8B1E1E),
            ),
            const SizedBox(height: 14),
          ],
          if (corniferState?.notice != null) ...<Widget>[
            _MessageCard(
              title: 'Cornifer community',
              message: corniferState!.notice!,
              accent: const Color(0xFF0F5132),
            ),
            const SizedBox(height: 14),
          ],
          if (state.loading)
            Card(
              child: Padding(
                padding: const EdgeInsets.all(32),
                child: Center(child: ClimbingLoader()),
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
                if (capability.authFields.isNotEmpty)
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
                  )
                else
                  _OpenCatalogCard(
                    capability: capability,
                    surfacesLoading: state.surfacesLoading,
                    accessLoaded: state.accessLoaded,
                    onRefresh: () => unawaited(controller.unlockCatalog(
                      const <String, String>{},
                    )),
                  ),
                const SizedBox(height: 14),
                if (widget.providerId == 'cornifer' &&
                    corniferState != null) ...<Widget>[
                  _buildCorniferCommunitySection(
                    context: context,
                    state: state,
                    controller: controller,
                    communityState: corniferState,
                  ),
                  const SizedBox(height: 14),
                ],
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
                  selectedClimbIds: state.selectedClimbIds,
                  queryController: _queryController,
                  gradeMinController: _gradeMinController,
                  gradeMaxController: _gradeMaxController,
                  onApplyQuery: () => unawaited(
                    controller.updateSearch(
                      query: _queryController.text,
                      gradeMin: _gradeMinController.text,
                      gradeMax: _gradeMaxController.text,
                    ),
                  ),
                  onSortChanged: (String? value) {
                    if (value == null) {
                      return;
                    }
                    unawaited(controller.updateSearch(sort: value));
                  },
                  onSelectClimb: (ProviderClimb climb) =>
                      unawaited(controller.selectClimb(climb.id)),
                  onLongPressClimb: (ProviderClimb climb) =>
                      controller.toggleMultiSelect(climb.id),
                  onTogglePlannedClimb: (ProviderClimb climb) =>
                      controller.togglePlannedClimb(
                    state.selectedClimb?.id == climb.id
                        ? state.selectedClimb!
                        : climb,
                  ),
                  onAddSelectedToShortlist: () =>
                      controller.addSelectedToPlannedClimbs(),
                  onClearMultiSelect: () => controller.clearMultiSelect(),
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
                if (widget.providerId == 'cornifer' &&
                    corniferState != null) ...<Widget>[
                  const SizedBox(height: 14),
                  _buildCorniferEngagementSection(
                    context: context,
                    communityState: corniferState,
                    climb: state.selectedClimb,
                  ),
                ],
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
      shareId: plan.shareId,
    ).toUri();
    await Share.share(
      shareUri.toString(),
      subject: plan.title,
    );
  }

  Widget _buildCorniferCommunitySection({
    required BuildContext context,
    required ProviderSoloViewState state,
    required ProviderSoloController controller,
    required CorniferCommunityState communityState,
  }) {
    final CorniferBoardDraft? boardDraft = communityState.boardDraft;
    final Uri? server = state.server;
    final bool signedIn = communityState.session != null;
    final String resolvedBoardImageUrl =
        server == null || boardDraft == null || boardDraft.imageUrl.isEmpty
            ? ''
            : ref
                .read(apiClientProvider)
                .resolveMediaUrl(server: server, url: boardDraft.imageUrl);

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(22),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              'Cornifer community',
              style: Theme.of(context).textTheme.headlineMedium,
            ),
            const SizedBox(height: 8),
            const Text(
              'Cornifer browse is open-read inside Kilter Together. Sign in only for community actions: publish boards, publish climbs, log tries, and rate climbs.',
            ),
            const SizedBox(height: 18),
            Text(
              'Account',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 10),
            if (communityState.loadingSession)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 12),
                child: Center(child: ClimbingLoader()),
              )
            else if (!signedIn) ...<Widget>[
              TextField(
                controller: _corniferUsernameController,
                decoration: const InputDecoration(
                  labelText: 'Cornifer username',
                ),
                textInputAction: TextInputAction.next,
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _corniferPasswordController,
                obscureText: true,
                decoration: const InputDecoration(
                  labelText: 'Cornifer password',
                ),
                textInputAction: TextInputAction.done,
              ),
              const SizedBox(height: 12),
              Row(
                children: <Widget>[
                  Expanded(
                    child: FilledButton(
                      onPressed: communityState.actionInFlight
                          ? null
                          : () => unawaited(_registerCornifer()),
                      child: const Text('Register'),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: OutlinedButton(
                      onPressed: communityState.actionInFlight
                          ? null
                          : () => unawaited(_loginCornifer()),
                      child: const Text('Sign in'),
                    ),
                  ),
                ],
              ),
            ] else ...<Widget>[
              Wrap(
                spacing: 10,
                runSpacing: 10,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: <Widget>[
                  _InfoChip(
                    label: 'Signed in as ${communityState.session!.username}',
                  ),
                  OutlinedButton(
                    onPressed: communityState.actionInFlight
                        ? null
                        : () => unawaited(_logoutCornifer()),
                    child: const Text('Sign out'),
                  ),
                ],
              ),
            ],
            const SizedBox(height: 24),
            Text(
              'Board authoring',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 8),
            const Text(
              'Create a board draft, detect holds from a board photo, review them, and publish the board into the shared Cornifer catalog.',
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _corniferBoardNameController,
              decoration: const InputDecoration(labelText: 'Board name'),
              textInputAction: TextInputAction.next,
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _corniferBoardLocationController,
              decoration: const InputDecoration(labelText: 'Location'),
              textInputAction: TextInputAction.next,
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _corniferBoardDescriptionController,
              decoration: const InputDecoration(labelText: 'Board description'),
              minLines: 2,
              maxLines: 3,
            ),
            const SizedBox(height: 12),
            if (_corniferImagePath != null) ...<Widget>[
              ClipRRect(
                borderRadius: BorderRadius.zero,
                child: Image.file(
                  File(_corniferImagePath!),
                  height: 180,
                  width: double.infinity,
                  fit: BoxFit.cover,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                _corniferImagePath!,
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ] else if (boardDraft != null &&
                resolvedBoardImageUrl.isNotEmpty) ...<Widget>[
              ClipRRect(
                borderRadius: BorderRadius.zero,
                child: Image.network(
                  resolvedBoardImageUrl,
                  height: 180,
                  width: double.infinity,
                  fit: BoxFit.cover,
                  errorBuilder:
                      (BuildContext context, Object _, StackTrace? __) {
                    return Container(
                      height: 180,
                      width: double.infinity,
                      color: const Color(0xFFF5F5F5),
                      alignment: Alignment.center,
                      child: const Text('Unable to load board image preview'),
                    );
                  },
                ),
              ),
            ] else
              Container(
                height: 120,
                width: double.infinity,
                decoration: BoxDecoration(
                  color: const Color(0xFFF5F5F5),
                  border: Border.all(color: const Color(0xFFD4D4D4)),
                ),
                alignment: Alignment.center,
                child: const Text(
                    'Choose a board photo to start Cornifer authoring'),
              ),
            const SizedBox(height: 12),
            Row(
              children: <Widget>[
                Expanded(
                  child: FilledButton.tonal(
                    onPressed: communityState.actionInFlight
                        ? null
                        : () => unawaited(_pickCorniferBoardImage()),
                    child: const Text('Pick board photo'),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: FilledButton(
                    onPressed: communityState.actionInFlight || !signedIn
                        ? null
                        : () => unawaited(_createCorniferBoard()),
                    child: Text(boardDraft == null
                        ? 'Create board draft'
                        : 'Replace draft'),
                  ),
                ),
              ],
            ),
            if (boardDraft != null) ...<Widget>[
              const SizedBox(height: 22),
              Container(
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: const Color(0xFFF8FAFC),
                  border: Border.all(color: const Color(0xFFE2E8F0)),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Wrap(
                      spacing: 10,
                      runSpacing: 10,
                      children: <Widget>[
                        _InfoChip(label: boardDraft.name),
                        _InfoChip(label: boardDraft.location),
                        _InfoChip(
                          label: boardDraft.draft
                              ? 'Draft board'
                              : 'Published board',
                        ),
                        _InfoChip(label: '${boardDraft.holds.length} holds'),
                      ],
                    ),
                    if (boardDraft.description.isNotEmpty) ...<Widget>[
                      const SizedBox(height: 10),
                      Text(boardDraft.description),
                    ],
                  ],
                ),
              ),
              const SizedBox(height: 16),
              Row(
                children: <Widget>[
                  Expanded(
                    child: FilledButton.tonal(
                      onPressed: communityState.actionInFlight ||
                              !signedIn ||
                              !boardDraft.draft
                          ? null
                          : () => unawaited(_detectCorniferHolds()),
                      child: const Text('Run hold detection'),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: OutlinedButton(
                      onPressed: communityState.actionInFlight ||
                              !signedIn ||
                              !boardDraft.draft
                          ? null
                          : () => unawaited(_addCorniferHold()),
                      child: const Text('Add manual hold'),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              if (boardDraft.holds.isEmpty)
                const Text(
                  'No holds are attached to this board yet. Run detection or add them manually.',
                )
              else
                Column(
                  children: boardDraft.holds
                      .map(
                        (CorniferBoardHold hold) => Container(
                          margin: const EdgeInsets.only(bottom: 10),
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: Colors.white,
                            border: Border.all(color: const Color(0xFFE2E8F0)),
                          ),
                          child: Row(
                            children: <Widget>[
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: <Widget>[
                                    Text(
                                      'Hold ${hold.position + 1}',
                                      style: Theme.of(context)
                                          .textTheme
                                          .titleMedium,
                                    ),
                                    const SizedBox(height: 4),
                                    Text(
                                      'x ${hold.centroidX.toStringAsFixed(1)} · y ${hold.centroidY.toStringAsFixed(1)}',
                                    ),
                                  ],
                                ),
                              ),
                              IconButton(
                                onPressed: communityState.actionInFlight ||
                                        !signedIn ||
                                        !boardDraft.draft
                                    ? null
                                    : () => unawaited(_editCorniferHold(hold)),
                                icon: const Icon(Icons.edit_outlined),
                              ),
                              IconButton(
                                onPressed: communityState.actionInFlight ||
                                        !signedIn ||
                                        !boardDraft.draft
                                    ? null
                                    : () =>
                                        unawaited(_deleteCorniferHold(hold)),
                                icon: const Icon(Icons.delete_outline),
                              ),
                            ],
                          ),
                        ),
                      )
                      .toList(growable: false),
                ),
              if (boardDraft.holds.isNotEmpty && boardDraft.draft) ...<Widget>[
                const SizedBox(height: 8),
                FilledButton(
                  onPressed: communityState.actionInFlight || !signedIn
                      ? null
                      : () => unawaited(
                            _publishCorniferBoard(
                              controller: controller,
                              boardDraft: boardDraft,
                            ),
                          ),
                  child: const Text('Publish board'),
                ),
              ],
            ],
            if (boardDraft != null && !boardDraft.draft) ...<Widget>[
              const SizedBox(height: 24),
              Text(
                'Climb authoring',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 8),
              const Text(
                'Assign board holds into a climb with explicit roles. This keeps Cornifer climbs tied to the canonical board map instead of a one-off screenshot.',
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _corniferClimbNameController,
                decoration: const InputDecoration(labelText: 'Climb name'),
                textInputAction: TextInputAction.next,
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _corniferClimbGradeController,
                decoration: const InputDecoration(
                  labelText: 'Primary grade',
                  hintText: 'V5',
                ),
                textInputAction: TextInputAction.next,
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _corniferClimbDescriptionController,
                decoration:
                    const InputDecoration(labelText: 'Climb description'),
                minLines: 2,
                maxLines: 3,
              ),
              const SizedBox(height: 16),
              Text(
                'Hold roles',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const SizedBox(height: 8),
              ...boardDraft.holds.map(
                (CorniferBoardHold hold) => Padding(
                  padding: const EdgeInsets.only(bottom: 10),
                  child: DropdownButtonFormField<String>(
                    initialValue: _corniferHoldRoles[hold.id] ?? '',
                    decoration: InputDecoration(
                      labelText:
                          'Hold ${hold.position + 1} (${hold.centroidX.toStringAsFixed(0)}, ${hold.centroidY.toStringAsFixed(0)})',
                    ),
                    items: const <DropdownMenuItem<String>>[
                      DropdownMenuItem<String>(
                        value: '',
                        child: Text('Not used in this climb'),
                      ),
                      DropdownMenuItem<String>(
                        value: 'start',
                        child: Text('Start hold'),
                      ),
                      DropdownMenuItem<String>(
                        value: 'hand',
                        child: Text('Hand hold'),
                      ),
                      DropdownMenuItem<String>(
                        value: 'foothold',
                        child: Text('Foothold'),
                      ),
                      DropdownMenuItem<String>(
                        value: 'end',
                        child: Text('Finish hold'),
                      ),
                    ],
                    onChanged: communityState.actionInFlight || !signedIn
                        ? null
                        : (String? value) {
                            setState(() {
                              if (value == null || value.isEmpty) {
                                _corniferHoldRoles.remove(hold.id);
                              } else {
                                _corniferHoldRoles[hold.id] = value;
                              }
                            });
                          },
                  ),
                ),
              ),
              FilledButton(
                onPressed: communityState.actionInFlight || !signedIn
                    ? null
                    : () => unawaited(
                          _publishCorniferClimb(
                            controller: controller,
                            boardDraft: boardDraft,
                          ),
                        ),
                child: const Text('Publish climb'),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildCorniferEngagementSection({
    required BuildContext context,
    required CorniferCommunityState communityState,
    required ProviderClimb? climb,
  }) {
    if (climb == null) {
      return const SizedBox.shrink();
    }

    final int attemptCount = communityState.attemptCounts[climb.id] ??
        int.tryParse(climb.meta['attempt_count'] ?? '') ??
        0;
    final Map<String, int> ratingSummary =
        communityState.ratingSummaries[climb.id] ??
            <String, int>{
              'upvotes': int.tryParse(climb.meta['upvotes'] ?? '') ?? 0,
              'downvotes': int.tryParse(climb.meta['downvotes'] ?? '') ?? 0,
            };
    final int myRating = communityState.myRatings[climb.id] ??
        int.tryParse(climb.meta['my_rating'] ?? '') ??
        0;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(22),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              'Community actions',
              style: Theme.of(context).textTheme.headlineMedium,
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 10,
              runSpacing: 10,
              children: <Widget>[
                _InfoChip(label: '${ratingSummary['upvotes'] ?? 0} upvotes'),
                _InfoChip(
                    label: '${ratingSummary['downvotes'] ?? 0} downvotes'),
                _InfoChip(label: '$attemptCount tries logged'),
                if ((climb.meta['board_name'] ?? '').isNotEmpty)
                  _InfoChip(label: climb.meta['board_name']!),
                if ((climb.meta['location'] ?? '').isNotEmpty)
                  _InfoChip(label: climb.meta['location']!),
                if (myRating != 0)
                  _InfoChip(
                      label: myRating > 0 ? 'You upvoted' : 'You downvoted'),
              ],
            ),
            const SizedBox(height: 16),
            if (communityState.session == null)
              const Text(
                'Sign in above to log tries or rate this Cornifer climb.',
              )
            else ...<Widget>[
              Row(
                children: <Widget>[
                  Expanded(
                    child: TextField(
                      controller: _corniferAttemptController,
                      decoration: const InputDecoration(
                        labelText: 'Tries used',
                        hintText: '1',
                      ),
                      keyboardType: TextInputType.number,
                    ),
                  ),
                  const SizedBox(width: 12),
                  FilledButton(
                    onPressed: communityState.actionInFlight
                        ? null
                        : () => unawaited(_logCorniferAttempt(climb)),
                    child: const Text('Log tries'),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              Row(
                children: <Widget>[
                  Expanded(
                    child: FilledButton.tonalIcon(
                      onPressed: communityState.actionInFlight
                          ? null
                          : () => unawaited(_rateCorniferClimb(climb, 1)),
                      icon: const Icon(Icons.thumb_up_alt_outlined),
                      label: const Text('Upvote'),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: FilledButton.tonalIcon(
                      onPressed: communityState.actionInFlight
                          ? null
                          : () => unawaited(_rateCorniferClimb(climb, -1)),
                      icon: const Icon(Icons.thumb_down_alt_outlined),
                      label: const Text('Downvote'),
                    ),
                  ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }

  Future<void> _pickCorniferBoardImage() async {
    final XFile? file = await _imagePicker.pickImage(
      source: ImageSource.gallery,
      imageQuality: 90,
    );
    if (!mounted || file == null) {
      return;
    }
    setState(() {
      _corniferImagePath = file.path;
    });
  }

  Future<void> _registerCornifer() async {
    final ProviderSoloViewState state =
        ref.read(providerSoloControllerProvider(_args));
    await ref
        .read(corniferCommunityControllerProvider(state.server).notifier)
        .register(
          username: _corniferUsernameController.text,
          password: _corniferPasswordController.text,
        );
  }

  Future<void> _loginCornifer() async {
    final ProviderSoloViewState state =
        ref.read(providerSoloControllerProvider(_args));
    await ref
        .read(corniferCommunityControllerProvider(state.server).notifier)
        .login(
          username: _corniferUsernameController.text,
          password: _corniferPasswordController.text,
        );
  }

  Future<void> _logoutCornifer() async {
    final ProviderSoloViewState state =
        ref.read(providerSoloControllerProvider(_args));
    await ref
        .read(corniferCommunityControllerProvider(state.server).notifier)
        .logout();
  }

  Future<void> _createCorniferBoard() async {
    final ProviderSoloViewState state =
        ref.read(providerSoloControllerProvider(_args));
    if (_corniferImagePath == null || _corniferImagePath!.trim().isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
            content: Text('Pick a board photo before creating a board draft.')),
      );
      return;
    }
    final CorniferBoardDraft? draft = await ref
        .read(corniferCommunityControllerProvider(state.server).notifier)
        .createBoard(
          name: _corniferBoardNameController.text,
          location: _corniferBoardLocationController.text,
          description: _corniferBoardDescriptionController.text,
          imagePath: _corniferImagePath!,
        );
    if (draft == null || !mounted) {
      return;
    }
    setState(() {
      _corniferHoldRoles.clear();
      _corniferClimbNameController.clear();
      _corniferClimbGradeController.clear();
      _corniferClimbDescriptionController.clear();
    });
  }

  Future<void> _detectCorniferHolds() async {
    final ProviderSoloViewState state =
        ref.read(providerSoloControllerProvider(_args));
    await ref
        .read(corniferCommunityControllerProvider(state.server).notifier)
        .detectHolds();
  }

  Future<void> _addCorniferHold() async {
    final ProviderSoloViewState state =
        ref.read(providerSoloControllerProvider(_args));
    final CorniferCommunityController communityController =
        ref.read(corniferCommunityControllerProvider(state.server).notifier);
    final CorniferCommunityState communityState =
        ref.read(corniferCommunityControllerProvider(state.server));
    final CorniferBoardDraft? boardDraft = communityState.boardDraft;
    if (boardDraft == null) {
      return;
    }
    final CorniferBoardHold? created = await _showCorniferHoldEditor(
      suggestedPosition: boardDraft.holds.length,
    );
    if (created == null) {
      return;
    }
    await communityController.updateBoardHolds(
      <CorniferBoardHold>[...boardDraft.holds, created],
    );
  }

  Future<void> _editCorniferHold(CorniferBoardHold hold) async {
    final ProviderSoloViewState state =
        ref.read(providerSoloControllerProvider(_args));
    final CorniferCommunityController communityController =
        ref.read(corniferCommunityControllerProvider(state.server).notifier);
    final CorniferCommunityState communityState =
        ref.read(corniferCommunityControllerProvider(state.server));
    final CorniferBoardDraft? boardDraft = communityState.boardDraft;
    if (boardDraft == null) {
      return;
    }
    final CorniferBoardHold? updated = await _showCorniferHoldEditor(
      hold: hold,
      suggestedPosition: hold.position,
    );
    if (updated == null) {
      return;
    }
    await communityController.updateBoardHolds(
      boardDraft.holds
          .map((CorniferBoardHold item) => item.id == hold.id ? updated : item)
          .toList(growable: false),
    );
  }

  Future<void> _deleteCorniferHold(CorniferBoardHold hold) async {
    final ProviderSoloViewState state =
        ref.read(providerSoloControllerProvider(_args));
    final CorniferCommunityController communityController =
        ref.read(corniferCommunityControllerProvider(state.server).notifier);
    final CorniferCommunityState communityState =
        ref.read(corniferCommunityControllerProvider(state.server));
    final CorniferBoardDraft? boardDraft = communityState.boardDraft;
    if (boardDraft == null) {
      return;
    }
    await communityController.updateBoardHolds(
      boardDraft.holds
          .where((CorniferBoardHold item) => item.id != hold.id)
          .toList(growable: false),
    );
    if (!mounted) {
      return;
    }
    setState(() {
      _corniferHoldRoles.remove(hold.id);
    });
  }

  Future<void> _publishCorniferBoard({
    required ProviderSoloController controller,
    required CorniferBoardDraft boardDraft,
  }) async {
    final ProviderSoloViewState state =
        ref.read(providerSoloControllerProvider(_args));
    final CorniferBoardDraft? updated = await ref
        .read(corniferCommunityControllerProvider(state.server).notifier)
        .updateBoardHolds(
          boardDraft.holds,
          publish: true,
        );
    if (updated == null || !mounted) {
      return;
    }
    await _refreshCorniferCatalog(
      controller: controller,
      parentSurfaceId: updated.location,
      childSurfaceId: updated.id,
    );
  }

  Future<void> _publishCorniferClimb({
    required ProviderSoloController controller,
    required CorniferBoardDraft boardDraft,
  }) async {
    final ProviderSoloViewState state =
        ref.read(providerSoloControllerProvider(_args));
    final List<CorniferClimbSelection> selectedHolds = boardDraft.holds
        .where((CorniferBoardHold hold) =>
            (_corniferHoldRoles[hold.id] ?? '').isNotEmpty)
        .map(
          (CorniferBoardHold hold) => CorniferClimbSelection(
            boardHoldId: hold.id,
            role: _corniferHoldRoles[hold.id]!,
          ),
        )
        .toList(growable: false);
    final ProviderClimb? climb = await ref
        .read(corniferCommunityControllerProvider(state.server).notifier)
        .createClimb(
          boardId: boardDraft.id,
          name: _corniferClimbNameController.text,
          grade: _corniferClimbGradeController.text,
          description: _corniferClimbDescriptionController.text,
          holds: selectedHolds,
        );
    if (climb == null || !mounted) {
      return;
    }
    await _refreshCorniferCatalog(
      controller: controller,
      parentSurfaceId: boardDraft.location,
      childSurfaceId: boardDraft.id,
      climbId: climb.id,
    );
    setState(() {
      _corniferClimbNameController.clear();
      _corniferClimbGradeController.clear();
      _corniferClimbDescriptionController.clear();
      _corniferHoldRoles.clear();
    });
  }

  Future<void> _logCorniferAttempt(ProviderClimb climb) async {
    final ProviderSoloViewState state =
        ref.read(providerSoloControllerProvider(_args));
    final int tries = int.tryParse(_corniferAttemptController.text.trim()) ?? 0;
    await ref
        .read(corniferCommunityControllerProvider(state.server).notifier)
        .submitAttempt(
          climbId: climb.id,
          tries: tries,
        );
  }

  Future<void> _rateCorniferClimb(ProviderClimb climb, int value) async {
    final ProviderSoloViewState state =
        ref.read(providerSoloControllerProvider(_args));
    await ref
        .read(corniferCommunityControllerProvider(state.server).notifier)
        .rateClimb(
          climbId: climb.id,
          value: value,
        );
  }

  Future<void> _refreshCorniferCatalog({
    required ProviderSoloController controller,
    String? parentSurfaceId,
    String? childSurfaceId,
    String? climbId,
  }) async {
    await controller.unlockCatalog(const <String, String>{});
    if (parentSurfaceId != null && parentSurfaceId.isNotEmpty) {
      await controller.loadChildSurfaces(parentSurfaceId);
    }
    if (childSurfaceId != null && childSurfaceId.isNotEmpty) {
      await controller.selectChildSurface(childSurfaceId);
    }
    if (climbId != null && climbId.isNotEmpty) {
      await controller.selectClimb(climbId);
    }
  }

  Future<CorniferBoardHold?> _showCorniferHoldEditor({
    CorniferBoardHold? hold,
    required int suggestedPosition,
  }) async {
    final TextEditingController positionController = TextEditingController(
      text: '${hold?.position ?? suggestedPosition}',
    );
    final TextEditingController xController = TextEditingController(
      text: hold == null ? '' : hold.centroidX.toStringAsFixed(1),
    );
    final TextEditingController yController = TextEditingController(
      text: hold == null ? '' : hold.centroidY.toStringAsFixed(1),
    );

    final CorniferBoardHold? result = await showDialog<CorniferBoardHold>(
      context: context,
      builder: (BuildContext context) {
        return AlertDialog(
          title: Text(hold == null ? 'Add hold' : 'Edit hold'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              TextField(
                controller: positionController,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(labelText: 'Position'),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: xController,
                keyboardType:
                    const TextInputType.numberWithOptions(decimal: true),
                decoration: const InputDecoration(labelText: 'Centroid X'),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: yController,
                keyboardType:
                    const TextInputType.numberWithOptions(decimal: true),
                decoration: const InputDecoration(labelText: 'Centroid Y'),
              ),
            ],
          ),
          actions: <Widget>[
            TextButton(
              onPressed: () => Navigator.of(context).pop(),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () {
                final int? position =
                    int.tryParse(positionController.text.trim());
                final double? centroidX =
                    double.tryParse(xController.text.trim());
                final double? centroidY =
                    double.tryParse(yController.text.trim());
                if (position == null ||
                    centroidX == null ||
                    centroidY == null) {
                  return;
                }
                Navigator.of(context).pop(
                  CorniferBoardHold(
                    id: hold?.id ??
                        'hold-${DateTime.now().microsecondsSinceEpoch}',
                    position: position,
                    centroidX: centroidX,
                    centroidY: centroidY,
                    contour: hold?.contour ?? const <List<num>>[],
                  ),
                );
              },
              child: const Text('Save'),
            ),
          ],
        );
      },
    );

    positionController.dispose();
    xController.dispose();
    yController.dispose();
    return result;
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

class _OpenCatalogCard extends StatelessWidget {
  const _OpenCatalogCard({
    required this.capability,
    required this.surfacesLoading,
    required this.accessLoaded,
    required this.onRefresh,
  });

  final ProviderCapability capability;
  final bool surfacesLoading;
  final bool accessLoaded;
  final VoidCallback onRefresh;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(22),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              '${capability.label} catalog',
              style: Theme.of(context).textTheme.headlineMedium,
            ),
            const SizedBox(height: 8),
            Text(
              accessLoaded
                  ? 'This provider is open-read on the active server. The catalog is already available for solo browse and room seeding.'
                  : 'This provider does not need a reconnect secret. Kilter Together loads it directly from the active server.',
            ),
            const SizedBox(height: 16),
            Row(
              children: <Widget>[
                Expanded(
                  child: FilledButton.tonal(
                    onPressed: surfacesLoading ? null : onRefresh,
                    child: Text(
                      surfacesLoading ? 'Refreshing...' : 'Refresh catalog',
                    ),
                  ),
                ),
                if (accessLoaded) ...<Widget>[
                  const SizedBox(width: 12),
                  const Chip(label: Text('Open-read')),
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
    required this.selectedClimbIds,
    required this.queryController,
    required this.gradeMinController,
    required this.gradeMaxController,
    required this.onApplyQuery,
    required this.onSortChanged,
    required this.onSelectClimb,
    required this.onLongPressClimb,
    required this.onTogglePlannedClimb,
    required this.onAddSelectedToShortlist,
    required this.onClearMultiSelect,
    required this.onPreviousPage,
    required this.onNextPage,
  });

  final ProviderSoloViewState state;
  final Set<String> selectedClimbIds;
  final TextEditingController queryController;
  final TextEditingController gradeMinController;
  final TextEditingController gradeMaxController;
  final VoidCallback onApplyQuery;
  final ValueChanged<String?> onSortChanged;
  final ValueChanged<ProviderClimb> onSelectClimb;
  final ValueChanged<ProviderClimb> onLongPressClimb;
  final ValueChanged<ProviderClimb> onTogglePlannedClimb;
  final VoidCallback onAddSelectedToShortlist;
  final VoidCallback onClearMultiSelect;
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
            Row(
              children: <Widget>[
                Expanded(
                  child: TextField(
                    controller: gradeMinController,
                    decoration: const InputDecoration(
                        labelText: 'Grade min', hintText: 'V3'),
                    textInputAction: TextInputAction.next,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: TextField(
                    controller: gradeMaxController,
                    decoration: const InputDecoration(
                        labelText: 'Grade max', hintText: 'V8'),
                    textInputAction: TextInputAction.search,
                    onSubmitted: (_) => onApplyQuery(),
                  ),
                ),
              ],
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
              Center(child: ClimbingLoader())
            else if (state.climbs.isEmpty)
              const Text('No climbs match the current provider filters.')
            else
              Column(
                children: state.climbs.map(
                  (ProviderClimb climb) {
                    final bool isMultiSelected =
                        selectedClimbIds.contains(climb.id);
                    return Padding(
                      padding: const EdgeInsets.only(bottom: 10),
                      child: InkWell(
                        borderRadius: BorderRadius.zero,
                        onTap: selectedClimbIds.isNotEmpty
                            ? () => onLongPressClimb(climb)
                            : () => onSelectClimb(climb),
                        onLongPress: () => onLongPressClimb(climb),
                        child: Stack(
                          children: <Widget>[
                            Ink(
                              decoration: BoxDecoration(
                                borderRadius: BorderRadius.zero,
                                border: Border.all(
                                  color: isMultiSelected
                                      ? const Color(0xFF1A1A1A)
                                      : state.selectedClimb?.id == climb.id
                                          ? const Color(0xFF1A1A1A)
                                          : const Color(0xFFE2E8F0),
                                  width: isMultiSelected ||
                                          state.selectedClimb?.id == climb.id
                                      ? 1.4
                                      : 1,
                                ),
                                color: isMultiSelected
                                    ? const Color(0xFFF0F0F0)
                                    : state.selectedClimb?.id == climb.id
                                        ? const Color(0xFFF5F5F5)
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
                                          ].join(' · '),
                                          style: Theme.of(context)
                                              .textTheme
                                              .bodySmall,
                                        ),
                                        if (_hasClimbMeta(climb)) ...<Widget>[
                                          const SizedBox(height: 6),
                                          Wrap(
                                            spacing: 8,
                                            runSpacing: 6,
                                            children: <Widget>[
                                              if ((climb.meta['color'] ?? '')
                                                  .isNotEmpty)
                                                _ColorDot(
                                                    color: _parseClimbColor(
                                                        climb.meta['color']!)),
                                              if ((climb.meta['hold_type'] ??
                                                      '')
                                                  .isNotEmpty)
                                                _InfoChip(
                                                    label: climb
                                                        .meta['hold_type']!),
                                              if ((climb.meta['foot_rule'] ??
                                                      '')
                                                  .isNotEmpty)
                                                _InfoChip(
                                                    label: climb
                                                        .meta['foot_rule']!),
                                            ],
                                          ),
                                        ],
                                      ],
                                    ),
                                  ),
                                  IconButton(
                                    onPressed: () =>
                                        onTogglePlannedClimb(climb),
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
                            if (selectedClimbIds.isNotEmpty)
                              Positioned(
                                top: 8,
                                right: 8,
                                child: Icon(
                                  isMultiSelected
                                      ? Icons.check_box
                                      : Icons.check_box_outline_blank,
                                  size: 22,
                                  color: const Color(0xFF1A1A1A),
                                ),
                              ),
                          ],
                        ),
                      ),
                    );
                  },
                ).toList(growable: false),
              ),
            if (selectedClimbIds.isNotEmpty) ...<Widget>[
              const SizedBox(height: 10),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: const Color(0xFFF5F5F5),
                  borderRadius: BorderRadius.zero,
                  border: Border.all(color: const Color(0xFFD4D4D4)),
                ),
                child: Row(
                  children: <Widget>[
                    Text('${selectedClimbIds.length} selected'),
                    const Spacer(),
                    FilledButton.tonal(
                      onPressed: onAddSelectedToShortlist,
                      child: const Text('Add to shortlist'),
                    ),
                    const SizedBox(width: 8),
                    OutlinedButton(
                      onPressed: onClearMultiSelect,
                      child: const Text('Done'),
                    ),
                  ],
                ),
              ),
            ],
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
      return Card(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Center(child: ClimbingLoader()),
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
          borderRadius: BorderRadius.zero,
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

bool _hasClimbMeta(ProviderClimb climb) {
  return (climb.meta['color'] ?? '').isNotEmpty ||
      (climb.meta['hold_type'] ?? '').isNotEmpty ||
      (climb.meta['foot_rule'] ?? '').isNotEmpty;
}

Color _parseClimbColor(String raw) {
  return switch (raw.toLowerCase().trim()) {
    'green' => const Color(0xFF16A34A),
    'blue' => const Color(0xFF2563EB),
    'red' => const Color(0xFFDC2626),
    'yellow' => const Color(0xFFEAB308),
    'orange' => const Color(0xFFEA580C),
    'purple' => const Color(0xFF9333EA),
    'pink' => const Color(0xFFEC4899),
    'white' => const Color(0xFFE2E8F0),
    'black' => const Color(0xFF1E293B),
    _ => const Color(0xFF6B7280),
  };
}

class _ColorDot extends StatelessWidget {
  const _ColorDot({required this.color});
  final Color color;
  @override
  Widget build(BuildContext context) {
    return Container(
      width: 10,
      height: 10,
      decoration: BoxDecoration(shape: BoxShape.circle, color: color),
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
        color: const Color(0xFFF5F5F5),
        borderRadius: BorderRadius.zero,
        border: Border.all(color: const Color(0xFFD4D4D4)),
      ),
      child: Text(label),
    );
  }
}
