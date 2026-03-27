import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/models/app_prefs_models.dart';
import '../../../core/p2p/p2p_provider.dart';
import '../../../core/p2p/p2p_transport.dart';
import '../../../core/presentation/app_surfaces.dart';
import '../../../core/presentation/gradient_scaffold.dart';
import '../../../core/storage/app_prefs_controller.dart';
import '../../../core/theme/app_theme.dart';

String _providerLabel(String providerId) {
  return switch (providerId) {
    'kilter' => 'Kilter',
    'crux' => 'Crux',
    _ => providerId,
  };
}

String _formatRelativeTime(String raw) {
  final DateTime? parsed = DateTime.tryParse(raw);
  if (parsed == null) {
    return raw;
  }

  final Duration diff = DateTime.now().toUtc().difference(parsed.toUtc());
  if (diff.inMinutes < 1) {
    return 'just now';
  }
  if (diff.inMinutes < 60) {
    return '${diff.inMinutes}m ago';
  }
  if (diff.inHours < 24) {
    return '${diff.inHours}h ago';
  }
  if (diff.inDays < 7) {
    return '${diff.inDays}d ago';
  }
  return '${(diff.inDays / 7).floor()}w ago';
}

class SessionHomeScreen extends ConsumerStatefulWidget {
  const SessionHomeScreen({super.key});

  @override
  ConsumerState<SessionHomeScreen> createState() => _SessionHomeScreenState();
}

class _SessionHomeScreenState extends ConsumerState<SessionHomeScreen> {
  List<P2pPeer> _nearbyPeers = <P2pPeer>[];
  StreamSubscription<P2pPeer>? _discoverySub;
  bool _scanning = false;

  P2pTransport? _transport;

  @override
  void dispose() {
    _discoverySub?.cancel();
    if (_scanning) {
      unawaited(_transport?.stopDiscovery() ?? Future<void>.value());
    }
    super.dispose();
  }

  Future<void> _scanNearby() async {
    setState(() {
      _scanning = true;
      _nearbyPeers = <P2pPeer>[];
    });
    final P2pTransport transport = ref.read(p2pTransportProvider);
    _transport = transport;
    _discoverySub?.cancel();
    _discoverySub = transport.discoveredPeers.listen((P2pPeer peer) {
      if (!mounted) {
        return;
      }
      setState(() {
        if (!_nearbyPeers.any((P2pPeer item) => item.id == peer.id)) {
          _nearbyPeers = <P2pPeer>[..._nearbyPeers, peer];
        }
      });
    });
    try {
      await transport.startDiscovery(serviceId: p2pServiceId);
    } catch (_) {
      if (mounted) {
        setState(() {
          _scanning = false;
        });
      }
    }

    Future<void>.delayed(const Duration(seconds: 8), () {
      if (!mounted) {
        return;
      }
      unawaited(transport.stopDiscovery());
      _discoverySub?.cancel();
      setState(() {
        _scanning = false;
      });
    });
  }

