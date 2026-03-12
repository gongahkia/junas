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
import '../../../core/models/session_models.dart';
import '../../../core/presentation/gradient_scaffold.dart';
import '../../../core/storage/app_prefs_controller.dart';
import '../../../core/storage/provider_secret_repository.dart';
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

class RoomScreen extends ConsumerStatefulWidget {
  const RoomScreen({
    super.key,
    required this.server,
    required this.slug,
  });

  final String server;
  final String slug;

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

  bool _rememberProviderSecret = false;
  bool _showQr = false;
  bool _shareBusy = false;
  String _boundRoomName = '';

  RoomRouteArgs get _args =>
      RoomRouteArgs(server: widget.server, slug: widget.slug);

  @override
  void initState() {
    super.initState();
    WakelockPlus.enable();
    unawaited(_loadRememberedProviderSecret());
  }

  @override
  void dispose() {
    _roomNameController.dispose();
    _catalogQueryController.dispose();
    _kilterUsernameController.dispose();
    _kilterPasswordController.dispose();
    _cruxTokenController.dispose();
    WakelockPlus.disable();
    super.dispose();
  }

  Future<void> _loadRememberedProviderSecret() async {
    try {
      final RoomViewState roomState = ref.read(roomControllerProvider(_args));
      final RoomSnapshot? room = roomState.room;
      if (room == null) {
        return;
      }
      final Map<String, String> secret =
          await ref.read(providerSecretRepositoryProvider).readSecret(
                server: _args.serverUri,
                providerId: room.providerId,
              );
      if (!mounted || secret.isEmpty) {
        return;
      }
      setState(() {
        _rememberProviderSecret = true;
        _kilterUsernameController.text = secret['username'] ?? '';
        _kilterPasswordController.text = secret['password'] ?? '';
        _cruxTokenController.text = secret['token'] ?? '';
      });
    } catch (_) {
      // Ignore secure-store read failures and keep the reconnect inputs manual.
    }
  }

