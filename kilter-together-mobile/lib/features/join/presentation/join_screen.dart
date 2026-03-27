import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

import '../../../core/deep_links/invite_links.dart';
import '../../../core/models/app_prefs_models.dart';
import '../../../core/p2p/p2p_provider.dart';
import '../../../core/p2p/p2p_transport.dart';
import '../../../core/presentation/app_surfaces.dart';
import '../../../core/presentation/gradient_scaffold.dart';
import '../../../core/storage/app_prefs_controller.dart';
import '../../../core/storage/session_repository.dart';
import '../../../core/theme/app_theme.dart';

class JoinRoomScreen extends ConsumerStatefulWidget {
  const JoinRoomScreen({
    super.key,
    this.initialSlug,
    this.initialReason,
  });

  final String? initialSlug;
  final String? initialReason;

  @override
  ConsumerState<JoinRoomScreen> createState() => _JoinRoomScreenState();
}

class _JoinRoomScreenState extends ConsumerState<JoinRoomScreen> {
  final TextEditingController _displayNameController =
      TextEditingController(text: 'Guest');
  bool _discovering = false;
  bool _scannerOpen = false;
  List<P2pPeer> _discoveredPeers = <P2pPeer>[];
  StreamSubscription<P2pPeer>? _discoverySub;
  P2pTransport? _transport;
  String? _inlineError;

  @override
  void initState() {
    super.initState();
    ref.read(sessionRepositoryProvider).loadAppPrefs().then((AppPrefs prefs) {
      if (!mounted) {
        return;
      }
      if (prefs.savedDisplayName.trim().isNotEmpty) {
        setState(() {
          _displayNameController.text = prefs.savedDisplayName.trim();
        });
      }
    });
    unawaited(_startDiscovery());
  }

  @override
  void dispose() {
    _displayNameController.dispose();
    _discoverySub?.cancel();
    unawaited(_transport?.stopDiscovery() ?? Future<void>.value());
    super.dispose();
  }

  Future<void> _startDiscovery() async {
    setState(() {
      _discovering = true;
      _discoveredPeers = <P2pPeer>[];
    });
    final P2pTransport transport = ref.read(p2pTransportProvider);
    _transport = transport;
    _discoverySub?.cancel();
    _discoverySub = transport.discoveredPeers.listen((P2pPeer peer) {
      if (!mounted) {
        return;
      }
      setState(() {
        if (!_discoveredPeers.any((P2pPeer item) => item.id == peer.id)) {
          _discoveredPeers = <P2pPeer>[..._discoveredPeers, peer];
        }
      });
    });
    try {
      await transport.startDiscovery(serviceId: p2pServiceId);
    } catch (error) {
      if (mounted) {
        setState(() {
          _inlineError = 'Discovery failed: $error';
        });
      }
    }
  }

  void _joinPeer(P2pPeer peer) {
    final String displayName = _displayNameController.text.trim();
    if (displayName.isEmpty) {
      setState(() {
        _inlineError = 'Enter a display name.';
      });
      return;
    }
    unawaited(
      ref
          .read(appPrefsControllerProvider.notifier)
          .rememberDisplayName(displayName),
    );
    context.goNamed(
      'room',
      queryParameters: <String, String>{
        'slug': peer.id,
        'role': 'guest',
        'display_name': displayName,
        'host_peer_id': peer.id,
        'host_peer_name': peer.displayName,
      },
    );
  }

