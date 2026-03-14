import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:share_plus/share_plus.dart';

import '../../../core/deep_links/invite_links.dart';
import '../../../core/models/app_prefs_models.dart';
import '../../../core/models/board_models.dart';
import '../../../core/models/product_models.dart';
import '../../../core/models/provider_models.dart';
import '../../../core/models/session_models.dart';
import '../../../core/network/api_client.dart';
import '../../../core/presentation/climb_media_preview.dart';
import '../../../core/presentation/flow_guide_sheet.dart';
import '../../../core/presentation/gradient_scaffold.dart';
import '../../../core/storage/app_prefs_controller.dart';
import '../../../core/storage/offline_kilter_catalog_repository.dart';
import '../application/solo_board_controller.dart';

const List<int> _angleOptions = <int>[
  5,
  10,
  15,
  20,
  25,
  30,
  35,
  40,
  45,
  50,
  55,
  60,
  65,
  70
];
const List<String> _sortOptions = <String>['popular', 'newest'];
const FlowGuideContent _soloBoardGuide = FlowGuideContent(
  eyebrow: 'Solo board guide',
  title: 'Use this board as a planning workspace',
  summary:
      'This screen is the detailed solo workspace: filter the climb list, keep favorites or shortlist state, and turn a board plan into a room seed when you are ready.',
  sections: <FlowGuideSection>[
    FlowGuideSection(
      title: 'Tune the board context',
      body:
          'Adjust board, angle, sort, query, setter, and grade until the catalog matches the session you want to plan.',
    ),
    FlowGuideSection(
      title: 'Save what matters',
      body:
          'Use favorites for durable keepers, shortlist for the current session idea, and saved presets when you want to reopen the same filter stack later.',
    ),
    FlowGuideSection(
      title: 'Promote into a shared session',
      body:
          'Once the shortlist feels right, seed a new room or share the plan so the host flow starts with the same surface and climb context.',
    ),
  ],
  completionLabel: 'Mark solo guide complete',
);

class SoloBoardScreen extends ConsumerStatefulWidget {
  const SoloBoardScreen({
    super.key,
    required this.boardId,
    this.initialServer,
    this.initialAngle,
    this.initialSort,
    this.initialQuery,
    this.initialSetter,
    this.initialGrade,
    this.initialClimbUuid,
  });

  final String boardId;
  final String? initialServer;
  final int? initialAngle;
  final String? initialSort;
  final String? initialQuery;
  final String? initialSetter;
  final String? initialGrade;
  final String? initialClimbUuid;

  @override
  ConsumerState<SoloBoardScreen> createState() => _SoloBoardScreenState();
}

class _SoloBoardScreenState extends ConsumerState<SoloBoardScreen> {
  late final TextEditingController _queryController =
      TextEditingController(text: widget.initialQuery ?? '');
  late final TextEditingController _setterController =
      TextEditingController(text: widget.initialSetter ?? '');
  late final TextEditingController _gradeController =
      TextEditingController(text: widget.initialGrade ?? '');
  final TextEditingController _planTitleController = TextEditingController();
  final TextEditingController _planNotesController = TextEditingController();
  bool _autoGuideAttempted = false;

  SoloBoardRouteArgs get _args => SoloBoardRouteArgs(
        boardId: widget.boardId,
        initialServer: widget.initialServer,
        initialAngle: widget.initialAngle,
        initialSort: widget.initialSort,
        initialQuery: widget.initialQuery,
        initialSetter: widget.initialSetter,
        initialGrade: widget.initialGrade,
        initialClimbUuid: widget.initialClimbUuid,
      );