  Future<void> _shareInvite(Uri inviteUri, String roomName) async {
    setState(() {
      _shareBusy = true;
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

  Future<void> _copyInvite(Uri inviteUri) async {
    await Clipboard.setData(ClipboardData(text: inviteUri.toString()));
    if (!mounted) {
      return;
    }
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Invite copied to the clipboard.')),
    );
  }

  Future<void> _submitReconnect(RoomSnapshot room) async {
    final Map<String, String> secret = room.providerId == 'kilter'
        ? <String, String>{
            'username': _kilterUsernameController.text.trim(),
            'password': _kilterPasswordController.text,
          }
        : <String, String>{
            'token': _cruxTokenController.text.trim(),
          };

    await ref
        .read(roomControllerProvider(_args).notifier)
        .reconnectProvider(secret);

    if (_rememberProviderSecret) {
      await ref.read(providerSecretRepositoryProvider).saveSecret(
            server: _args.serverUri,
            providerId: room.providerId,
            secret: secret,
          );
      await ref
          .read(appPrefsControllerProvider.notifier)
          .rememberProviderSecretPreference(
            providerId: room.providerId,
            remember: true,
          );
    } else {
      await ref.read(providerSecretRepositoryProvider).clearSecret(
            server: _args.serverUri,
            providerId: room.providerId,
          );
      await ref
          .read(appPrefsControllerProvider.notifier)
          .rememberProviderSecretPreference(
            providerId: room.providerId,
            remember: false,
          );
    }
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
    if (room.surface == null || room.surface!.id != seed.surface.id) {
      messenger.showSnackBar(
        SnackBar(
          content: Text(
            'Choose ${seed.surface.name} as the room surface before importing the saved plan.',
          ),
        ),
      );
      return;
    }

    await ref.read(roomControllerProvider(_args).notifier).importPendingSeed(
          seed.climbs
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

  @override
  Widget build(BuildContext context) {
    final RoomViewState roomState = ref.watch(roomControllerProvider(_args));
    final RoomController controller =
        ref.read(roomControllerProvider(_args).notifier);
    final AppPrefs prefs = ref.watch(appPrefsControllerProvider).valueOrNull ??
        AppPrefs.defaults();

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
    });

    final RoomSnapshot? room = roomState.room;
    final ThemeData theme = Theme.of(context);
    final TextTheme textTheme = theme.textTheme;

    if (roomState.loading && room == null) {
      return GradientScaffold(
        title: 'Room ${widget.slug}',
        subtitle: widget.server,
        actions: <Widget>[
          IconButton(
            onPressed: () => context.goNamed('landing'),
            icon: const Icon(Icons.close),
          ),
        ],
        child: const Center(
          child: Padding(
            padding: EdgeInsets.all(36),
            child: CircularProgressIndicator(),
          ),
        ),
      );
    }

    if (roomState.requiresRejoin || room == null) {
      return GradientScaffold(
        title: 'Room unavailable',
        subtitle: widget.server,
        actions: <Widget>[
          IconButton(
            onPressed: () => context.goNamed('landing'),
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
                      'server': widget.server,
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
      server: roomState.server,
      slug: room.slug,
    );
    final Uri inviteUri = invite.toUri();

    return GradientScaffold(
      title: room.roomName ?? 'Room ${room.slug}',
      subtitle: describeServer(roomState.server),
      actions: <Widget>[
        IconButton(
          onPressed: roomState.refreshing
              ? null
              : () => unawaited(controller.refresh()),
          icon: Icon(roomState.refreshing ? Icons.sync : Icons.refresh),
        ),
        IconButton(
          onPressed: _shareBusy
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
              accent: const Color(0xFFB91C1C),
            ),
            const SizedBox(height: 14),
          ],
          if (roomState.notice != null) ...<Widget>[
            _MessageCard(
              title: 'Updated',
              message: roomState.notice!,
              accent: const Color(0xFF0F766E),
            ),
            const SizedBox(height: 14),
          ],
          if (prefs.pendingRoomSeed != null &&
              prefs.pendingRoomSeed!.providerId == room.providerId) ...<Widget>[
            _PendingRoomSeedCard(
              seed: prefs.pendingRoomSeed!,
              room: room,
              actionInFlight: roomState.actionInFlight,
              onImport: () => unawaited(
                  _importPendingRoomSeed(prefs.pendingRoomSeed!, room)),
            ),
            const SizedBox(height: 14),
          ],
          _OverviewCard(room: room),
          const SizedBox(height: 14),
          _InviteCard(
            inviteUri: inviteUri,
            showQr: _showQr,
            onToggleQr: () => setState(() => _showQr = !_showQr),
            onCopy: () => unawaited(_copyInvite(inviteUri)),
            onShare: _shareBusy
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
          if (room.permissions.manageSurface ||
              room.connection.connected) ...<Widget>[
            _SurfaceCard(
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
                  ? () => unawaited(controller.setSurface())
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
            ),
            const SizedBox(height: 14),
          ],
          _CatalogCard(
            roomState: roomState,
            queryController: _catalogQueryController,
            sortOptions: _catalogSorts,
            onSearch: () => unawaited(
              controller.loadCatalog(
                q: _catalogQueryController.text.trim(),
                sort: roomState.catalogSort,
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
          _QueueCard(
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
          ),
          const SizedBox(height: 14),
          _FinalistsCard(
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
          _ParticipantsCard(
            room: room,
            onRoleChanged: (int participantId, String? role) {
              if (role == null) {
                return;
              }
              unawaited(controller.updateParticipantRole(participantId, role));
            },
            onRemove: (int participantId) =>
                unawaited(controller.removeParticipant(participantId)),
          ),
          const SizedBox(height: 14),
          _ManageRoomCard(
            room: room,
            roomNameController: _roomNameController,
            assistantModes: _assistantModes,
            busy: roomState.actionInFlight,
            onSaveName: room.permissions.editRoomSettings
                ? () => unawaited(
                    controller.updateRoomName(_roomNameController.text.trim()))
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
            onCloseRoom: room.permissions.closeRoom
                ? () async {
                    final GoRouter router = GoRouter.of(context);
                    await controller.closeRoom();
                    if (!mounted) {
                      return;
                    }
                    router.goNamed('landing');
                  }
                : null,
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
          borderRadius: BorderRadius.circular(28),
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
  });

  final PendingRoomSeed seed;
  final RoomSnapshot room;
  final bool actionInFlight;
  final VoidCallback onImport;

  @override
  Widget build(BuildContext context) {
    final bool surfaceMatches = room.surface?.id == seed.surface.id;

    return Card(
      child: Container(
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(28),
          gradient: const LinearGradient(
            colors: <Color>[
              Color(0xFFECFDF5),
              Colors.white,
            ],
          ),
        ),
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              'Saved plan seed is ready',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 8),
            Text(
              '${seed.surface.name} · ${seed.climbs.length} climb${seed.climbs.length == 1 ? '' : 's'}',
            ),
            const SizedBox(height: 10),
            Text(
              surfaceMatches
                  ? 'This room already matches the saved plan context. Import the queued climbs directly.'
                  : 'Choose ${seed.surface.name} as the room surface first, then import the saved queue.',
            ),
            const SizedBox(height: 14),
            FilledButton.tonal(
              onPressed: surfaceMatches && !actionInFlight ? onImport : null,
              child: const Text('Import plan to queue'),
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
                _Chip(label: room.providerId.toUpperCase()),
                _Chip(label: room.status.toUpperCase()),
                _Chip(
                    label: room.connection.connected
                        ? 'CONNECTED'
                        : 'AUTH REQUIRED'),
                if (room.surface != null) _Chip(label: room.surface!.name),
              ],
            ),
            const SizedBox(height: 14),
            Text(
              room.currentClimb?.name ?? 'No current climb selected',
              style: textTheme.headlineMedium,
            ),
            if (room.currentClimb?.primaryGrade != null) ...<Widget>[
              const SizedBox(height: 6),
              Text(room.currentClimb!.primaryGrade!),
            ],
            if (room.assistant.message != null ||
                room.assistant.suggestion != null) ...<Widget>[
              const SizedBox(height: 16),
              Container(
                decoration: BoxDecoration(
                  color: const Color(0xFFE8F7F2),
                  borderRadius: BorderRadius.circular(22),
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

class _InviteCard extends StatelessWidget {
  const _InviteCard({
    required this.inviteUri,
    required this.showQr,
    required this.onToggleQr,
    required this.onCopy,
    required this.onShare,
  });

  final Uri inviteUri;
  final bool showQr;
  final VoidCallback onToggleQr;
  final VoidCallback onCopy;
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
            SelectableText(inviteUri.toString()),
            const SizedBox(height: 14),
            Wrap(
              spacing: 10,
              runSpacing: 10,
              children: <Widget>[
                FilledButton.tonal(
                  onPressed: onCopy,
                  child: const Text('Copy invite'),
                ),
                FilledButton.tonal(
                  onPressed: onShare,
                  child: const Text('Share invite'),
                ),
                OutlinedButton(
                  onPressed: onToggleQr,
                  child: Text(showQr ? 'Hide QR' : 'Show QR'),
                ),
              ],
            ),
            if (showQr) ...<Widget>[
              const SizedBox(height: 18),
              Center(
                child: QrImageView(
                  data: inviteUri.toString(),
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
                onPressed: onSaveSurface,
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
                onPressed: onReconnect,
                child: const Text('Reconnect provider'),
              ),
          ],
        ),
      ),
    );
  }
}

class _CatalogCard extends StatelessWidget {
  const _CatalogCard({
    required this.roomState,
    required this.queryController,
    required this.sortOptions,
    required this.onSearch,
    required this.onSortChanged,
    required this.onSelectClimb,
    required this.onLoadMore,
    required this.onToggleVote,
    required this.onAddQueue,
    required this.onAddFinalist,
    required this.onPromoteCurrent,
    required this.onPromoteNext,
  });

  final RoomViewState roomState;
  final TextEditingController queryController;
  final List<String> sortOptions;
  final VoidCallback onSearch;
  final ValueChanged<String?> onSortChanged;
  final ValueChanged<String> onSelectClimb;
  final VoidCallback? onLoadMore;
  final ValueChanged<String> onToggleVote;
  final ValueChanged<String> onAddQueue;
  final ValueChanged<String> onAddFinalist;
  final ValueChanged<String> onPromoteCurrent;
  final ValueChanged<String> onPromoteNext;

  @override
  Widget build(BuildContext context) {
    final RoomSnapshot room = roomState.room!;
    final RoomCatalogClimbsResponse? catalog = roomState.catalog;
    final RoomCatalogClimbResponse? selectedClimb =
        roomState.selectedCatalogClimb;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(22),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              'Catalog',
              style: Theme.of(context).textTheme.headlineMedium,
            ),
            const SizedBox(height: 12),
            TextField(
              controller: queryController,
              decoration: InputDecoration(
                labelText: 'Search climbs',
                suffixIcon: IconButton(
                  onPressed: onSearch,
                  icon: const Icon(Icons.search),
                ),
              ),
              onSubmitted: (_) => onSearch(),
            ),
            const SizedBox(height: 12),
            DropdownButtonFormField<String>(
              initialValue: roomState.catalogSort,
              decoration: const InputDecoration(labelText: 'Sort'),
              items: sortOptions
                  .map(
                    (String value) => DropdownMenuItem<String>(
                      value: value,
                      child: Text(value),
                    ),
                  )
                  .toList(growable: false),
              onChanged: onSortChanged,
            ),
            if (selectedClimb != null) ...<Widget>[
              const SizedBox(height: 16),
              Container(
                decoration: BoxDecoration(
                  color: const Color(0xFFE9F4FF),
                  borderRadius: BorderRadius.circular(22),
                ),
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Text(
                      selectedClimb.climb.name,
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                    const SizedBox(height: 6),
                    Text(selectedClimb.climb.setterName ?? 'Unknown setter'),
                    if (selectedClimb.climb.primaryGrade != null) ...<Widget>[
                      const SizedBox(height: 6),
                      Text(selectedClimb.climb.primaryGrade!),
                    ],
                    const SizedBox(height: 12),
                    Wrap(
                      spacing: 10,
                      runSpacing: 10,
                      children: <Widget>[
                        FilledButton.tonal(
                          onPressed: () => onToggleVote(selectedClimb.climb.id),
                          child: Text(
                              selectedClimb.myVote ? 'Remove vote' : 'Vote'),
                        ),
                        if (room.permissions.manageQueue)
                          FilledButton.tonal(
                            onPressed: () => onAddQueue(selectedClimb.climb.id),
                            child: const Text('Queue'),
                          ),
                        if (room.permissions.manageFinalists)
                          FilledButton.tonal(
                            onPressed: () =>
                                onAddFinalist(selectedClimb.climb.id),
                            child: const Text('Finalist'),
                          ),
                        if (room.permissions.manageSession)
                          FilledButton.tonal(
                            onPressed: () =>
                                onPromoteCurrent(selectedClimb.climb.id),
                            child: const Text('Current'),
                          ),
                        if (room.permissions.manageSession)
                          FilledButton.tonal(
                            onPressed: () =>
                                onPromoteNext(selectedClimb.climb.id),
                            child: const Text('Next'),
                          ),
                      ],
                    ),
                  ],
                ),
              ),
            ],
            const SizedBox(height: 16),
            if (roomState.catalogLoading)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 18),
                child: Center(child: CircularProgressIndicator()),
              )
            else if (catalog == null || catalog.climbs.isEmpty)
              const Text('No climbs are loaded for this room surface yet.')
            else
              ...catalog.climbs.map(
                (ProviderClimb climb) => ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: Text(climb.name),
                  subtitle: Text(
                    [
                      if ((climb.setterName ?? '').isNotEmpty)
                        climb.setterName!,
                      if ((climb.primaryGrade ?? '').isNotEmpty)
                        climb.primaryGrade!,
                    ].join(' · '),
                  ),
                  trailing: Text('${catalog.voteCounts[climb.id] ?? 0}'),
                  onTap: () => onSelectClimb(climb.id),
                ),
              ),
            if (onLoadMore != null) ...<Widget>[
              const SizedBox(height: 12),
              Align(
                alignment: Alignment.centerLeft,
                child: FilledButton.tonal(
                  onPressed: onLoadMore,
                  child: const Text('Load more climbs'),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _QueueCard extends StatelessWidget {
  const _QueueCard({
    required this.room,
    required this.queueStatuses,
    required this.onMoveUp,
    required this.onMoveDown,
    required this.onDelete,
    required this.onPromoteCurrent,
    required this.onPromoteNext,
    required this.onStatusChanged,
  });

  final RoomSnapshot room;
  final List<String> queueStatuses;
  final ValueChanged<int> onMoveUp;
  final ValueChanged<int> onMoveDown;
  final ValueChanged<int> onDelete;
  final ValueChanged<String> onPromoteCurrent;
  final ValueChanged<String> onPromoteNext;
  final void Function(int entryId, String? value) onStatusChanged;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(22),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              'Queue',
              style: Theme.of(context).textTheme.headlineMedium,
            ),
            const SizedBox(height: 12),
            if (room.queue.isEmpty)
              const Text('No climbs are queued yet.')
            else
              ...room.queue.map(
                (QueueEntry entry) => Padding(
                  padding: const EdgeInsets.only(bottom: 14),
                  child: Container(
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(22),
                      border: Border.all(color: const Color(0xFFE2E8F0)),
                    ),
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Text(entry.climb.name,
                            style: Theme.of(context).textTheme.titleLarge),
                        const SizedBox(height: 6),
                        Text('${entry.status} · added by ${entry.addedBy}'),
                        const SizedBox(height: 12),
                        Wrap(
                          spacing: 10,
                          runSpacing: 10,
                          children: <Widget>[
                            if (room.permissions.manageQueue)
                              SizedBox(
                                width: 180,
                                child: DropdownButtonFormField<String>(
                                  initialValue: entry.status,
                                  decoration: const InputDecoration(
                                      labelText: 'Status'),
                                  items: queueStatuses
                                      .map(
                                        (String value) =>
                                            DropdownMenuItem<String>(
                                          value: value,
                                          child: Text(value),
                                        ),
                                      )
                                      .toList(growable: false),
                                  onChanged: (String? value) =>
                                      onStatusChanged(entry.id, value),
                                ),
                              ),
                            if (room.permissions.manageQueue)
                              OutlinedButton(
                                onPressed: () => onMoveUp(entry.id),
                                child: const Text('Up'),
                              ),
                            if (room.permissions.manageQueue)
                              OutlinedButton(
                                onPressed: () => onMoveDown(entry.id),
                                child: const Text('Down'),
                              ),
                            if (room.permissions.manageSession)
                              FilledButton.tonal(
                                onPressed: () =>
                                    onPromoteCurrent(entry.climb.id),
                                child: const Text('Current'),
                              ),
                            if (room.permissions.manageSession)
                              FilledButton.tonal(
                                onPressed: () => onPromoteNext(entry.climb.id),
                                child: const Text('Next'),
                              ),
                            if (room.permissions.manageQueue)
                              OutlinedButton(
                                onPressed: () => onDelete(entry.id),
                                child: const Text('Delete'),
                              ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _FinalistsCard extends StatelessWidget {
  const _FinalistsCard({
    required this.room,
    required this.onMoveUp,
    required this.onMoveDown,
    required this.onDelete,
    required this.onPickRandomFinalists,
    required this.onPickRandomTopVoted,
    required this.onPromoteCurrent,
    required this.onPromoteNext,
  });

  final RoomSnapshot room;
  final ValueChanged<int> onMoveUp;
  final ValueChanged<int> onMoveDown;
  final ValueChanged<int> onDelete;
  final VoidCallback onPickRandomFinalists;
  final VoidCallback onPickRandomTopVoted;
  final ValueChanged<String> onPromoteCurrent;
  final ValueChanged<String> onPromoteNext;

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
                    'Finalists',
                    style: Theme.of(context).textTheme.headlineMedium,
                  ),
                ),
                if (room.permissions.manageFinalists)
                  PopupMenuButton<String>(
                    onSelected: (String value) {
                      if (value == 'finalists') {
                        onPickRandomFinalists();
                      } else {
                        onPickRandomTopVoted();
                      }
                    },
                    itemBuilder: (BuildContext context) =>
                        const <PopupMenuEntry<String>>[
                      PopupMenuItem<String>(
                        value: 'finalists',
                        child: Text('Pick random finalist'),
                      ),
                      PopupMenuItem<String>(
                        value: 'top_voted',
                        child: Text('Pick from top voted'),
                      ),
                    ],
                  ),
              ],
            ),
            const SizedBox(height: 12),
            if (room.finalists.isEmpty)
              const Text('No finalists selected yet.')
            else
              ...room.finalists.map(
                (FinalistEntry entry) => Padding(
                  padding: const EdgeInsets.only(bottom: 14),
                  child: Container(
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(22),
                      border: Border.all(color: const Color(0xFFE2E8F0)),
                    ),
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Text(entry.climb.name,
                            style: Theme.of(context).textTheme.titleLarge),
                        const SizedBox(height: 6),
                        Text('Added by ${entry.addedBy}'),
                        const SizedBox(height: 12),
                        Wrap(
                          spacing: 10,
                          runSpacing: 10,
                          children: <Widget>[
                            if (room.permissions.manageFinalists)
                              OutlinedButton(
                                onPressed: () => onMoveUp(entry.id),
                                child: const Text('Up'),
                              ),
                            if (room.permissions.manageFinalists)
                              OutlinedButton(
                                onPressed: () => onMoveDown(entry.id),
                                child: const Text('Down'),
                              ),
                            if (room.permissions.manageSession)
                              FilledButton.tonal(
                                onPressed: () =>
                                    onPromoteCurrent(entry.climb.id),
                                child: const Text('Current'),
                              ),
                            if (room.permissions.manageSession)
                              FilledButton.tonal(
                                onPressed: () => onPromoteNext(entry.climb.id),
                                child: const Text('Next'),
                              ),
                            if (room.permissions.manageFinalists)
                              OutlinedButton(
                                onPressed: () => onDelete(entry.id),
                                child: const Text('Delete'),
                              ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _ParticipantsCard extends StatelessWidget {
  const _ParticipantsCard({
    required this.room,
    required this.onRoleChanged,
    required this.onRemove,
  });

  final RoomSnapshot room;
  final void Function(int participantId, String? role) onRoleChanged;
  final ValueChanged<int> onRemove;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(22),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              'Participants',
              style: Theme.of(context).textTheme.headlineMedium,
            ),
            const SizedBox(height: 12),
            ...room.participants.map(
              (Participant participant) => Padding(
                padding: const EdgeInsets.only(bottom: 14),
                child: Container(
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(22),
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
                              participant.displayName,
                              style: Theme.of(context).textTheme.titleLarge,
                            ),
                          ),
                          Icon(
                            participant.isOnline
                                ? Icons.circle
                                : Icons.circle_outlined,
                            size: 14,
                            color: participant.isOnline
                                ? const Color(0xFF0F766E)
                                : const Color(0xFF94A3B8),
                          ),
                        ],
                      ),
                      const SizedBox(height: 6),
                      Text('${participant.role} · ${participant.status}'),
                      if (room.permissions.assignCoHosts &&
                          participant.role != 'host') ...<Widget>[
                        const SizedBox(height: 12),
                        DropdownButtonFormField<String>(
                          initialValue: participant.role == 'co_host'
                              ? 'co_host'
                              : 'participant',
                          decoration: const InputDecoration(labelText: 'Role'),
                          items: const <DropdownMenuItem<String>>[
                            DropdownMenuItem<String>(
                              value: 'participant',
                              child: Text('participant'),
                            ),
                            DropdownMenuItem<String>(
                              value: 'co_host',
                              child: Text('co_host'),
                            ),
                          ],
                          onChanged: (String? value) =>
                              onRoleChanged(participant.id, value),
                        ),
                      ],
                      if (room.permissions.manageParticipants &&
                          participant.displayName != room.displayName &&
                          participant.role != 'host') ...<Widget>[
                        const SizedBox(height: 12),
                        OutlinedButton(
                          onPressed: () => onRemove(participant.id),
                          child: const Text('Remove participant'),
                        ),
                      ],
                    ],
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ManageRoomCard extends StatelessWidget {
  const _ManageRoomCard({
    required this.room,
    required this.roomNameController,
    required this.assistantModes,
    required this.busy,
    required this.onSaveName,
    required this.onAssistantModeChanged,
    required this.onFistBumpsChanged,
    required this.onClearVotes,
    required this.onCloseRoom,
  });

  final RoomSnapshot room;
  final TextEditingController roomNameController;
  final List<String> assistantModes;
  final bool busy;
  final VoidCallback? onSaveName;
  final ValueChanged<String?>? onAssistantModeChanged;
  final ValueChanged<bool>? onFistBumpsChanged;
  final VoidCallback? onClearVotes;
  final VoidCallback? onCloseRoom;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(22),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              'Room controls',
              style: Theme.of(context).textTheme.headlineMedium,
            ),
            const SizedBox(height: 12),
            TextField(
              controller: roomNameController,
              decoration: const InputDecoration(labelText: 'Room name'),
            ),
            const SizedBox(height: 10),
            if (onSaveName != null)
              FilledButton.tonal(
                onPressed: busy ? null : onSaveName,
                child: const Text('Save room name'),
              ),
            const SizedBox(height: 12),
            DropdownButtonFormField<String>(
              initialValue: room.assistant.mode,
              decoration: const InputDecoration(labelText: 'Assistant mode'),
              items: assistantModes
                  .map(
                    (String value) => DropdownMenuItem<String>(
                      value: value,
                      child: Text(value),
                    ),
                  )
                  .toList(growable: false),
              onChanged: onAssistantModeChanged,
            ),
            const SizedBox(height: 10),
            SwitchListTile.adaptive(
              contentPadding: EdgeInsets.zero,
              value: room.fistBumpsEnabled,
              onChanged: onFistBumpsChanged,
              title: const Text('Enable fist bumps'),
            ),
            const SizedBox(height: 12),
            Wrap(
              spacing: 10,
              runSpacing: 10,
              children: <Widget>[
                if (onClearVotes != null)
                  OutlinedButton(
                    onPressed: busy ? null : onClearVotes,
                    child: const Text('Clear votes'),
                  ),
                if (onCloseRoom != null)
                  FilledButton(
                    onPressed: busy ? null : onCloseRoom,
                    child: const Text('Close room'),
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _Chip extends StatelessWidget {
  const _Chip({
    required this.label,
  });

  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: const Color(0xFFE7F8F4),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        label,
        style: const TextStyle(
          fontWeight: FontWeight.w700,
          letterSpacing: 0.2,
        ),
      ),
    );
  }
}

extension<T> on Iterable<T> {
  T? get firstOrNull {
    if (isEmpty) {
      return null;
    }
    return first;
  }
}
