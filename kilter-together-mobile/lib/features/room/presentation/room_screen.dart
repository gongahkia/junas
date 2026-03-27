import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:qr_flutter/qr_flutter.dart';
import 'package:share_plus/share_plus.dart';
import 'package:wakelock_plus/wakelock_plus.dart';

import '../../../core/deep_links/invite_links.dart';
import '../../../core/models/app_prefs_models.dart';
import '../../../core/models/provider_models.dart';
import '../../../core/models/room_models.dart';
import '../../../core/presentation/climbing_loader.dart';
import '../../../core/presentation/feedback_prompt_card.dart';
import 'room_catalog_card.dart';
import 'room_queue_cards.dart';
import '../../../core/presentation/flow_guide_sheet.dart';
import '../../../core/presentation/gradient_scaffold.dart';
import '../../../core/storage/app_prefs_controller.dart';
import '../application/room_controller.dart';

const List<int> _kilterAngleOptions = <int>[
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
const List<String> _participantStatuses = <String>[
  'watching',
  'ready',
  'resting',
  'away'
];
const List<String> _assistantModes = <String>['manual', 'assist'];
const List<String> _catalogSorts = <String>['popular', 'newest'];
const List<String> _queueStatuses = <String>[
  'queued',
  'next',
  'current',
  'done'
];
const FlowGuideContent _hostRoomGuide = FlowGuideContent(
  eyebrow: 'Host room guide',
  title: 'Run the shared session from this phone',
  summary:
      'The host view owns the shared room context: surface, invite distribution, queue and finalists, assistant mode, and the final room close action.',
  sections: <FlowGuideSection>[
    FlowGuideSection(
      title: 'Set the shared room context',
      body:
          'Validate the provider connection, choose the surface, and keep the room name or assistant mode aligned with the session the group is actually climbing.',
    ),
    FlowGuideSection(
      title: 'Coordinate the group live',
      body:
          'Use queue, finalists, participant roles, and invite sharing from this screen so everyone stays in the same room state.',
    ),
    FlowGuideSection(
      title: 'Wrap the session cleanly',
      body:
          'When the session is done, close the room from here so the room snapshot, recap flow, and recent-session history all settle on the server.',
    ),
  ],
  completionLabel: 'Mark host',
);
const FlowGuideContent _guestRoomGuide = FlowGuideContent(
  eyebrow: 'Guest room guide',
  title: 'Participate in the shared session',
  summary:
      'Guest phones follow the host-managed room context while still letting each person set status, fist bump climbs, and help shape the queue.',
  sections: <FlowGuideSection>[
    FlowGuideSection(
      title: 'Follow the shared surface',
      body:
          'The host chooses the provider connection and active surface, so your job here is to react to the current room state instead of configuring it.',
    ),
    FlowGuideSection(
      title: 'Signal and contribute',
      body:
          'Update your own participant status, fist bump climbs, and add items to queue or finalists when the room permissions allow it.',
    ),
    FlowGuideSection(
      title: 'Rejoin when needed',
      body:
          'If this device loses the saved room session, use the original invite flow again so the app can restore the room token locally.',
    ),
  ],
  completionLabel: 'Mark guest guide complete',
);

bool _viewerOwnsRoomSetup(RoomSnapshot room) {
  return room.permissions.manageSurface ||
      room.permissions.editRoomSettings ||
      room.permissions.manageSession ||
      room.permissions.closeRoom;
}

class _ShareReadiness {
  const _ShareReadiness({
    required this.roomOpen,
    required this.providerConnected,
    required this.surfaceSelected,
  });

  final bool roomOpen;
  final bool providerConnected;
  final bool surfaceSelected;

  bool get inviteUnlocked => roomOpen && providerConnected && surfaceSelected;
  bool get isReady => inviteUnlocked;
}

_ShareReadiness _shareReadinessForRoom(RoomSnapshot room) {
  return _ShareReadiness(
    roomOpen: room.status != 'closed',
    providerConnected: room.connection.connected,
    surfaceSelected: room.surface != null,
  );
}

String _shareReadinessSummary(RoomSnapshot room, _ShareReadiness readiness) {
  final bool owner = _viewerOwnsRoomSetup(room);
  if (!readiness.roomOpen) {
    return 'This room is closed. Start a new room before sending another invite.';
  }
  if (readiness.isReady) {
    return owner
        ? 'Provider connection is active and the shared surface is set. This room is ready to share.'
        : 'The host has finished room setup. This room is ready to share.';
  }
  if (!readiness.providerConnected && !readiness.surfaceSelected) {
    return owner
        ? 'Reconnect the provider and choose the shared surface before sharing the invite.'
        : 'Waiting for the host to reconnect the provider and choose the shared surface.';
  }
  if (!readiness.providerConnected) {
    return owner
        ? 'Reconnect the provider on this phone before sharing the invite.'
        : 'Waiting for the host to reconnect the provider before climbs can load.';
  }
  return owner
      ? 'Choose the shared surface before sharing the invite.'
      : 'Waiting for the host to choose the shared surface.';
}

bool _pendingSeedMatchesRoomSurface(
  RoomSnapshot room,
  PendingRoomSeed seed,
) {
  final ProviderSurface? roomSurface = room.surface;
  if (roomSurface == null || room.providerId != seed.providerId) {
    return false;
  }
  if ((roomSurface.id).trim() != seed.surface.id.trim()) {
    return false;
  }

  final String roomAngle = (roomSurface.meta['angle'] ?? '').trim();
  final String seedAngle = (seed.surface.meta['angle'] ?? '').trim();
  if ((roomAngle.isNotEmpty || seedAngle.isNotEmpty) &&
      roomAngle != seedAngle) {
    return false;
  }

  final String roomParent = (roomSurface.meta['gym_slug'] ??
          roomSurface.meta['parent_id'] ??
          roomSurface.parentId ??
          '')
      .trim();
  final String seedParent = (seed.surface.meta['gym_slug'] ??
          seed.surface.meta['parent_id'] ??
          seed.surface.parentId ??
          '')
      .trim();
  if ((roomParent.isNotEmpty || seedParent.isNotEmpty) &&
      roomParent != seedParent) {
    return false;
  }

  return true;
}

String? _validateReconnectSecret(
  RoomSnapshot room, {
  required String username,
  required String password,
  required String token,
}) {
  if (room.providerId == 'kilter') {
    if (username.trim().isEmpty) {
      return 'Enter the Kilter username before reconnecting the provider on this phone.';
    }
    if (password.isEmpty) {
      return 'Enter the Kilter password before reconnecting the provider on this phone.';
    }
    return null;
  }

  if (token.trim().isEmpty) {
    return 'Enter the ${room.providerId.toUpperCase()} token before reconnecting the provider on this phone.';
  }
  return null;
}

class RoomScreen extends ConsumerStatefulWidget {
  const RoomScreen({
    super.key,
    required this.slug,
    this.role = 'host',
    this.displayName,
    this.hostPeerId,
    this.hostPeerName,
  });

  final String slug;
  final String role;
  final String? displayName;
  final String? hostPeerId;
  final String? hostPeerName;

  @override
  ConsumerState<RoomScreen> createState() => _RoomScreenState();
}

class _RoomScreenState extends ConsumerState<RoomScreen> {
  final TextEditingController _roomNameController = TextEditingController();
  final TextEditingController _catalogQueryController = TextEditingController();
  final TextEditingController _kilterUsernameController =
      TextEditingController();
  final TextEditingController _kilterPasswordController =
      TextEditingController();
  final TextEditingController _cruxTokenController = TextEditingController();
  final TextEditingController _gradeMinController = TextEditingController();
  final TextEditingController _gradeMaxController = TextEditingController();

  bool _rememberProviderSecret = false;
  bool _showQr = false;
  bool _shareBusy = false;
  bool _inviteCopied = false;
  bool _showCloseFeedback = false;
  bool _autoGuideAttempted = false;
  bool _firstActionHintDismissed = false;
  String _boundRoomName = '';
  Timer? _copiedInviteResetTimer;

  RoomRouteArgs get _args => RoomRouteArgs(
        server: 'p2p://local',
        slug: widget.slug,
        role: widget.role,
        displayName: widget.displayName,
        hostPeerId: widget.hostPeerId,
        hostPeerName: widget.hostPeerName,
      );

  @override
  void initState() {
    super.initState();
    WakelockPlus.enable();
    unawaited(_loadRememberedProviderSecret());
  }

  @override
  void dispose() {
    _copiedInviteResetTimer?.cancel();
    _roomNameController.dispose();
    _catalogQueryController.dispose();
    _kilterUsernameController.dispose();
    _kilterPasswordController.dispose();
    _cruxTokenController.dispose();
    _gradeMinController.dispose();
    _gradeMaxController.dispose();
    WakelockPlus.disable();
    super.dispose();
  }

  Future<void> _loadRememberedProviderSecret() async {
    // in P2P mode the host already owns the provider connection.
    // for hosts: provider is implicitly connected (offline catalog).
    // for guests: credentials are never needed — host relays catalog data.
  }

  Future<void> _shareInvite(Uri inviteUri, String roomName) async {
    setState(() {
      _shareBusy = true;
      _inviteCopied = false;
    });
    try {
      await Share.share(
        inviteUri.toString(),
        subject: roomName,
      );
    } finally {
      if (mounted) {
        setState(() {
          _shareBusy = false;
        });
      }
    }
  }

  void _markInviteCopied() {
    _copiedInviteResetTimer?.cancel();
    if (mounted) {
      setState(() {
        _inviteCopied = true;
      });
    }
    _copiedInviteResetTimer = Timer(const Duration(seconds: 3), () {
      if (!mounted) {
        return;
      }
      setState(() {
        _inviteCopied = false;
      });
    });
  }

  Future<void> _copyInvite(Uri inviteUri) async {
    _markInviteCopied();
    await Clipboard.setData(ClipboardData(text: inviteUri.toString()));
    if (!mounted) {
      return;
    }
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Invite copied to the clipboard.')),
    );
  }

  Future<void> _submitReconnect(RoomSnapshot room) async {
    final String username = _kilterUsernameController.text.trim();
    final String password = _kilterPasswordController.text;
    final String token = _cruxTokenController.text.trim();
    final String? validationError = _validateReconnectSecret(
      room,
      username: username,
      password: password,
      token: token,
    );
    if (validationError != null) {
      ref
          .read(roomControllerProvider(_args).notifier)
          .setClientError(validationError);
      return;
    }

    final Map<String, String> secret = room.providerId == 'kilter'
        ? <String, String>{
            'username': username,
            'password': password,
          }
        : <String, String>{
            'token': token,
          };

    await ref
        .read(roomControllerProvider(_args).notifier)
        .reconnectProvider(secret);
  }

  Future<void> _importPendingRoomSeed(
    PendingRoomSeed seed,
    RoomSnapshot room,
  ) async {
    final ScaffoldMessengerState messenger = ScaffoldMessenger.of(context);
    if (seed.providerId != room.providerId) {
      messenger.showSnackBar(
        const SnackBar(
            content: Text('The saved plan seed is for a different provider.')),
      );
      return;
    }
    if (!_pendingSeedMatchesRoomSurface(room, seed)) {
      messenger.showSnackBar(
        SnackBar(
          content: Text(
            'Choose ${seed.surface.name} as the room surface before importing the saved plan.',
          ),
        ),
      );
      return;
    }

    final Set<String> queuedClimbIds =
        room.queue.map((QueueEntry entry) => entry.climb.id).toSet();
    await ref.read(roomControllerProvider(_args).notifier).importPendingSeed(
          seed.climbs
              .where((ProviderClimb item) => !queuedClimbIds.contains(item.id))
              .map((ProviderClimb item) => item.id)
              .toList(growable: false),
        );
    if (!mounted) {
      return;
    }
    final RoomViewState nextState = ref.read(roomControllerProvider(_args));
    if (nextState.errorMessage == null) {
      await ref
          .read(appPrefsControllerProvider.notifier)
          .clearPendingRoomSeed();
    }
  }

  Future<void> _clearPendingRoomSeed() async {
    await ref.read(appPrefsControllerProvider.notifier).clearPendingRoomSeed();
  }

  String _guideBranchForRoom(RoomSnapshot room) {
    if (room.permissions.closeRoom ||
        room.permissions.manageSession ||
        room.permissions.manageSurface ||
        room.permissions.editRoomSettings) {
      return 'host';
    }
    return 'guest';
  }

  bool _guideCompleted(AppPrefs prefs, String branch) {
    return switch (branch) {
      'host' => prefs.guidedTour.hostCompleted,
      'guest' => prefs.guidedTour.guestCompleted,
      _ => true,
    };
  }

  FlowGuideContent _guideContentForRoom(RoomSnapshot room) {
    return _guideBranchForRoom(room) == 'host'
        ? _hostRoomGuide
        : _guestRoomGuide;
  }

  void _maybeAutoOpenGuide(RoomSnapshot room, AppPrefs prefs) {
    final String branch = _guideBranchForRoom(room);
    if (_autoGuideAttempted ||
        !prefs.settings.autoGuidesEnabled ||
        prefs.guidedTour.activeBranch != branch ||
        _guideCompleted(prefs, branch)) {
      return;
    }
    _autoGuideAttempted = true;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) {
        return;
      }
      unawaited(_openGuide(room));
    });
  }

  Future<void> _openGuide(RoomSnapshot room) async {
    final AppPrefs prefs =
        ref.read(appPrefsControllerProvider).valueOrNull ?? AppPrefs.defaults();
    final String branch = _guideBranchForRoom(room);
    final FlowGuideResult? result = await showFlowGuideSheet(
      context: context,
      content: _guideContentForRoom(room),
      completed: _guideCompleted(prefs, branch),
    );
    if (result != FlowGuideResult.completed || !mounted) {
      return;
    }
    await ref.read(appPrefsControllerProvider.notifier).completeGuideBranch(
          branch,
        );
  }

  Future<void> _maybeShowCloseFeedback(RoomSnapshot room) async {
    if (!room.permissions.closeRoom) {
      return;
    }
    final bool shouldShow = await ref
        .read(appPrefsControllerProvider.notifier)
        .shouldShowFeedbackPrompt('room-close');
    if (!mounted) {
      return;
    }
    setState(() {
      _showCloseFeedback = shouldShow;
    });
  }

  Future<void> _dismissCloseFeedback() async {
    await ref
        .read(appPrefsControllerProvider.notifier)
        .markFeedbackPromptSeen('room-close');
    if (!mounted) {
      return;
    }
    setState(() {
      _showCloseFeedback = false;
    });
  }

  Future<void> _showLeaveDialog() async {
    final bool? leave = await showDialog<bool>(
      context: context,
      builder: (BuildContext ctx) => AlertDialog(
        title: const Text('Leave this room?'),
        actions: <Widget>[
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('Stay'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            child: const Text('Leave'),
          ),
        ],
      ),
    );
    if (leave == true && mounted) {
      context.goNamed('session-home');
    }
  }

  @override
  Widget build(BuildContext context) {
    final RoomViewState roomState = ref.watch(roomControllerProvider(_args));
    final RoomController controller =
        ref.read(roomControllerProvider(_args).notifier);
    final AsyncValue<AppPrefs> prefsValue =
        ref.watch(appPrefsControllerProvider);
    final AppPrefs prefs = prefsValue.valueOrNull ?? AppPrefs.defaults();

    ref.listen<RoomViewState>(roomControllerProvider(_args),
        (RoomViewState? previous, RoomViewState next) {
      final RoomSnapshot? room = next.room;
      if (room != null && room.roomName != _boundRoomName) {
        _boundRoomName = room.roomName ?? '';
        _roomNameController.text = room.roomName ?? '';
      }
      final String currentQuery = next.catalogQuery;
      if (_catalogQueryController.text != currentQuery) {
        _catalogQueryController.text = currentQuery;
      }
      if (room != null &&
          (previous?.room?.version != room.version ||
              previous?.room?.slug != room.slug)) {
        unawaited(
          ref.read(appPrefsControllerProvider.notifier).rememberRoomVisit(
                server: next.server,
                room: room,
              ),
        );
      }
      if (room != null &&
          previous?.room?.status != 'closed' &&
          room.status == 'closed' &&
          room.permissions.closeRoom) {
        unawaited(_maybeShowCloseFeedback(room));
      }
      if (!_firstActionHintDismissed && room != null) {
        // fr-r5 auto-dismiss
        if (next.room?.myVotes.isNotEmpty == true ||
            (next.room?.queue.length ?? 0) >
                (previous?.room?.queue.length ?? 0)) {
          setState(() {
            _firstActionHintDismissed = true;
          });
        }
      }
    });

    final RoomSnapshot? room = roomState.room;
    final ThemeData theme = Theme.of(context);
    final TextTheme textTheme = theme.textTheme;

    if (roomState.loading && room == null) {
      return GradientScaffold(
        title: 'Room ${widget.slug}',
        subtitle: 'P2P session',
        actions: <Widget>[
          IconButton(
            onPressed: () => context.goNamed('session-home'),
            icon: const Icon(Icons.close),
          ),
        ],
        child: Center(
          child: Padding(
            padding: const EdgeInsets.all(36),
            child: ClimbingLoader(),
          ),
        ),
      );
    }

    if (roomState.requiresRejoin || room == null) {
      return GradientScaffold(
        title: 'Room unavailable',
        subtitle: 'P2P session',
        actions: <Widget>[
          IconButton(
            onPressed: () => context.goNamed('session-home'),
            icon: const Icon(Icons.close),
          ),
        ],
        child: Card(
          child: Padding(
            padding: const EdgeInsets.all(22),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(
                  'Rejoin required',
                  style: textTheme.headlineMedium,
                ),
                const SizedBox(height: 10),
                Text(roomState.errorMessage ??
                    'This device no longer has a valid room session.'),
                const SizedBox(height: 18),
                FilledButton.tonal(
                  onPressed: () => context.goNamed(
                    'join-room',
                    queryParameters: <String, String>{
                      'server': 'P2P session',
                      'slug': widget.slug,
                      if (roomState.joinReason != null)
                        'reason': roomState.joinReason!,
                    },
                  ),
                  child: const Text('Rejoin room'),
                ),
              ],
            ),
          ),
        ),
      );
    }

    final InviteLink invite = InviteLink(
      kind: InviteKind.join,
      slug: room.slug,
    );
    final Uri inviteUri = invite.toUri();
    final Uri webJoinUri = inviteUri;
    final _ShareReadiness shareReadiness = _shareReadinessForRoom(room);
    final String shareReadinessSummary =
        _shareReadinessSummary(room, shareReadiness);
    final bool showSurfaceCard =
        room.permissions.manageSurface || room.connection.connected;
    final bool prioritizeSurfaceSetup = room.permissions.manageSurface &&
        (!room.connection.connected || room.surface == null);
    final Widget? surfaceCard = showSurfaceCard
        ? _SurfaceCard(
            roomState: roomState,
            onLoadTopLevel: () => unawaited(controller.loadSurfaces()),
            onParentSurfaceChanged: (String? value) {
              if (value == null) {
                return;
              }
              controller.updateSurfaceDraft(parentSurfaceId: value);
              if (roomState.hasNestedSurfaceHierarchy) {
                unawaited(controller.loadSurfaces(parentId: value));
              }
            },
            onChildSurfaceChanged: (String? value) {
              if (value == null) {
                return;
              }
              controller.updateSurfaceDraft(childSurfaceId: value);
            },
            onAngleChanged: (int? value) {
              if (value == null) {
                return;
              }
              controller.updateSurfaceDraft(angle: value);
            },
            onSaveSurface: room.permissions.manageSurface
                ? () async {
                    if (room.surface != null) {
                      final bool? confirmed = await showDialog<bool>(
                        context: context,
                        builder: (BuildContext dialogContext) {
                          return AlertDialog(
                            title: const Text('Change surface?'),
                            content: const Text(
                                'This resets the catalog view for all participants.'),
                            actions: <Widget>[
                              TextButton(
                                onPressed: () =>
                                    Navigator.of(dialogContext).pop(false),
                                child: const Text('Cancel'),
                              ),
                              FilledButton.tonal(
                                onPressed: () =>
                                    Navigator.of(dialogContext).pop(true),
                                child: const Text('Change'),
                              ),
                            ],
                          );
                        },
                      );
                      if (confirmed != true) return;
                    }
                    unawaited(controller.setSurface());
                  }
                : null,
            onReconnect:
                room.permissions.manageSurface && room.connection.connected
                    ? () => unawaited(_submitReconnect(room))
                    : room.permissions.manageSurface
                        ? () => unawaited(_submitReconnect(room))
                        : null,
            rememberProviderSecret: _rememberProviderSecret,
            onRememberProviderSecretChanged: (bool value) {
              setState(() {
                _rememberProviderSecret = value;
              });
            },
            kilterUsernameController: _kilterUsernameController,
            kilterPasswordController: _kilterPasswordController,
            cruxTokenController: _cruxTokenController,
          )
        : null;

    if (prefsValue.hasValue) {
      _maybeAutoOpenGuide(room, prefs);
    }

    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (bool didPop, dynamic result) {
        if (!didPop) _showLeaveDialog();
      },
      child: GradientScaffold(
        title: room.roomName ?? 'Room ${room.slug}',
        subtitle: 'P2P session',
        actions: <Widget>[
          IconButton(
            onPressed: () => unawaited(_openGuide(room)),
            icon: const Icon(Icons.help_outline),
          ),
          IconButton(
            onPressed: roomState.refreshing
                ? null
                : () => unawaited(controller.refresh()),
            icon: Icon(roomState.refreshing ? Icons.sync : Icons.refresh),
          ),
          IconButton(
            onPressed: _shareBusy || !shareReadiness.isReady
                ? null
                : () => unawaited(
                    _shareInvite(inviteUri, room.roomName ?? room.slug)),
            icon: const Icon(Icons.ios_share),
          ),
        ],
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            if (roomState.errorMessage != null) ...<Widget>[
              _MessageCard(
                title: 'Action blocked',
                message: roomState.errorMessage!,
                accent: const Color(0xFF404040),
              ),
              const SizedBox(height: 14),
            ],
            if (roomState.notice != null) ...<Widget>[
              _MessageCard(
                title: 'Updated',
                message: roomState.notice!,
                accent: const Color(0xFF1A1A1A),
              ),
              const SizedBox(height: 14),
            ],
            if (_showCloseFeedback) ...<Widget>[
              FeedbackPromptCard(
                title: 'How did closing the room feel?',
                description:
                    'A quick signal helps tune the room wrap-up flow before more post-session UI gets added.',
                onDismiss: () => unawaited(_dismissCloseFeedback()),
                onSubmit: (String sentiment, String? message) async {
                  await _dismissCloseFeedback();
                },
              ),
              const SizedBox(height: 14),
            ],
            if (prefs.pendingRoomSeed != null &&
                prefs.pendingRoomSeed!.providerId ==
                    room.providerId) ...<Widget>[
              _PendingRoomSeedCard(
                seed: prefs.pendingRoomSeed!,
                room: room,
                actionInFlight: roomState.actionInFlight,
                onImport: () => unawaited(
                    _importPendingRoomSeed(prefs.pendingRoomSeed!, room)),
                onClear: () => unawaited(_clearPendingRoomSeed()),
              ),
              const SizedBox(height: 14),
            ],
            _OverviewCard(room: room),
            const SizedBox(height: 14),
            if (!_firstActionHintDismissed &&
                !prefs.guidedTour.guestCompleted &&
                !_viewerOwnsRoomSetup(room))
              AnimatedSize(
                duration: const Duration(milliseconds: 200),
                child: ClipRect(
                  child: _FirstActionHintCard(
                    onDismiss: () =>
                        setState(() => _firstActionHintDismissed = true),
                  ),
                ),
              ),
            if (!_firstActionHintDismissed &&
                !prefs.guidedTour.guestCompleted &&
                !_viewerOwnsRoomSetup(room))
              const SizedBox(height: 14),
            _LiveSignalCard(
              room: room,
              roomState: roomState,
            ),
            const SizedBox(height: 14),
            _ShareReadinessCard(
              room: room,
              readiness: shareReadiness,
              summary: shareReadinessSummary,
            ),
            const SizedBox(height: 14),
            if (prioritizeSurfaceSetup && surfaceCard != null) ...<Widget>[
              surfaceCard,
              const SizedBox(height: 14),
            ],
            _InviteCard(
              inviteUri: inviteUri,
              qrUri: webJoinUri,
              roomSlug: room.slug,
              joinPath: '/join/${Uri.encodeComponent(room.slug)}',
              shareReady: shareReadiness.isReady,
              lockedMessage: shareReadinessSummary,
              showQr: _showQr && shareReadiness.isReady,
              copyLabel: _inviteCopied ? 'Copied' : 'Copy invite',
              shareLabel: _shareBusy ? 'Sharing...' : 'Share invite',
              onToggleQr: shareReadiness.isReady
                  ? () => setState(() => _showQr = !_showQr)
                  : null,
              onCopy: shareReadiness.isReady
                  ? () => unawaited(_copyInvite(inviteUri))
                  : null,
              onShare: _shareBusy || !shareReadiness.isReady
                  ? null
                  : () => unawaited(
                      _shareInvite(inviteUri, room.roomName ?? room.slug)),
            ),
            const SizedBox(height: 14),
            _SelfStatusCard(
              room: room,
              statuses: _participantStatuses,
              onChanged: (String? value) {
                if (value == null) {
                  return;
                }
                unawaited(controller.updateMyStatus(value));
              },
            ),
            const SizedBox(height: 14),
            if (!prioritizeSurfaceSetup && surfaceCard != null) ...<Widget>[
              surfaceCard,
              const SizedBox(height: 14),
            ],
            CatalogCard(
              roomState: roomState,
              queryController: _catalogQueryController,
              gradeMinController: _gradeMinController,
              gradeMaxController: _gradeMaxController,
              sortOptions: _catalogSorts,
              onSearch: () => unawaited(
                controller.loadCatalog(
                  q: _catalogQueryController.text.trim(),
                  sort: roomState.catalogSort,
                  gradeMin: _gradeMinController.text.trim(),
                  gradeMax: _gradeMaxController.text.trim(),
                ),
              ),
              onSortChanged: (String? value) {
                if (value == null) {
                  return;
                }
                unawaited(
                  controller.loadCatalog(
                    q: _catalogQueryController.text.trim(),
                    sort: value,
                    gradeMin: _gradeMinController.text.trim(),
                    gradeMax: _gradeMaxController.text.trim(),
                  ),
                );
              },
              onSelectClimb: (String climbId) =>
                  unawaited(controller.selectCatalogClimb(climbId)),
              onLoadMore: roomState.catalogNextCursor == null
                  ? null
                  : () => unawaited(
                        controller.loadCatalog(
                          q: roomState.catalogQuery,
                          sort: roomState.catalogSort,
                          cursor: roomState.catalogNextCursor,
                        ),
                      ),
              onToggleVote: (String climbId) =>
                  unawaited(controller.toggleVote(climbId)),
              onAddQueue: (String climbId) =>
                  unawaited(controller.addQueueEntry(climbId)),
              onAddFinalist: (String climbId) =>
                  unawaited(controller.addFinalist(climbId)),
              onPromoteCurrent: (String climbId) =>
                  unawaited(controller.promoteClimb(climbId, 'current')),
              onPromoteNext: (String climbId) =>
                  unawaited(controller.promoteClimb(climbId, 'next')),
            ),
            const SizedBox(height: 14),
            _LeaderboardCard(
              room: room,
              roomState: roomState,
              onSelectClimb: (String climbId) =>
                  unawaited(controller.selectCatalogClimb(climbId)),
              onToggleVote: (String climbId) =>
                  unawaited(controller.toggleVote(climbId)),
            ),
            const SizedBox(height: 14),
            QueueCard(
              room: room,
              queueStatuses: _queueStatuses,
              onMoveUp: (int entryId) =>
                  unawaited(controller.moveQueueEntry(entryId, -1)),
              onMoveDown: (int entryId) =>
                  unawaited(controller.moveQueueEntry(entryId, 1)),
              onDelete: (int entryId) =>
                  unawaited(controller.deleteQueueEntry(entryId)),
              onPromoteCurrent: (String climbId) =>
                  unawaited(controller.promoteClimb(climbId, 'current')),
              onPromoteNext: (String climbId) =>
                  unawaited(controller.promoteClimb(climbId, 'next')),
              onStatusChanged: (int entryId, String? value) {
                if (value == null) {
                  return;
                }
                unawaited(controller.addQueueStatusUpdate(entryId, value));
              },
              onAutoRefill: room.permissions.manageQueue &&
                      room.queue
                          .where((QueueEntry e) => e.status == 'queued')
                          .isEmpty &&
                      room.voteCounts.values.any((int c) => c > 0)
                  ? () => unawaited(controller.autoRefillQueue())
                  : null,
            ),
            const SizedBox(height: 14),
            FinalistsCard(
              room: room,
              onMoveUp: (int entryId) =>
                  unawaited(controller.moveFinalist(entryId, -1)),
              onMoveDown: (int entryId) =>
                  unawaited(controller.moveFinalist(entryId, 1)),
              onDelete: (int entryId) =>
                  unawaited(controller.deleteFinalist(entryId)),
              onPickRandomFinalists: () =>
                  unawaited(controller.pickRandom('finalists')),
              onPickRandomTopVoted: () =>
                  unawaited(controller.pickRandom('top_voted')),
              onPromoteCurrent: (String climbId) =>
                  unawaited(controller.promoteClimb(climbId, 'current')),
              onPromoteNext: (String climbId) =>
                  unawaited(controller.promoteClimb(climbId, 'next')),
            ),
            const SizedBox(height: 14),
            ParticipantsCard(
              room: room,
              onRoleChanged: (int participantId, String? role) {
                if (role == null) {
                  return;
                }
                unawaited(
                    controller.updateParticipantRole(participantId, role));
              },
              onRemove: (int participantId) =>
                  unawaited(controller.removeParticipant(participantId)),
            ),
            const SizedBox(height: 14),
            ManageRoomCard(
              room: room,
              roomNameController: _roomNameController,
              assistantModes: _assistantModes,
              busy: roomState.actionInFlight,
              onSaveName: room.permissions.editRoomSettings
                  ? () => unawaited(controller
                      .updateRoomName(_roomNameController.text.trim()))
                  : null,
              onAssistantModeChanged: room.permissions.manageSession
                  ? (String? value) {
                      if (value == null) {
                        return;
                      }
                      unawaited(controller.updateAssistantMode(value));
                    }
                  : null,
              onFistBumpsChanged: room.permissions.editRoomSettings
                  ? (bool value) =>
                      unawaited(controller.setFistBumpsEnabled(value))
                  : null,
              onClearVotes: room.permissions.manageSession
                  ? () => unawaited(controller.clearVotes())
                  : null,
              onCloseRoom: room.permissions.closeRoom && room.status != 'closed'
                  ? () async {
                      await controller.closeRoom();
                    }
                  : null,
            ),
          ],
        ),
      ),
    ); // PopScope
  }
}