  @override
  void dispose() {
    _queryController.dispose();
    _setterController.dispose();
    _gradeController.dispose();
    _planTitleController.dispose();
    _planNotesController.dispose();
    super.dispose();
  }

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
      content: _soloBoardGuide,
      completed: prefs.guidedTour.soloCompleted,
    );
    if (result != FlowGuideResult.completed || !mounted) {
      return;
    }
    await ref.read(appPrefsControllerProvider.notifier).completeGuideBranch(
          'solo',
        );
  }

  @override
  Widget build(BuildContext context) {
    final SoloBoardViewState state =
        ref.watch(soloBoardControllerProvider(_args));
    final SoloBoardController controller =
        ref.read(soloBoardControllerProvider(_args).notifier);
    final AsyncValue<AppPrefs> prefsValue =
        ref.watch(appPrefsControllerProvider);
    final AppPrefs prefs = prefsValue.valueOrNull ?? AppPrefs.defaults();
    final ApiClient apiClient = ref.read(apiClientProvider);
    final OfflineKilterCatalogRepository catalogRepository =
        ref.read(offlineKilterCatalogRepositoryProvider);
    final BoardOption? board = state.board;
    final BoardClimb? selectedClimb = state.selectedClimb;
    final SoloSavedClimb? selectedSavedClimb =
        _buildSelectedSavedClimb(state, board, selectedClimb);
    final String presetId = _buildPresetId(state);
    final bool presetSaved = prefs.savedSoloFilters
        .any((SoloFilterPreset item) => item.id == presetId);
    final bool isFavorite = selectedSavedClimb != null &&
        prefs.soloFavorites
            .any((SoloSavedClimb item) => item.key == selectedSavedClimb.key);
    final bool isShortlisted = selectedSavedClimb != null &&
        prefs.soloShortlist
            .any((SoloSavedClimb item) => item.key == selectedSavedClimb.key);
    final List<SoloSavedClimb> shortlistForBoard = prefs.soloShortlist
        .where(
          (SoloSavedClimb item) =>
              item.boardId == state.boardId && item.angle == state.angle,
        )
        .toList(growable: false);

    if (prefsValue.hasValue) {
      _maybeAutoOpenGuide(prefs);
    }

    if (_planTitleController.text.isEmpty && board != null) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (!mounted || _planTitleController.text.isNotEmpty) {
          return;
        }
        _planTitleController.text = '${board.kilterName} plan';
      });
    }

    return GradientScaffold(
      title: board?.kilterName.isNotEmpty == true
          ? board!.kilterName
          : 'Solo board',
      subtitle: state.server == null
          ? 'Choose a self-hosted server before using solo browse.'
          : '${describeServer(state.server!)} · Board ${state.boardId}',
      actions: <Widget>[
        IconButton(
          onPressed: () => unawaited(_openGuide()),
          icon: const Icon(Icons.help_outline),
        ),
        IconButton(
          onPressed:
              state.pageLoading ? null : () => unawaited(controller.refresh()),
          icon: Icon(state.pageLoading ? Icons.sync : Icons.refresh),
        ),
        IconButton(
          onPressed: () => context.goNamed('solo-entry'),
          icon: const Icon(Icons.arrow_back),
        ),
      ],
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          if (state.errorMessage != null) ...<Widget>[
            _MessageCard(
              title: 'Unable to load solo browse',
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
          if (state.missingServer)
            _MissingServerCard(onJoin: () => context.goNamed('join-room'))
          else if (state.loading && board == null)
            const Card(
              child: Padding(
                padding: EdgeInsets.all(32),
                child: Center(child: CircularProgressIndicator()),
              ),
            )
          else if (board == null)
            const Card(
              child: Padding(
                padding: EdgeInsets.all(22),
                child:
                    Text('This board is not available on the active server.'),
              ),
            )
          else
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                _BoardHeaderCard(
                  state: state,
                  shortlistCount: shortlistForBoard.length,
                  onBoardChanged: (String? nextBoardId) {
                    if (nextBoardId == null || nextBoardId == state.boardId) {
                      return;
                    }
                    context.goNamed(
                      'solo-board',
                      pathParameters: <String, String>{'boardId': nextBoardId},
                      queryParameters: <String, String>{
                        if (state.server != null)
                          'server': state.server!.toString(),
                        'angle': '${state.angle}',
                        'sort': state.sort,
                        if (state.query.trim().isNotEmpty)
                          'q': state.query.trim(),
                        if (state.setter.trim().isNotEmpty)
                          'setter': state.setter.trim(),
                        if (state.grade.trim().isNotEmpty)
                          'grade': state.grade.trim(),
                      },
                    );
                  },
                ),
                const SizedBox(height: 14),
                _FiltersCard(
                  state: state,
                  queryController: _queryController,
                  setterController: _setterController,
                  gradeController: _gradeController,
                  presetSaved: presetSaved,
                  onAngleChanged: (int value) =>
                      unawaited(controller.updateBoardContext(angle: value)),
                  onSortChanged: (String? value) {
                    if (value == null) {
                      return;
                    }
                    unawaited(controller.updateBoardContext(sort: value));
                  },
                  onApply: () => unawaited(
                    controller.updateBoardContext(
                      query: _queryController.text,
                      setter: _setterController.text,
                      grade: _gradeController.text,
                    ),
                  ),
                  onClear: () {
                    _queryController.clear();
                    _setterController.clear();
                    _gradeController.clear();
                    unawaited(
                      controller.updateBoardContext(
                        query: '',
                        setter: '',
                        grade: '',
                      ),
                    );
                  },
                  onTogglePreset: () async {
                    final AppPrefsController appPrefsController =
                        ref.read(appPrefsControllerProvider.notifier);
                    if (presetSaved) {
                      await appPrefsController.removeSoloFilterPreset(presetId);
                    } else {
                      await appPrefsController.saveSoloFilterPreset(
                        _buildPreset(state, board),
                      );
                    }
                  },
                ),
                const SizedBox(height: 14),
                _CurrentActionsCard(
                  selectedClimb: selectedClimb,
                  shortlistCount: shortlistForBoard.length,
                  isFavorite: isFavorite,
                  isShortlisted: isShortlisted,
                  actionInFlight: state.actionInFlight,
                  planTitleController: _planTitleController,
                  planNotesController: _planNotesController,
                  onToggleFavorite: selectedSavedClimb == null
                      ? null
                      : () => unawaited(
                            ref
                                .read(appPrefsControllerProvider.notifier)
                                .toggleSoloFavorite(selectedSavedClimb),
                          ),
                  onToggleShortlist: selectedSavedClimb == null
                      ? null
                      : () => unawaited(
                            ref
                                .read(appPrefsControllerProvider.notifier)
                                .toggleSoloShortlist(selectedSavedClimb),
                          ),
                  onSeedRoom: () => unawaited(
                    _seedRoom(
                      context: context,
                      controller: controller,
                      board: board,
                      state: state,
                      shortlist: shortlistForBoard,
                      selectedSavedClimb: selectedSavedClimb,
                      apiClient: apiClient,
                    ),
                  ),
                  onSharePlan: () => unawaited(
                    _sharePlan(
                      context: context,
                      controller: controller,
                      board: board,
                      state: state,
                      shortlist: shortlistForBoard,
                      selectedSavedClimb: selectedSavedClimb,
                      prefs: prefs,
                      apiClient: apiClient,
                    ),
                  ),
                ),
                const SizedBox(height: 14),
                _SelectedClimbCard(
                  climb: selectedClimb,
                  board: board,
                  angle: state.angle,
                  catalogRepository: catalogRepository,
                ),
                const SizedBox(height: 14),
                _ClimbCatalogCard(
                  state: state,
                  onSelectClimb: (BoardClimb climb) =>
                      unawaited(controller.selectClimb(climb.uuid)),
                  onPreviousPage: state.currentPage <= 1
                      ? null
                      : () => unawaited(controller.previousPage()),
                  onNextPage: state.hasNextPage
                      ? () => unawaited(controller.nextPage())
                      : null,
                ),
              ],
            ),
        ],
      ),
    );
  }

  Future<void> _seedRoom({
    required BuildContext context,
    required SoloBoardController controller,
    required BoardOption board,
    required SoloBoardViewState state,
    required List<SoloSavedClimb> shortlist,
    required SoloSavedClimb? selectedSavedClimb,
    required ApiClient apiClient,
  }) async {
    final GoRouter router = GoRouter.of(context);
    final List<ProviderClimb> climbs = shortlist.isNotEmpty
        ? shortlist
            .map((SoloSavedClimb item) => _providerClimbFromSaved(item,
                apiClient: apiClient, server: state.server))
            .toList(growable: false)
        : selectedSavedClimb == null
            ? const <ProviderClimb>[]
            : <ProviderClimb>[
                _providerClimbFromSaved(
                  selectedSavedClimb,
                  apiClient: apiClient,
                  server: state.server,
                ),
              ];

    await controller.beginRoomSeed(
      climbs: climbs,
      title: board.kilterName,
    );
    if (!mounted) {
      return;
    }
    router.goNamed('create-room');
  }

  Future<void> _sharePlan({
    required BuildContext context,
    required SoloBoardController controller,
    required BoardOption board,
    required SoloBoardViewState state,
    required List<SoloSavedClimb> shortlist,
    required SoloSavedClimb? selectedSavedClimb,
    required AppPrefs prefs,
    required ApiClient apiClient,
  }) async {
    final ScaffoldMessengerState messenger = ScaffoldMessenger.of(context);
    final List<ProviderClimb> climbs = shortlist.isNotEmpty
        ? shortlist
            .map((SoloSavedClimb item) => _providerClimbFromSaved(item,
                apiClient: apiClient, server: state.server))
            .toList(growable: false)
        : selectedSavedClimb == null
            ? const <ProviderClimb>[]
            : <ProviderClimb>[
                _providerClimbFromSaved(
                  selectedSavedClimb,
                  apiClient: apiClient,
                  server: state.server,
                ),
              ];

    if (climbs.isEmpty || state.server == null) {
      messenger.showSnackBar(
        const SnackBar(
            content:
                Text('Select or shortlist a climb before sharing a plan.')),
      );
      return;
    }

    final SoloPlanSnapshot? plan = await controller.createPlan(
      title: _planTitleController.text,
      notes: _planNotesController.text,
      climbs: climbs,
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

class _BoardHeaderCard extends StatelessWidget {
  const _BoardHeaderCard({
    required this.state,
    required this.shortlistCount,
    required this.onBoardChanged,
  });

  final SoloBoardViewState state;
  final int shortlistCount;
  final ValueChanged<String?> onBoardChanged;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(22),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              'Board context',
              style: Theme.of(context).textTheme.headlineMedium,
            ),
            const SizedBox(height: 12),
            DropdownButtonFormField<String>(
              initialValue: state.boardId,
              decoration: const InputDecoration(labelText: 'Board'),
              items: state.boards
                  .map(
                    (BoardOption board) => DropdownMenuItem<String>(
                      value: '${board.id}',
                      child: Text(board.kilterName),
                    ),
                  )
                  .toList(growable: false),
              onChanged: onBoardChanged,
            ),
            const SizedBox(height: 16),
            Wrap(
              spacing: 10,
              runSpacing: 10,
              children: <Widget>[
                _InfoChip(label: '${state.angle}°'),
                _InfoChip(label: 'Sort: ${state.sort}'),
                _InfoChip(
                    label:
                        '${state.climbs.length} climbs on page ${state.currentPage}'),
                _InfoChip(label: '$shortlistCount shortlisted'),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _FiltersCard extends StatelessWidget {
  const _FiltersCard({
    required this.state,
    required this.queryController,
    required this.setterController,
    required this.gradeController,
    required this.presetSaved,
    required this.onAngleChanged,
    required this.onSortChanged,
    required this.onApply,
    required this.onClear,
    required this.onTogglePreset,
  });

  final SoloBoardViewState state;
  final TextEditingController queryController;
  final TextEditingController setterController;
  final TextEditingController gradeController;
  final bool presetSaved;
  final ValueChanged<int> onAngleChanged;
  final ValueChanged<String?> onSortChanged;
  final VoidCallback onApply;
  final VoidCallback onClear;
  final VoidCallback onTogglePreset;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(22),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              'Filters',
              style: Theme.of(context).textTheme.headlineMedium,
            ),
            const SizedBox(height: 8),
            const Text(
              'Tune the local Kilter dataset by angle, search, setter, grade, and sort order. The current view is persisted as solo resume state.',
            ),
            const SizedBox(height: 16),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: _angleOptions
                  .map(
                    (int angle) => ChoiceChip(
                      label: Text('$angle°'),
                      selected: state.angle == angle,
                      onSelected: (_) => onAngleChanged(angle),
                    ),
                  )
                  .toList(growable: false),
            ),
            const SizedBox(height: 16),
            DropdownButtonFormField<String>(
              initialValue: state.sort,
              decoration: const InputDecoration(labelText: 'Sort'),
              items: _sortOptions
                  .map(
                    (String option) => DropdownMenuItem<String>(
                      value: option,
                      child: Text(option),
                    ),
                  )
                  .toList(growable: false),
              onChanged: onSortChanged,
            ),
            const SizedBox(height: 12),
            TextField(
              controller: queryController,
              decoration: const InputDecoration(
                labelText: 'Search climb name',
                hintText: 'Compression, prow, warm-up...',
              ),
              textInputAction: TextInputAction.search,
              onSubmitted: (_) => onApply(),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: setterController,
              decoration: const InputDecoration(
                labelText: 'Setter',
                hintText: 'setter-a',
              ),
              textInputAction: TextInputAction.search,
              onSubmitted: (_) => onApply(),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: gradeController,
              decoration: const InputDecoration(
                labelText: 'Grade',
                hintText: '7a',
              ),
              textInputAction: TextInputAction.search,
              onSubmitted: (_) => onApply(),
            ),
            const SizedBox(height: 16),
            Row(
              children: <Widget>[
                Expanded(
                  child: FilledButton(
                    onPressed: onApply,
                    child: const Text('Apply filters'),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: FilledButton.tonal(
                    onPressed: onClear,
                    child: const Text('Clear filters'),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            OutlinedButton.icon(
              onPressed: onTogglePreset,
              icon: Icon(presetSaved
                  ? Icons.delete_outline
                  : Icons.bookmark_add_outlined),
              label: Text(
                  presetSaved ? 'Remove saved filter' : 'Save filter preset'),
            ),
          ],
        ),
      ),
    );
  }
}

class _CurrentActionsCard extends StatelessWidget {
  const _CurrentActionsCard({
    required this.selectedClimb,
    required this.shortlistCount,
    required this.isFavorite,
    required this.isShortlisted,
    required this.actionInFlight,
    required this.planTitleController,
    required this.planNotesController,
    required this.onToggleFavorite,
    required this.onToggleShortlist,
    required this.onSeedRoom,
    required this.onSharePlan,
  });

  final BoardClimb? selectedClimb;
  final int shortlistCount;
  final bool isFavorite;
  final bool isShortlisted;
  final bool actionInFlight;
  final TextEditingController planTitleController;
  final TextEditingController planNotesController;
  final VoidCallback? onToggleFavorite;
  final VoidCallback? onToggleShortlist;
  final VoidCallback onSeedRoom;
  final VoidCallback onSharePlan;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(22),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              'Current solo actions',
              style: Theme.of(context).textTheme.headlineMedium,
            ),
            const SizedBox(height: 8),
            Text(
              selectedClimb == null
                  ? 'Select a climb to pin it as a favorite, shortlist it, or seed a room from the current board context.'
                  : '${selectedClimb!.climbName} is active. Favorites and shortlist entries stay on-device, while room seeds and shared plans can leave the phone.',
            ),
            const SizedBox(height: 16),
            Wrap(
              spacing: 10,
              runSpacing: 10,
              children: <Widget>[
                FilledButton.tonalIcon(
                  onPressed: onToggleFavorite,
                  icon:
                      Icon(isFavorite ? Icons.favorite : Icons.favorite_border),
                  label: Text(isFavorite ? 'Saved favorite' : 'Add favorite'),
                ),
                FilledButton.tonalIcon(
                  onPressed: onToggleShortlist,
                  icon: Icon(
                      isShortlisted ? Icons.checklist_rtl : Icons.playlist_add),
                  label: Text(isShortlisted ? 'In shortlist' : 'Add shortlist'),
                ),
              ],
            ),
            const SizedBox(height: 18),
            TextField(
              controller: planTitleController,
              decoration: const InputDecoration(
                labelText: 'Plan title',
                hintText: 'Board plan',
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: planNotesController,
              decoration: const InputDecoration(
                labelText: 'Plan notes',
                hintText: 'Short warm-up circuit or session note',
              ),
              minLines: 2,
              maxLines: 3,
            ),
            const SizedBox(height: 16),
            Row(
              children: <Widget>[
                Expanded(
                  child: FilledButton(
                    onPressed: actionInFlight ? null : onSharePlan,
                    child: Text(
                      shortlistCount > 0
                          ? 'Share shortlist plan'
                          : 'Share current climb',
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: OutlinedButton(
                    onPressed: actionInFlight ? null : onSeedRoom,
                    child: Text(
                      shortlistCount > 0
                          ? 'Start room from shortlist'
                          : 'Start room from current view',
                    ),
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

class _SelectedClimbCard extends StatelessWidget {
  const _SelectedClimbCard({
    required this.climb,
    required this.board,
    required this.angle,
    required this.catalogRepository,
  });

  final BoardClimb? climb;
  final BoardOption board;
  final int angle;
  final OfflineKilterCatalogRepository catalogRepository;

  @override
  Widget build(BuildContext context) {
    if (climb == null) {
      return const Card(
        child: Padding(
          padding: EdgeInsets.all(22),
          child: Text('No climbs matched the current filters.'),
        ),
      );
    }

    final String? grade = climb!.gradeForAngle(angle);

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(22),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              climb!.climbName,
              style: Theme.of(context).textTheme.headlineMedium,
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 10,
              runSpacing: 10,
              children: <Widget>[
                _InfoChip(
                    label: grade == null || grade.isEmpty
                        ? 'Grade unavailable'
                        : grade),
                _InfoChip(label: climb!.setterName),
                _InfoChip(label: '${climb!.ascends} ascends'),
                _InfoChip(label: board.name),
              ],
            ),
            if ((climb!.description ?? '').isNotEmpty) ...<Widget>[
              const SizedBox(height: 12),
              Text(climb!.description!),
            ],
            const SizedBox(height: 18),
            FutureBuilder<List<String>>(
              future: _resolveImagePaths(climb!),
              builder:
                  (BuildContext context, AsyncSnapshot<List<String>> snapshot) {
                final List<String> imageUrls =
                    snapshot.data ?? const <String>[];
                return ClimbMediaPreview(
                  imageUrls: imageUrls,
                  highlightedHolds: climb!.highlightedHolds,
                  emptyMessage: 'No board images available for this climb',
                  errorMessage: 'Unable to load board image layers',
                );
              },
            ),
          ],
        ),
      ),
    );
  }

  Future<List<String>> _resolveImagePaths(BoardClimb climb) async {
    final List<String> imageUrls = <String>[];
    for (final String filename in climb.imageFilenames) {
      final String? imagePath =
          await catalogRepository.resolveImagePath(filename);
      if (imagePath != null) {
        imageUrls.add(imagePath);
      }
    }
    return imageUrls;
  }
}

class _ClimbCatalogCard extends StatelessWidget {
  const _ClimbCatalogCard({
    required this.state,
    required this.onSelectClimb,
    required this.onPreviousPage,
    required this.onNextPage,
  });

  final SoloBoardViewState state;
  final ValueChanged<BoardClimb> onSelectClimb;
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
            Row(
              children: <Widget>[
                Expanded(
                  child: Text(
                    'Climbs',
                    style: Theme.of(context).textTheme.headlineMedium,
                  ),
                ),
                if (state.pageLoading)
                  const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator()),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              'Page ${state.currentPage}${state.hasNextPage ? ' · more available' : ''}',
            ),
            const SizedBox(height: 16),
            if (state.climbs.isEmpty)
              const Text('No climbs matched the current filters.')
            else
              Column(
                children: state.climbs
                    .map(
                      (BoardClimb climb) => Padding(
                        padding: const EdgeInsets.only(bottom: 10),
                        child: InkWell(
                          borderRadius: BorderRadius.circular(20),
                          onTap: () => onSelectClimb(climb),
                          child: Ink(
                            decoration: BoxDecoration(
                              borderRadius: BorderRadius.circular(20),
                              border: Border.all(
                                color: state.selectedClimb?.uuid == climb.uuid
                                    ? const Color(0xFF0F766E)
                                    : const Color(0xFFE2E8F0),
                                width: state.selectedClimb?.uuid == climb.uuid
                                    ? 1.4
                                    : 1,
                              ),
                              color: state.selectedClimb?.uuid == climb.uuid
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
                                        climb.climbName,
                                        style: Theme.of(context)
                                            .textTheme
                                            .titleLarge,
                                      ),
                                      const SizedBox(height: 4),
                                      Text(climb.setterName),
                                      const SizedBox(height: 4),
                                      Text(
                                        [
                                          if ((climb.gradeForAngle(
                                                      state.angle) ??
                                                  '')
                                              .isNotEmpty)
                                            climb.gradeForAngle(state.angle)!,
                                          '${climb.ascends} ascends',
                                        ].join(' · '),
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
              'Join or host a room first so the mobile app knows which self-hosted node should serve the Kilter dataset and board images.',
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

SoloSavedClimb? _buildSelectedSavedClimb(
  SoloBoardViewState state,
  BoardOption? board,
  BoardClimb? climb,
) {
  if (board == null || climb == null) {
    return null;
  }
  return SoloSavedClimb(
    uuid: climb.uuid,
    productSizeId: climb.productSizeId,
    climbName: climb.climbName,
    setterName: climb.setterName,
    boardId: state.boardId,
    boardName: board.kilterName,
    angle: state.angle,
    ascends: climb.ascends,
    savedAt: DateTime.now().toUtc().toIso8601String(),
    grade: climb.gradeForAngle(state.angle),
    imageFilename:
        climb.imageFilenames.isEmpty ? null : climb.imageFilenames.first,
  );
}

SoloFilterPreset _buildPreset(SoloBoardViewState state, BoardOption board) {
  return SoloFilterPreset(
    id: _buildPresetId(state),
    label: _buildPresetLabel(state, board),
    boardId: state.boardId,
    boardName: board.kilterName,
    angle: state.angle,
    sort: state.sort,
    savedAt: DateTime.now().toUtc().toIso8601String(),
    q: state.query.trim().isEmpty ? null : state.query.trim(),
    setter: state.setter.trim().isEmpty ? null : state.setter.trim(),
    grade: state.grade.trim().isEmpty ? null : state.grade.trim(),
  );
}

String _buildPresetId(SoloBoardViewState state) {
  return <String>[
    state.boardId,
    '${state.angle}',
    state.sort,
    state.query.trim(),
    state.setter.trim(),
    state.grade.trim(),
  ].join('|');
}

String _buildPresetLabel(SoloBoardViewState state, BoardOption board) {
  final List<String> parts = <String>['${board.kilterName} · ${state.angle}°'];
  if (state.query.trim().isNotEmpty) {
    parts.add('"${state.query.trim()}"');
  }
  if (state.setter.trim().isNotEmpty) {
    parts.add('setter:${state.setter.trim()}');
  }
  if (state.grade.trim().isNotEmpty) {
    parts.add('grade:${state.grade.trim()}');
  }
  return parts.join(' · ');
}

ProviderClimb _providerClimbFromSaved(
  SoloSavedClimb climb, {
  required ApiClient apiClient,
  required Uri? server,
}) {
  return ProviderClimb(
    id: 'kilter:${climb.productSizeId}:${climb.uuid}',
    externalId: climb.uuid,
    providerId: 'kilter',
    surfaceId: climb.boardId,
    name: climb.climbName,
    setterName: climb.setterName,
    primaryGrade: climb.grade,
    popularity: climb.ascends,
    media: climb.imageFilename == null || server == null
        ? const <ProviderClimbMedia>[]
        : <ProviderClimbMedia>[
            ProviderClimbMedia(
              url: apiClient.getImageUrl(
                  server: server, filename: climb.imageFilename!),
              kind: 'image',
            ),
          ],
    meta: <String, String>{
      'board_id': climb.boardId,
      'board_name': climb.boardName,
      'angle': '${climb.angle}',
    },
  );
}