  void _handleQrDetected(String raw) {
    final InviteLink? invite = InviteLink.parse(raw);
    if (invite == null || invite.kind != InviteKind.join) {
      setState(() {
        _inlineError = 'Not a valid room invite QR.';
      });
      return;
    }
    final String slug = invite.slug ?? '';
    if (slug.isEmpty) {
      setState(() {
        _inlineError = 'QR missing room code.';
      });
      return;
    }
    final P2pPeer? match = _discoveredPeers.cast<P2pPeer?>().firstWhere(
          (P2pPeer? peer) => peer!.displayName.contains(slug),
          orElse: () => null,
        );
    if (match != null) {
      _joinPeer(match);
    } else {
      setState(() {
        _inlineError =
            'Scanned room "$slug" and will keep looking for the host nearby.';
        _scannerOpen = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final KilterPalette palette = kilterPaletteOf(context);

    return GradientScaffold(
      title: 'Join a room',
      subtitle:
          'Discover nearby P2P sessions or scan the host QR to fall straight into the shared room.',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          AppPanel(
            accentColor: palette.highlight,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: <Widget>[
                    AppBadge(
                      label: 'Guest join',
                      icon: Icons.group_add_rounded,
                      color: palette.highlight,
                    ),
                    if ((widget.initialSlug ?? '').trim().isNotEmpty)
                      AppBadge(
                        label: 'Invite ${widget.initialSlug!.trim()}',
                        icon: Icons.link_rounded,
                        color: palette.secondary,
                      ),
                  ],
                ),
                const SizedBox(height: 18),
                TextField(
                  controller: _displayNameController,
                  decoration: const InputDecoration(labelText: 'Display name'),
                ),
                if ((widget.initialReason ?? '').trim().isNotEmpty) ...<Widget>[
                  const SizedBox(height: 12),
                  Text(
                    widget.initialReason!.trim(),
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ],
                if (_inlineError != null) ...<Widget>[
                  const SizedBox(height: 16),
                  AppPanel(
                    padding: const EdgeInsets.all(16),
                    accentColor: const Color(0xFF9B3445),
                    backgroundColor: const Color(0xFFFFF4F5),
                    child: Text(_inlineError!),
                  ),
                ],
              ],
            ),
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
                            _discovering
                                ? 'Searching for hosts on the local transport.'
                                : 'Refresh discovery if the host started the room recently.',
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(width: 12),
                    AppBadge(
                      label: _discovering
                          ? 'Scanning'
                          : '${_discoveredPeers.length} live',
                      icon: _discovering
                          ? Icons.bluetooth_searching_rounded
                          : Icons.wifi_tethering_rounded,
                      color:
                          _discovering ? palette.highlight : palette.secondary,
                    ),
                  ],
                ),
                const SizedBox(height: 18),
                SizedBox(
                  width: double.infinity,
                  child: OutlinedButton.icon(
                    onPressed: _startDiscovery,
                    icon: const Icon(Icons.refresh_rounded),
                    label: const Text('Refresh discovery'),
                  ),
                ),
                const SizedBox(height: 18),
                if (_discoveredPeers.isEmpty)
                  AppPanel(
                    accentColor: palette.secondary,
                    backgroundColor: palette.panelRaised,
                    child: Text(
                      _discovering
                          ? 'Searching for nearby sessions. Ask the host to leave the room lobby open until you appear.'
                          : 'No nearby sessions found yet. Ask the host to start advertising again.',
                    ),
                  )
                else
                  Column(
                    children: List<Widget>.generate(_discoveredPeers.length,
                        (int index) {
                      final P2pPeer peer = _discoveredPeers[index];
                      final List<String> parts = peer.displayName.split('|');
                      final String roomName =
                          parts.isNotEmpty ? parts.first : peer.displayName;
                      final String slug = parts.length > 1 ? parts.last : '';

                      return Padding(
                        padding: EdgeInsets.only(
                          bottom: index == _discoveredPeers.length - 1 ? 0 : 10,
                        ),
                        child: AppPanel(
                          padding: const EdgeInsets.all(18),
                          accentColor: palette.secondary,
                          backgroundColor: Colors.white,
                          child: Row(
                            children: <Widget>[
                              Container(
                                width: 46,
                                height: 46,
                                decoration: BoxDecoration(
                                  color:
                                      palette.secondary.withValues(alpha: 0.12),
                                  borderRadius: BorderRadius.circular(16),
                                ),
                                child: Icon(
                                  Icons.podcasts_rounded,
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
                                    if (slug.isNotEmpty) ...<Widget>[
                                      const SizedBox(height: 4),
                                      Text(
                                        'Code: $slug',
                                        style: Theme.of(context)
                                            .textTheme
                                            .bodySmall,
                                      ),
                                    ],
                                  ],
                                ),
                              ),
                              const SizedBox(width: 12),
                              FilledButton(
                                onPressed: () => _joinPeer(peer),
                                child: const Text('Join'),
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
          const SizedBox(height: 16),
          AppPanel(
            accentColor: palette.primary,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Row(
                  children: <Widget>[
                    Expanded(
                      child: Text(
                        'QR fallback',
                        style: Theme.of(context).textTheme.titleLarge,
                      ),
                    ),
                    AppBadge(
                      label: _scannerOpen ? 'Scanner on' : 'Scanner off',
                      icon: _scannerOpen
                          ? Icons.qr_code_2_rounded
                          : Icons.qr_code_scanner_rounded,
                      color: palette.primary,
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                SizedBox(
                  width: double.infinity,
                  child: OutlinedButton.icon(
                    onPressed: () {
                      setState(() {
                        _scannerOpen = !_scannerOpen;
                      });
                    },
                    icon: Icon(
                      _scannerOpen
                          ? Icons.visibility_off_rounded
                          : Icons.qr_code_scanner_rounded,
                    ),
                    label: Text(_scannerOpen ? 'Hide scanner' : 'Open scanner'),
                  ),
                ),
                if (_scannerOpen) ...<Widget>[
                  const SizedBox(height: 16),
                  ClipRRect(
                    borderRadius: BorderRadius.circular(26),
                    child: SizedBox(
                      height: 280,
                      child: MobileScanner(
                        onDetect: (BarcodeCapture capture) {
                          final String? raw =
                              capture.barcodes.firstOrNull?.rawValue;
                          if (raw != null && raw.trim().isNotEmpty) {
                            _handleQrDetected(raw);
                          }
                        },
                      ),
                    ),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}