class _FirstActionHintCard extends StatelessWidget {
  const _FirstActionHintCard({required this.onDismiss});
  final VoidCallback onDismiss;
  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: const Color(0xFFF0F0F0),
        borderRadius: BorderRadius.zero,
        border: Border.all(color: const Color(0xFFD4D4D4)),
      ),
      padding: const EdgeInsets.fromLTRB(16, 14, 8, 14),
      child: Row(
        children: <Widget>[
          Expanded(
            child: Text(
              'Browse the catalog, fist bump climbs, or add to the queue to start contributing.',
              style: Theme.of(context).textTheme.bodyMedium,
            ),
          ),
          IconButton(
            onPressed: onDismiss,
            icon: const Icon(Icons.close, size: 18),
          ),
        ],
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
          border: Border.all(color: accent.withValues(alpha: 0.18)),
        ),
        padding: const EdgeInsets.all(18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              title,
              style: Theme.of(context)
                  .textTheme
                  .titleLarge
                  ?.copyWith(color: accent),
            ),
            const SizedBox(height: 8),
            Text(message),
          ],
        ),
      ),
    );
  }
}

class _PendingRoomSeedCard extends StatelessWidget {
  const _PendingRoomSeedCard({
    required this.seed,
    required this.room,
    required this.actionInFlight,
    required this.onImport,
    required this.onClear,
  });