  @override
  Widget build(BuildContext context) {
    final KilterPalette palette = kilterPaletteOf(context);
    final AsyncValue<AppPrefs> prefsValue =
        ref.watch(appPrefsControllerProvider);
    final AppPrefs prefs = prefsValue.valueOrNull ?? AppPrefs.defaults();
    final List<RecentRoom> previewRecentRooms =
        prefs.recentRooms.take(3).toList(growable: false);

    return GradientScaffold(
      title: 'Session',
      subtitle:
          'Host or join a P2P climbing session. Nearby phones coordinate directly, even when you are off-grid at the wall.',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          LayoutBuilder(
            builder: (BuildContext context, BoxConstraints constraints) {
              final Axis direction =
                  constraints.maxWidth < 560 ? Axis.vertical : Axis.horizontal;
              return Flex(
                direction: direction,
                children: <Widget>[
                  Expanded(
                    child: _HomeActionCard(
                      accent: palette.primary,
                      icon: Icons.add_home_work_outlined,
                      eyebrow: 'Host lane',
                      title: 'Start the room',
                      description:
                          'Own the surface, invite link, queue, and live room flow from this phone.',
                      actionLabel: 'Host a session',
                      onTap: () {
                        unawaited(
                          ref
                              .read(appPrefsControllerProvider.notifier)
                              .queueGuideBranch('host'),
                        );
                        context.goNamed('create-room');
                      },
                    ),
                  ),
                  SizedBox(
                    width: direction == Axis.horizontal ? 14 : 0,
                    height: direction == Axis.vertical ? 14 : 0,
                  ),
                  Expanded(
                    child: _HomeActionCard(
                      accent: palette.highlight,
                      icon: Icons.qr_code_scanner_rounded,
                      eyebrow: 'Guest lane',
                      title: 'Jump into a room',
                      description:
                          'Scan a QR or pick a nearby host as soon as they start advertising.',
                      actionLabel: 'Join a session',
                      onTap: () {
                        unawaited(
                          ref
                              .read(appPrefsControllerProvider.notifier)
                              .queueGuideBranch('guest'),
                        );
                        context.goNamed('join-room');
                      },
                    ),
                  ),
                ],
              );
            },
          ),
          const SizedBox(height: 16),
          AppPanel(
            accentColor: palette.secondary,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: <Widget>[
                          Text(
                            'Nearby sessions',
                            style: Theme.of(context).textTheme.titleLarge,
                          ),
                          const SizedBox(height: 8),
                          Text(
                            _scanning
                                ? 'Scanning for hosts over Bluetooth and Wi-Fi direct.'
                                : 'Kick off discovery to see live rooms that are already advertising nearby.',
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(width: 12),
                    AppBadge(
                      label: _scanning
                          ? 'Scanning'
                          : '${_nearbyPeers.length} found',
                      icon: _scanning
                          ? Icons.bluetooth_searching_rounded
                          : Icons.podcasts_rounded,
                      color: _scanning ? palette.highlight : palette.secondary,
                    ),
                  ],
                ),
                const SizedBox(height: 18),
                SizedBox(
                  width: double.infinity,
                  child: OutlinedButton.icon(
                    onPressed: _scanning ? null : _scanNearby,
                    icon: Icon(
                      _scanning
                          ? Icons.motion_photos_pause_rounded
                          : Icons.radar_rounded,
                    ),
                    label: Text(_scanning ? 'Scanning nearby' : 'Scan nearby'),
                  ),
                ),
                const SizedBox(height: 18),
                if (_nearbyPeers.isEmpty)
                  _InlineHint(
                    message: _scanning
                        ? 'Looking for nearby hosts. Ask the host phone to stay open on the created-room screen.'
                        : 'No hosts discovered yet. Discovery only shows rooms that are actively advertising.',
                  )
                else
                  Column(
                    children:
                        List<Widget>.generate(_nearbyPeers.length, (int index) {
                      final P2pPeer peer = _nearbyPeers[index];
                      final List<String> parts = peer.displayName.split('|');
                      final String roomName =
                          parts.isNotEmpty ? parts.first : peer.displayName;

                      return Padding(
                        padding: EdgeInsets.only(
                          bottom: index == _nearbyPeers.length - 1 ? 0 : 10,
                        ),
                        child: AppPanel(
                          padding: const EdgeInsets.all(18),
                          accentColor: palette.secondary,
                          backgroundColor: Colors.white,
                          onTap: () {
                            unawaited(
                              ref
                                  .read(appPrefsControllerProvider.notifier)
                                  .queueGuideBranch('guest'),
                            );
                            context.goNamed('join-room');
                          },
                          child: Row(
                            children: <Widget>[
                              Container(
                                width: 44,
                                height: 44,
                                decoration: BoxDecoration(
                                  color:
                                      palette.secondary.withValues(alpha: 0.14),
                                  borderRadius: BorderRadius.circular(16),
                                ),
                                child: Icon(
                                  Icons.wifi_tethering_rounded,
                                  color: palette.secondary,
                                ),
                              ),
                              const SizedBox(width: 14),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: <Widget>[
                                    Text(
                                      roomName,
                                      style: Theme.of(context)
                                          .textTheme
                                          .titleMedium,
                                    ),
                                    const SizedBox(height: 4),
                                    Text(
                                      'Tap to continue into the guest join flow.',
                                      style:
                                          Theme.of(context).textTheme.bodySmall,
                                    ),
                                  ],
                                ),
                              ),
                              Icon(
                                Icons.arrow_forward_rounded,
                                color: palette.subtleInk,
                              ),
                            ],
                          ),
                        ),
                      );
                    }),
                  ),
              ],
            ),
          ),
          const SizedBox(height: 24),
          Text(
            'Recent rooms',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 10),
          if (!prefs.settings.recentRoomsEnabled)
            const _InlineHint(
              message:
                  'Recent rooms are turned off in Settings for this device.',
            )
          else if (prefs.recentRooms.isEmpty)
            const _InlineHint(
              message: 'No recent rooms saved on this device yet.',
            )
          else
            Column(
              children: previewRecentRooms
                  .map(
                    (RecentRoom room) => Padding(
                      padding: const EdgeInsets.only(bottom: 10),
                      child: _RecentRoomTile(room: room),
                    ),
                  )
                  .toList(growable: false),
            ),
        ],
      ),
    );
  }
}

