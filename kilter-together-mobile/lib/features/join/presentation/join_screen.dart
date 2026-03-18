import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:mobile_scanner/mobile_scanner.dart';
import '../../../core/deep_links/invite_links.dart';
import '../../../core/models/app_prefs_models.dart';
import '../../../core/p2p/p2p_provider.dart';
import '../../../core/p2p/p2p_transport.dart';
import '../../../core/presentation/gradient_scaffold.dart';
import '../../../core/storage/app_prefs_controller.dart';
import '../../../core/storage/session_repository.dart';

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
  final TextEditingController _displayNameController = TextEditingController(text: 'Guest');
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
      if (!mounted) return;
      if (prefs.savedDisplayName.trim().isNotEmpty) {
        setState(() => _displayNameController.text = prefs.savedDisplayName.trim());
      }
    });
    _startDiscovery();
  }

  @override
  void dispose() {
    _displayNameController.dispose();
    _discoverySub?.cancel();
    unawaited(_transport?.stopDiscovery() ?? Future<void>.value());
    super.dispose();
  }

  Future<void> _startDiscovery() async {
    setState(() { _discovering = true; _discoveredPeers = <P2pPeer>[]; });
    final P2pTransport transport = ref.read(p2pTransportProvider);
    _transport = transport;
    _discoverySub?.cancel();
    _discoverySub = transport.discoveredPeers.listen((P2pPeer peer) {
      if (!mounted) return;
      setState(() {
        if (!_discoveredPeers.any((P2pPeer p) => p.id == peer.id)) {
          _discoveredPeers = <P2pPeer>[..._discoveredPeers, peer];
        }
      });
    });
    try {
      await transport.startDiscovery(serviceId: p2pServiceId);
    } catch (e) {
      if (mounted) setState(() => _inlineError = 'Discovery failed: $e');
    }
  }

  void _joinPeer(P2pPeer peer) {
    final String displayName = _displayNameController.text.trim();
    if (displayName.isEmpty) {
      setState(() => _inlineError = 'Enter a display name.');
      return;
    }
    unawaited(ref.read(appPrefsControllerProvider.notifier).rememberDisplayName(displayName));
    context.goNamed('room', queryParameters: <String, String>{
      'slug': peer.id,
      'role': 'guest',
      'display_name': displayName,
      'host_peer_id': peer.id,
      'host_peer_name': peer.displayName,
    });
  }

  void _handleQrDetected(String raw) {
    final InviteLink? invite = InviteLink.parse(raw);
    if (invite == null || invite.kind != InviteKind.join) {
      setState(() => _inlineError = 'Not a valid room invite QR.');
      return;
    }
    final String slug = invite.slug ?? '';
    if (slug.isEmpty) {
      setState(() => _inlineError = 'QR missing room code.');
      return;
    }
    // find matching peer by slug in display name
    final P2pPeer? match = _discoveredPeers.cast<P2pPeer?>().firstWhere(
      (P2pPeer? p) => p!.displayName.contains(slug),
      orElse: () => null,
    );
    if (match != null) {
      _joinPeer(match);
    } else {
      setState(() {
        _inlineError = 'Scanned room "$slug" — waiting for host to appear nearby.';
        _scannerOpen = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return GradientScaffold(
      title: 'Join a room',
      subtitle: 'Discover nearby P2P sessions or scan the host QR code.',
      child: Card(child: Padding(
        padding: const EdgeInsets.all(22),
        child: Column(children: <Widget>[
          TextField(
            controller: _displayNameController,
            decoration: const InputDecoration(labelText: 'Display name'),
          ),
          const SizedBox(height: 12),
          if (_inlineError != null) ...<Widget>[
            Container(
              width: double.infinity,
              decoration: BoxDecoration(
                color: const Color(0xFFF0F0F0),
                border: Border.all(color: const Color(0xFFD4D4D4)),
              ),
              padding: const EdgeInsets.all(14),
              child: Text(_inlineError!),
            ),
            const SizedBox(height: 12),
          ],
          Row(children: <Widget>[
            Expanded(child: Text(
              'Nearby sessions',
              style: Theme.of(context).textTheme.titleLarge,
            )),
            IconButton(
              onPressed: _startDiscovery,
              icon: const Icon(Icons.refresh),
            ),
          ]),
          const SizedBox(height: 8),
          if (_discoveredPeers.isEmpty)
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: const Color(0xFFF5F5F5),
                border: Border.all(color: const Color(0xFFD4D4D4)),
              ),
              child: Text(_discovering
                  ? 'Searching for nearby sessions...'
                  : 'No nearby sessions found. Ask the host to start advertising.'),
            )
          else
            ...List<Widget>.generate(_discoveredPeers.length, (int i) {
              final P2pPeer peer = _discoveredPeers[i];
              final List<String> parts = peer.displayName.split('|');
              final String roomName = parts.isNotEmpty ? parts.first : peer.displayName;
              final String slug = parts.length > 1 ? parts.last : '';
              return Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Container(
                  decoration: BoxDecoration(
                    color: Colors.white,
                    border: Border.all(color: const Color(0xFFD4D4D4)),
                  ),
                  child: ListTile(
                    title: Text(roomName),
                    subtitle: slug.isNotEmpty ? Text('Code: $slug') : null,
                    trailing: FilledButton(
                      onPressed: () => _joinPeer(peer),
                      child: const Text('Join'),
                    ),
                  ),
                ),
              );
            }),
          const SizedBox(height: 12),
          SizedBox(width: double.infinity, child: OutlinedButton.icon(
            onPressed: () => setState(() => _scannerOpen = !_scannerOpen),
            icon: Icon(_scannerOpen ? Icons.qr_code_2 : Icons.qr_code_scanner),
            label: Text(_scannerOpen ? 'Hide QR scanner' : 'Scan host QR'),
          )),
          if (_scannerOpen) ...<Widget>[
            const SizedBox(height: 12),
            SizedBox(
              height: 260,
              child: ClipRRect(
                child: MobileScanner(
                  onDetect: (BarcodeCapture capture) {
                    final String? raw = capture.barcodes.firstOrNull?.rawValue;
                    if (raw != null && raw.trim().isNotEmpty) _handleQrDetected(raw);
                  },
                ),
              ),
            ),
          ],
        ]),
      )),
    );
  }
}