  final PendingRoomSeed seed;
  final RoomSnapshot room;
  final bool actionInFlight;
  final VoidCallback onImport;
  final VoidCallback onClear;

  @override
  Widget build(BuildContext context) {
    final bool surfaceMatches = _pendingSeedMatchesRoomSurface(room, seed);
    final Set<String> queuedClimbIds =
        room.queue.map((QueueEntry entry) => entry.climb.id).toSet();
    final int pendingClimbCount = seed.climbs
        .where((ProviderClimb item) => !queuedClimbIds.contains(item.id))
        .length;
    final bool hasClimbs = seed.climbs.isNotEmpty;
    final String title = hasClimbs
        ? 'Saved plan seed is ready'
        : 'Saved surface context is ready';
    final String summary;
    if (hasClimbs) {
      summary = '${seed.surface.name} · ${seed.climbs.length} climb'
          '${seed.climbs.length == 1 ? '' : 's'}';
    } else {
      summary = seed.surface.name;
    }
    final String body;
    if (hasClimbs) {
      if (surfaceMatches) {
        body = pendingClimbCount > 0
            ? 'Import $pendingClimbCount saved climb${pendingClimbCount == 1 ? '' : 's'} into this room queue.'
            : 'Every saved climb is already in the room queue.';
      } else {
        body =
            'Choose ${seed.surface.name} as the room surface first, then import the saved queue.';
      }
    } else {
      body = surfaceMatches
          ? 'This room is already set to the saved plan context.'
          : 'Choose ${seed.surface.name} as the room surface first to use the saved plan context in this room.';
    }

    return Card(
      child: Container(
        decoration: BoxDecoration(
          borderRadius: BorderRadius.zero,
          gradient: const LinearGradient(
            colors: <Color>[
              Color(0xFFF0F0F0),
              Colors.white,
            ],
          ),
        ),
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              title,
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 8),
            Text(
              summary,
            ),
            const SizedBox(height: 10),
            Text(body),
            const SizedBox(height: 14),
            Wrap(
              spacing: 10,
              runSpacing: 10,
              children: <Widget>[
                if (surfaceMatches && hasClimbs)
                  FilledButton.tonal(
                    onPressed: actionInFlight
                        ? null
                        : pendingClimbCount > 0
                            ? onImport
                            : onClear,
                    child: Text(
                      pendingClimbCount > 0
                          ? 'Import plan to queue'
                          : 'Clear imported seed',
                    ),
                  ),
                TextButton(
                  onPressed: actionInFlight ? null : onClear,
                  child: const Text('Discard seed'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _OverviewCard extends StatelessWidget {
  const _OverviewCard({
    required this.room,
  });

  final RoomSnapshot room;

  @override
  Widget build(BuildContext context) {
    final TextTheme textTheme = Theme.of(context).textTheme;
    final List<Participant> liveParticipants = room.participants
        .where((Participant participant) => participant.isOnline)
        .toList(growable: false);
    final Map<String, int> readinessCounts = <String, int>{
      'ready': 0,
      'resting': 0,
      'away': 0,
      'watching': 0,
    };
    for (final Participant participant in room.participants) {
      readinessCounts[participant.status] =
          (readinessCounts[participant.status] ?? 0) + 1;
    }
    final String sharedSurfaceLabel = room.surface?.name ??
        (_viewerOwnsRoomSetup(room) ? 'Not selected yet' : 'Waiting for host');
    final String currentClimbLabel =
        room.currentClimb?.name ?? 'No current climb selected';
    final String signedInAs = (room.displayName ?? '').trim().isNotEmpty
        ? room.displayName!
        : 'Unknown participant';

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(22),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Wrap(
              spacing: 10,
              runSpacing: 10,
              children: <Widget>[
                RoomChip(label: room.providerId.toUpperCase()),
                RoomChip(label: room.status.toUpperCase()),
                RoomChip(
                    label: room.connection.connected
                        ? 'CONNECTED'
                        : 'AUTH REQUIRED'),
                if (room.surface != null) RoomChip(label: room.surface!.name),
                Container(
                  // fr-r7 online count
                  padding:
                      const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                  decoration: BoxDecoration(
                    color: const Color(0xFFE0F7FA),
                    borderRadius: BorderRadius.zero,
                  ),
                  child: Text(
                    '${liveParticipants.length} online',
                    style: textTheme.labelSmall
                        ?.copyWith(color: const Color(0xFF00897B)),
                  ),
                ),
                if (liveParticipants.length <= 1 && _viewerOwnsRoomSetup(room))
                  Container(
                    // fr-r7 waiting chip
                    padding:
                        const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                    decoration: BoxDecoration(
                      color: const Color(0xFFFFFBEB),
                      borderRadius: BorderRadius.zero,
                      border: Border.all(color: const Color(0xFFFCD34D)),
                    ),
                    child: Text(
                      'Waiting for guests...',
                      style: textTheme.labelSmall,
                    ),
                  ),
              ],
            ),
            const SizedBox(height: 14),
            Text('Room overview', style: textTheme.headlineMedium),
            const SizedBox(height: 12),
            Wrap(
              spacing: 24,
              runSpacing: 16,
              children: <Widget>[
                _OverviewStat(
                  label: 'Signed in as',
                  value: signedInAs,
                ),
                _OverviewStat(
                  label: 'Shared surface',
                  value: sharedSurfaceLabel,
                ),
                _OverviewStat(
                  label: 'Current climb',
                  value: currentClimbLabel,
                  supportingText: room.currentClimb?.primaryGrade,
                ),
                _OverviewStat(
                  label: 'Room slug',
                  value: room.slug,
                  monospace: true,
                ),
              ],
            ),
            const SizedBox(height: 18),
            Container(
              decoration: BoxDecoration(
                color: const Color(0xFFF5F5F5),
                borderRadius: BorderRadius.zero,
                border: Border.all(color: const Color(0xFFE2E8F0)),
              ),
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Row(
                    children: <Widget>[
                      Expanded(
                        child: Text(
                          'Room pulse',
                          style: textTheme.titleLarge,
                        ),
                      ),
                      Text(
                        liveParticipants.isEmpty
                            ? 'No one online yet'
                            : '${liveParticipants.length} online now',
                        style: textTheme.bodySmall,
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  Wrap(
                    spacing: 10,
                    runSpacing: 10,
                    children: <Widget>[
                      RoomChip(label: '${readinessCounts['ready'] ?? 0} ready'),
                      RoomChip(
                          label: '${readinessCounts['resting'] ?? 0} resting'),
                      RoomChip(label: '${readinessCounts['away'] ?? 0} away'),
                      RoomChip(
                          label:
                              '${readinessCounts['watching'] ?? 0} watching'),
                    ],
                  ),
                  const SizedBox(height: 12),
                  Wrap(
                    spacing: 10,
                    runSpacing: 10,
                    children: liveParticipants.isEmpty
                        ? const <Widget>[
                            RoomChip(label: 'Waiting for guests'),
                          ]
                        : liveParticipants
                            .map(
                              (Participant participant) => RoomChip(
                                label:
                                    '${participant.displayName} · ${participant.status}',
                              ),
                            )
                            .toList(growable: false),
                  ),
                ],
              ),
            ),
            if (room.assistant.message != null ||
                room.assistant.suggestion != null) ...<Widget>[
              const SizedBox(height: 16),
              Container(
                decoration: BoxDecoration(
                  color: const Color(0xFFE8F7F2),
                  borderRadius: BorderRadius.zero,
                ),
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Text(
                      'Assistant ${room.assistant.mode.toUpperCase()}',
                      style: textTheme.titleLarge,
                    ),
                    if (room.assistant.message != null) ...<Widget>[
                      const SizedBox(height: 6),
                      Text(room.assistant.message!),
                    ],
                    if (room.assistant.suggestion != null) ...<Widget>[
                      const SizedBox(height: 10),
                      Text(
                          'Suggested climb: ${room.assistant.suggestion!.climb.name}'),
                    ],
                  ],
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _LiveSignalCard extends StatelessWidget {
  const _LiveSignalCard({
    required this.room,
    required this.roomState,
  });

  final RoomSnapshot room;
  final RoomViewState roomState;

  @override
  Widget build(BuildContext context) {
    final QueueEntry? nextEntry = room.queue
        .where((QueueEntry entry) => entry.status == 'next')
        .firstOrNull;
    final _LeaderboardSummary leaderboard =
        _buildLeaderboardSummary(room, roomState);
    final List<ProviderClimb> topClimbs =
        leaderboard.climbs.take(3).toList(growable: false);

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(22),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              'Live signal',
              style: Theme.of(context).textTheme.headlineMedium,
            ),
            const SizedBox(height: 8),
            Text(
              'Use the current climb, next pick, and fist-bump pressure to keep the room moving without losing the shared context.',
            ),
            const SizedBox(height: 16),
            Wrap(
              spacing: 24,
              runSpacing: 16,
              children: <Widget>[
                _OverviewStat(
                  label: 'Current climb',
                  value: room.currentClimb?.name ?? 'Nothing live yet',
                  supportingText: room.currentClimb?.primaryGrade,
                ),
                _OverviewStat(
                  label: 'Next climb',
                  value: nextEntry?.climb.name ??
                      (room.queue.isEmpty
                          ? 'Queue is still empty'
                          : 'No next climb picked'),
                  supportingText: nextEntry?.climb.primaryGrade,
                ),
                _OverviewStat(
                  label: 'Top fist-bump pressure',
                  value: topClimbs.isEmpty
                      ? 'No fist bumps yet'
                      : leaderboard.topVoteTieCount > 1
                          ? '${leaderboard.topVoteTieCount} climbs tied at ${leaderboard.topVoteCount} fist bumps'
                          : '${topClimbs.first.name} · ${leaderboard.topVoteCount} fist bumps',
                ),
              ],
            ),
            const SizedBox(height: 18),
            if (topClimbs.isEmpty)
              const Text(
                'Fist bumps, finalists, and queue changes will start surfacing here once the room activity picks up.',
              )
            else
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Text(
                    'Top fist-bumped right now',
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                  const SizedBox(height: 10),
                  ...topClimbs.map(
                    (ProviderClimb climb) => Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: Row(
                        children: <Widget>[
                          Expanded(
                            child: Text(
                              climb.name,
                              style: Theme.of(context).textTheme.bodyLarge,
                            ),
                          ),
                          const SizedBox(width: 12),
                          RoomChip(
                            label:
                                '${room.voteCounts[climb.id] ?? 0} fist bump${(room.voteCounts[climb.id] ?? 0) == 1 ? '' : 's'}',
                          ),
                        ],
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

class _LeaderboardSummary {
  const _LeaderboardSummary({
    required this.climbs,
    required this.topVoteCount,
    required this.topVoteTieCount,
  });

  final List<ProviderClimb> climbs;
  final int topVoteCount;
  final int topVoteTieCount;
}

_LeaderboardSummary _buildLeaderboardSummary(
  RoomSnapshot room,
  RoomViewState roomState,
) {
  final Map<String, ProviderClimb> climbsById = <String, ProviderClimb>{};
  for (final ProviderClimb climb
      in roomState.catalog?.climbs ?? <ProviderClimb>[]) {
    climbsById[climb.id] = climb;
  }
  for (final QueueEntry entry in room.queue) {
    climbsById[entry.climb.id] = entry.climb;
  }
  for (final FinalistEntry entry in room.finalists) {
    climbsById[entry.climb.id] = entry.climb;
  }
  if (room.currentClimb != null) {
    climbsById[room.currentClimb!.id] = room.currentClimb!;
  }
  if (roomState.selectedCatalogClimb != null) {
    climbsById[roomState.selectedCatalogClimb!.climb.id] =
        roomState.selectedCatalogClimb!.climb;
  }

  final List<ProviderClimb> climbs = climbsById.values
      .where((ProviderClimb climb) => (room.voteCounts[climb.id] ?? 0) > 0)
      .toList(growable: false)
    ..sort((ProviderClimb left, ProviderClimb right) {
      final int voteDelta =
          (room.voteCounts[right.id] ?? 0) - (room.voteCounts[left.id] ?? 0);
      if (voteDelta != 0) {
        return voteDelta;
      }
      return left.name.compareTo(right.name);
    });

  final int topVoteCount =
      climbs.isEmpty ? 0 : (room.voteCounts[climbs.first.id] ?? 0);
  final int topVoteTieCount = topVoteCount == 0
      ? 0
      : climbs
          .where((ProviderClimb climb) =>
              (room.voteCounts[climb.id] ?? 0) == topVoteCount)
          .length;

  return _LeaderboardSummary(
    climbs: climbs,
    topVoteCount: topVoteCount,
    topVoteTieCount: topVoteTieCount,
  );
}

class _LeaderboardCard extends StatelessWidget {
  const _LeaderboardCard({
    required this.room,
    required this.roomState,
    required this.onSelectClimb,
    required this.onToggleVote,
  });

  final RoomSnapshot room;
  final RoomViewState roomState;
  final ValueChanged<String> onSelectClimb;
  final ValueChanged<String> onToggleVote;

  @override
  Widget build(BuildContext context) {
    final _LeaderboardSummary leaderboard =
        _buildLeaderboardSummary(room, roomState);
    final String? selectedClimbId = roomState.selectedCatalogClimb?.climb.id;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(22),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              'Leaderboard',
              style: Theme.of(context).textTheme.headlineMedium,
            ),
            const SizedBox(height: 8),
            Text(
              'Most fist-bumped climbs visible in this room snapshot.',
            ),
            const SizedBox(height: 16),
            if (!room.fistBumpsEnabled)
              const Text(
                'Fist bumps are disabled for this room.',
              )
            else if (leaderboard.climbs.isEmpty)
              const Text(
                'Fist bumps will surface the leaderboard once the group starts choosing climbs.',
              )
            else ...<Widget>[
              if (leaderboard.topVoteCount > 0 &&
                  leaderboard.topVoteTieCount > 1) ...<Widget>[
                Container(
                  width: double.infinity,
                  decoration: BoxDecoration(
                    color: const Color(0xFFFFFBEB),
                    borderRadius: BorderRadius.zero,
                    border: Border.all(color: const Color(0xFFFCD34D)),
                  ),
                  padding: const EdgeInsets.all(14),
                  child: Text(
                    'There is currently a tie for first place across ${leaderboard.topVoteTieCount} climbs.',
                  ),
                ),
                const SizedBox(height: 12),
              ],
              ...leaderboard.climbs.asMap().entries.map(
                (MapEntry<int, ProviderClimb> entry) {
                  final ProviderClimb climb = entry.value;
                  final QueueEntry? queueEntry = room.queue
                      .where((QueueEntry item) => item.climb.id == climb.id)
                      .firstOrNull;
                  final bool isFinalist = room.finalists.any(
                    (FinalistEntry item) => item.climb.id == climb.id,
                  );
                  final bool isSelected = selectedClimbId == climb.id;
                  final bool myVote = room.myVotes.contains(climb.id);
                  final bool toggleBlocked =
                      room.status == 'closed' || !room.fistBumpsEnabled;
                  return Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: InkWell(
                      borderRadius: BorderRadius.zero,
                      onTap: () => onSelectClimb(climb.id),
                      child: Ink(
                        decoration: BoxDecoration(
                          borderRadius: BorderRadius.zero,
                          border: Border.all(
                            color: isSelected
                                ? const Color(0xFF1A1A1A)
                                : const Color(0xFFE2E8F0),
                          ),
                          color: isSelected
                              ? const Color(0xFFF5F5F5)
                              : Colors.white,
                        ),
                        padding: const EdgeInsets.all(16),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: <Widget>[
                            Row(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: <Widget>[
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: <Widget>[
                                      Text(
                                        '#${entry.key + 1} ${climb.name}',
                                        style: Theme.of(context)
                                            .textTheme
                                            .titleMedium,
                                      ),
                                      const SizedBox(height: 4),
                                      Text(
                                        [
                                          if ((climb.setterName ?? '')
                                              .isNotEmpty)
                                            climb.setterName!,
                                          if ((climb.primaryGrade ?? '')
                                              .isNotEmpty)
                                            climb.primaryGrade!,
                                        ].join(' · '),
                                      ),
                                    ],
                                  ),
                                ),
                                const SizedBox(width: 12),
                                RoomChip(
                                  label:
                                      '${room.voteCounts[climb.id] ?? 0} fist bump${(room.voteCounts[climb.id] ?? 0) == 1 ? '' : 's'}',
                                ),
                              ],
                            ),
                            const SizedBox(height: 10),
                            Wrap(
                              spacing: 10,
                              runSpacing: 10,
                              children: <Widget>[
                                if (queueEntry != null)
                                  RoomChip(
                                    label: switch (queueEntry.status) {
                                      'queued' => 'Queued',
                                      'current' => 'Current',
                                      'next' => 'Next',
                                      'done' => 'Done',
                                      _ => queueEntry.status,
                                    },
                                  ),
                                if (isFinalist)
                                  const RoomChip(label: 'Finalist'),
                                if (myVote)
                                  const RoomChip(label: 'Fist bumped'),
                                if (isSelected)
                                  const RoomChip(label: 'Viewing'),
                              ],
                            ),
                            const SizedBox(height: 12),
                            Wrap(
                              spacing: 10,
                              runSpacing: 10,
                              children: <Widget>[
                                FilledButton.tonal(
                                  onPressed: () => onSelectClimb(climb.id),
                                  child: Text(isSelected
                                      ? 'Viewing detail'
                                      : 'View detail'),
                                ),
                                FilledButton.tonal(
                                  onPressed: toggleBlocked
                                      ? null
                                      : () => onToggleVote(climb.id),
                                  child: Text(myVote
                                      ? 'Remove fist bump'
                                      : 'Fist bump'),
                                ),
                              ],
                            ),
                          ],
                        ),
                      ),
                    ),
                  );
                },
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _OverviewStat extends StatelessWidget {
  const _OverviewStat({
    required this.label,
    required this.value,
    this.supportingText,
    this.monospace = false,
  });

  final String label;
  final String value;
  final String? supportingText;
  final bool monospace;

  @override
  Widget build(BuildContext context) {
    final TextTheme textTheme = Theme.of(context).textTheme;
    return SizedBox(
      width: 180,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(label, style: textTheme.bodySmall),
          const SizedBox(height: 4),
          Text(
            value,
            style: monospace
                ? textTheme.titleMedium?.copyWith(
                    fontFamily: 'monospace',
                  )
                : textTheme.titleMedium,
          ),
          if ((supportingText ?? '').trim().isNotEmpty) ...<Widget>[
            const SizedBox(height: 4),
            Text(
              supportingText!,
              style: textTheme.bodySmall,
            ),
          ],
        ],
      ),
    );
  }
}

class _ShareReadinessCard extends StatelessWidget {
  const _ShareReadinessCard({
    required this.room,
    required this.readiness,
    required this.summary,
  });

  final RoomSnapshot room;
  final _ShareReadiness readiness;
  final String summary;

  @override
  Widget build(BuildContext context) {
    final bool owner = _viewerOwnsRoomSetup(room);
    final bool closed = !readiness.roomOpen;
    final bool ready = readiness.isReady;
    final Color accent = closed
        ? const Color(0xFF404040)
        : ready
            ? const Color(0xFF404040)
            : owner
                ? const Color(0xFF525252)
                : const Color(0xFF1D4ED8);
    final String title = closed
        ? 'Room is closed'
        : ready
            ? 'Room is ready to share'
            : owner
                ? 'Room not ready to share yet'
                : 'Waiting for host setup';

    return Card(
      child: Container(
        decoration: BoxDecoration(
          borderRadius: BorderRadius.zero,
          border: Border.all(color: accent.withValues(alpha: 0.16)),
        ),
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              title,
              style: Theme.of(context)
                  .textTheme
                  .headlineMedium
                  ?.copyWith(color: accent),
            ),
            const SizedBox(height: 8),
            Text(summary),
            const SizedBox(height: 16),
            _ReadinessItem(
              label: 'Room is open',
              complete: readiness.roomOpen,
            ),
            const SizedBox(height: 10),
            _ReadinessItem(
              label: 'Provider connected on host phone',
              complete: readiness.providerConnected,
            ),
            const SizedBox(height: 10),
            _ReadinessItem(
              label: 'Shared surface selected',
              complete: readiness.surfaceSelected,
            ),
            const SizedBox(height: 10),
            _ReadinessItem(
              label: 'Invite unlocked',
              complete: readiness.inviteUnlocked,
            ),
          ],
        ),
      ),
    );
  }
}

class _ReadinessItem extends StatelessWidget {
  const _ReadinessItem({
    required this.label,
    required this.complete,
  });

  final String label;
  final bool complete;

  @override
  Widget build(BuildContext context) {
    final Color color =
        complete ? const Color(0xFF404040) : const Color(0xFF6B7280);
    return Row(
      children: <Widget>[
        Icon(
          complete ? Icons.check_circle : Icons.radio_button_unchecked,
          color: color,
          size: 18,
        ),
        const SizedBox(width: 10),
        Expanded(
          child: Text(
            label,
            style:
                Theme.of(context).textTheme.bodyMedium?.copyWith(color: color),
          ),
        ),
      ],
    );
  }
}

class _InviteCard extends StatelessWidget {
  const _InviteCard({
    required this.inviteUri,
    required this.qrUri,
    required this.roomSlug,
    required this.joinPath,
    required this.shareReady,
    required this.lockedMessage,
    required this.showQr,
    required this.copyLabel,
    required this.shareLabel,
    required this.onToggleQr,
    required this.onCopy,
    required this.onShare,
  });

  final Uri inviteUri;
  final Uri qrUri;
  final String roomSlug;
  final String joinPath;
  final bool shareReady;
  final String lockedMessage;
  final bool showQr;
  final String copyLabel;
  final String shareLabel;
  final VoidCallback? onToggleQr;
  final VoidCallback? onCopy;
  final VoidCallback? onShare;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(22),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              'Invite guests',
              style: Theme.of(context).textTheme.headlineMedium,
            ),
            const SizedBox(height: 8),
            if (shareReady)
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Text(
                    'Share the link or let guests scan the QR code.',
                    style: Theme.of(context).textTheme.bodyMedium,
                  ),
                  const SizedBox(height: 14),
                  Row(
                    children: <Widget>[
                      Expanded(
                        child: _InviteSummaryTile(
                          label: 'Join path',
                          primaryText: joinPath,
                          secondaryText: inviteUri.toString(),
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: _InviteSummaryTile(
                          label: 'Room slug',
                          primaryText: roomSlug,
                        ),
                      ),
                    ],
                  ),
                ],
              )
            else
              Container(
                width: double.infinity,
                decoration: BoxDecoration(
                  color: const Color(0xFFFFFBEB),
                  borderRadius: BorderRadius.zero,
                ),
                padding: const EdgeInsets.all(14),
                child: Text(lockedMessage),
              ),
            const SizedBox(height: 14),
            Wrap(
              spacing: 10,
              runSpacing: 10,
              children: <Widget>[
                FilledButton.tonal(
                  onPressed: onCopy,
                  child: Text(copyLabel),
                ),
                FilledButton.tonal(
                  onPressed: onShare,
                  child: Text(shareLabel),
                ),
                OutlinedButton(
                  onPressed: onToggleQr,
                  child: Text(showQr ? 'Hide QR' : 'Show QR'),
                ),
              ],
            ),
            if (showQr && shareReady) ...<Widget>[
              const SizedBox(height: 18),
              Center(
                child: QrImageView(
                  data: qrUri.toString(),
                  version: QrVersions.auto,
                  size: 220,
                  backgroundColor: Colors.white,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _InviteSummaryTile extends StatelessWidget {
  const _InviteSummaryTile({
    required this.label,
    required this.primaryText,
    this.secondaryText,
  });

  final String label;
  final String primaryText;
  final String? secondaryText;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      decoration: BoxDecoration(
        color: const Color(0xFFF5F5F5),
        borderRadius: BorderRadius.zero,
        border: Border.all(color: const Color(0xFFE2E8F0)),
      ),
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(
            label,
            style: Theme.of(context).textTheme.bodySmall,
          ),
          const SizedBox(height: 6),
          Text(
            primaryText,
            style: Theme.of(context).textTheme.titleMedium,
          ),
          if ((secondaryText ?? '').isNotEmpty) ...<Widget>[
            const SizedBox(height: 4),
            SelectableText(
              secondaryText!,
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
        ],
      ),
    );
  }
}

class _SelfStatusCard extends StatelessWidget {
  const _SelfStatusCard({
    required this.room,
    required this.statuses,
    required this.onChanged,
  });

  final RoomSnapshot room;
  final List<String> statuses;
  final ValueChanged<String?> onChanged;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(22),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              'My status',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 10),
            DropdownButtonFormField<String>(
              initialValue: room.participants
                  .where((Participant item) =>
                      item.displayName == room.displayName)
                  .map((Participant item) => item.status)
                  .firstOrNull,
              items: statuses
                  .map(
                    (String value) => DropdownMenuItem<String>(
                      value: value,
                      child: Text(value),
                    ),
                  )
                  .toList(growable: false),
              onChanged: onChanged,
              decoration: const InputDecoration(
                labelText: 'Set how this device is participating',
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _SurfaceCard extends StatelessWidget {
  const _SurfaceCard({
    required this.roomState,
    required this.onLoadTopLevel,
    required this.onParentSurfaceChanged,
    required this.onChildSurfaceChanged,
    required this.onAngleChanged,
    required this.onSaveSurface,
    required this.onReconnect,
    required this.rememberProviderSecret,
    required this.onRememberProviderSecretChanged,
    required this.kilterUsernameController,
    required this.kilterPasswordController,
    required this.cruxTokenController,
  });

  final RoomViewState roomState;
  final VoidCallback onLoadTopLevel;
  final ValueChanged<String?> onParentSurfaceChanged;
  final ValueChanged<String?> onChildSurfaceChanged;
  final ValueChanged<int?> onAngleChanged;
  final VoidCallback? onSaveSurface;
  final VoidCallback? onReconnect;
  final bool rememberProviderSecret;
  final ValueChanged<bool> onRememberProviderSecretChanged;
  final TextEditingController kilterUsernameController;
  final TextEditingController kilterPasswordController;
  final TextEditingController cruxTokenController;

  @override
  Widget build(BuildContext context) {
    final RoomSnapshot room = roomState.room!;
    final bool kilter = room.providerId == 'kilter';

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
                    'Surface and provider',
                    style: Theme.of(context).textTheme.headlineMedium,
                  ),
                ),
                IconButton(
                  onPressed: roomState.surfacesLoading ? null : onLoadTopLevel,
                  icon: const Icon(Icons.refresh),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Text(room.connection.connected
                ? 'Provider connection is active on this phone.'
                : 'Provider auth needs to be revalidated on this phone before guests can browse.'),
            const SizedBox(height: 16),
            if (kilter) ...<Widget>[
              DropdownButtonFormField<String>(
                initialValue: roomState.selectedParentSurfaceId.isEmpty
                    ? null
                    : roomState.selectedParentSurfaceId,
                decoration: const InputDecoration(labelText: 'Board'),
                items: roomState.parentSurfaces
                    .map(
                      (ProviderSurface item) => DropdownMenuItem<String>(
                        value: item.id,
                        child: Text(item.name),
                      ),
                    )
                    .toList(growable: false),
                onChanged: onParentSurfaceChanged,
              ),
              const SizedBox(height: 12),
              DropdownButtonFormField<int>(
                initialValue: roomState.selectedAngle,
                decoration: const InputDecoration(labelText: 'Board angle'),
                items: _kilterAngleOptions
                    .map(
                      (int item) => DropdownMenuItem<int>(
                        value: item,
                        child: Text('$item°'),
                      ),
                    )
                    .toList(growable: false),
                onChanged: onAngleChanged,
              ),
            ] else ...<Widget>[
              DropdownButtonFormField<String>(
                initialValue: roomState.selectedParentSurfaceId.isEmpty
                    ? null
                    : roomState.selectedParentSurfaceId,
                decoration: const InputDecoration(labelText: 'Gym'),
                items: roomState.parentSurfaces
                    .map(
                      (ProviderSurface item) => DropdownMenuItem<String>(
                        value: item.id,
                        child: Text(item.name),
                      ),
                    )
                    .toList(growable: false),
                onChanged: onParentSurfaceChanged,
              ),
              const SizedBox(height: 12),
              DropdownButtonFormField<String>(
                initialValue: roomState.selectedChildSurfaceId.isEmpty
                    ? null
                    : roomState.selectedChildSurfaceId,
                decoration: const InputDecoration(labelText: 'Wall'),
                items: roomState.childSurfaces
                    .map(
                      (ProviderSurface item) => DropdownMenuItem<String>(
                        value: item.id,
                        child: Text(item.name),
                      ),
                    )
                    .toList(growable: false),
                onChanged: onChildSurfaceChanged,
              ),
            ],
            if (onSaveSurface != null) ...<Widget>[
              const SizedBox(height: 14),
              FilledButton.tonal(
                onPressed: roomState.actionInFlight ? null : onSaveSurface,
                child: const Text('Save room surface'),
              ),
            ],
            const SizedBox(height: 18),
            if (room.providerId == 'kilter') ...<Widget>[
              TextField(
                controller: kilterUsernameController,
                decoration: const InputDecoration(labelText: 'Kilter username'),
              ),
              const SizedBox(height: 10),
              TextField(
                controller: kilterPasswordController,
                obscureText: true,
                decoration: const InputDecoration(labelText: 'Kilter password'),
              ),
            ] else ...<Widget>[
              TextField(
                controller: cruxTokenController,
                decoration: const InputDecoration(labelText: 'Crux token'),
              ),
            ],
            const SizedBox(height: 10),
            SwitchListTile.adaptive(
              contentPadding: EdgeInsets.zero,
              value: rememberProviderSecret,
              onChanged: onRememberProviderSecretChanged,
              title: const Text('Remember this provider secret on the device'),
            ),
            if (onReconnect != null)
              FilledButton.tonal(
                onPressed: roomState.actionInFlight ? null : onReconnect,
                child: const Text('Reconnect provider'),
              ),
          ],
        ),
      ),
    );
  }
}

// CatalogCard, QueueCard, FinalistsCard, ParticipantsCard, ManageRoomCard
// extracted to room_catalog_card.dart and room_queue_cards.dart
// RoomChip, RoomColorDot, hasClimbMeta, parseClimbColor also in room_catalog_card.dart