class _HomeActionCard extends StatelessWidget {
  const _HomeActionCard({
    required this.accent,
    required this.icon,
    required this.eyebrow,
    required this.title,
    required this.description,
    required this.actionLabel,
    required this.onTap,
  });

  final Color accent;
  final IconData icon;
  final String eyebrow;
  final String title;
  final String description;
  final String actionLabel;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return AppPanel(
      accentColor: accent,
      onTap: onTap,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          AppBadge(
            label: eyebrow,
            icon: icon,
            color: accent,
          ),
          const SizedBox(height: 18),
          Text(
            title,
            style: Theme.of(context).textTheme.headlineMedium,
          ),
          const SizedBox(height: 10),
          Text(description),
          const SizedBox(height: 18),
          Row(
            children: <Widget>[
              Text(
                actionLabel,
                style: Theme.of(context).textTheme.labelLarge?.copyWith(
                      color: accent,
                    ),
              ),
              const SizedBox(width: 8),
              Icon(Icons.arrow_outward_rounded, color: accent),
            ],
          ),
        ],
      ),
    );
  }
}

class _InlineHint extends StatelessWidget {
  const _InlineHint({
    required this.message,
  });

  final String message;

  @override
  Widget build(BuildContext context) {
    final KilterPalette palette = kilterPaletteOf(context);
    return AppPanel(
      accentColor: palette.secondary,
      backgroundColor: palette.panelRaised,
      child: Text(message),
    );
  }
}

class _RecentRoomTile extends StatelessWidget {
  const _RecentRoomTile({
    required this.room,
  });

  final RecentRoom room;

  @override
  Widget build(BuildContext context) {
    final KilterPalette palette = kilterPaletteOf(context);
    final String roomLabel = room.roomName ?? 'Room ${room.slug}';
    final String providerLabel = _providerLabel(room.providerId);
    final String surfaceLabel = (room.surfaceName ?? '').trim().isEmpty
        ? 'Surface pending'
        : room.surfaceName!;
    final String lastSeen = _formatRelativeTime(room.lastVisitedAt);

    return AppPanel(
      accentColor:
          room.providerId == 'crux' ? palette.highlight : palette.primary,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Text(
                      roomLabel,
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                    const SizedBox(height: 10),
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: <Widget>[
                        AppBadge(
                          label: providerLabel,
                          icon: Icons.interests_outlined,
                          color: room.providerId == 'crux'
                              ? palette.highlight
                              : palette.primary,
                        ),
                        AppBadge(
                          label: surfaceLabel,
                          icon: Icons.landscape_rounded,
                          color: palette.secondary,
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              Container(
                width: 44,
                height: 44,
                decoration: BoxDecoration(
                  color: palette.panelRaised,
                  borderRadius: BorderRadius.circular(16),
                ),
                child: Icon(
                  Icons.history_toggle_off_rounded,
                  color: palette.subtleInk,
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Text(
            'Last seen $lastSeen',
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ],
      ),
    );
  }
}
