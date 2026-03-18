import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../../core/models/app_prefs_models.dart';
import '../../../core/p2p/p2p_provider.dart';
import '../../../core/p2p/p2p_transport.dart';
import '../../../core/presentation/gradient_scaffold.dart';
import '../../../core/storage/app_prefs_controller.dart';

String _providerLabel(String providerId) {
  return switch (providerId) {
    'kilter' => 'Kilter',
    'crux' => 'Crux',
    _ => providerId,
  };
}

String _formatRelativeTime(String raw) {
  final DateTime? parsed = DateTime.tryParse(raw);
  if (parsed == null) return raw;
  final Duration diff = DateTime.now().toUtc().difference(parsed.toUtc());
  if (diff.inMinutes < 1) return 'just now';
  if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
  if (diff.inHours < 24) return '${diff.inHours}h ago';
  if (diff.inDays < 7) return '${diff.inDays}d ago';
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
    if (_scanning) unawaited(_transport?.stopDiscovery() ?? Future<void>.value());
    super.dispose();
  }

  Future<void> _scanNearby() async {
    setState(() { _scanning = true; _nearbyPeers = <P2pPeer>[]; });
    final P2pTransport transport = ref.read(p2pTransportProvider);
    _transport = transport;
    _discoverySub?.cancel();
    _discoverySub = transport.discoveredPeers.listen((P2pPeer peer) {
      if (!mounted) return;
      setState(() {
        if (!_nearbyPeers.any((P2pPeer p) => p.id == peer.id)) {
          _nearbyPeers = <P2pPeer>[..._nearbyPeers, peer];
        }
      });
    });
    try {
      await transport.startDiscovery(serviceId: p2pServiceId);
    } catch (e) {
      if (mounted) setState(() => _scanning = false);
      // silently handle discovery failure
    }
    // auto-stop after 8 seconds
    Future<void>.delayed(const Duration(seconds: 8), () {
      if (!mounted) return;
      unawaited(transport.stopDiscovery());
      _discoverySub?.cancel();
      setState(() => _scanning = false);
    });
  }

  @override
  Widget build(BuildContext context) {
    final AsyncValue<AppPrefs> prefsValue = ref.watch(appPrefsControllerProvider);
    final AppPrefs prefs = prefsValue.valueOrNull ?? AppPrefs.defaults();
    final List<RecentRoom> previewRecentRooms = prefs.recentRooms.take(3).toList(growable: false);
    return GradientScaffold(
      title: 'Session',
      subtitle: 'Host or join a P2P climbing session. No server required.',
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: <Widget>[
        Row(children: <Widget>[
          Expanded(child: FilledButton.icon(
            onPressed: () {
              unawaited(ref.read(appPrefsControllerProvider.notifier).queueGuideBranch('host'));
              context.goNamed('create-room');
            },
            icon: const Icon(Icons.add),
            label: const Text('Host'),
            style: FilledButton.styleFrom(
              shape: const RoundedRectangleBorder(borderRadius: BorderRadius.zero),
              backgroundColor: const Color(0xFF1A1A1A),
            ),
          )),
          const SizedBox(width: 12),
          Expanded(child: OutlinedButton.icon(
            onPressed: () {
              unawaited(ref.read(appPrefsControllerProvider.notifier).queueGuideBranch('guest'));
              context.goNamed('join-room');
            },
            icon: const Icon(Icons.qr_code_scanner_rounded),
            label: const Text('Join'),
            style: OutlinedButton.styleFrom(
              shape: const RoundedRectangleBorder(borderRadius: BorderRadius.zero),
              side: const BorderSide(color: Color(0xFFD4D4D4)),
            ),
          )),
        ]),
        const SizedBox(height: 16),
        // nearby sessions preview
        Container(
          width: double.infinity,
          decoration: BoxDecoration(
            color: const Color(0xFFF5F5F5),
            border: Border.all(color: const Color(0xFFD4D4D4)),
          ),
          padding: const EdgeInsets.all(16),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: <Widget>[
            Row(children: <Widget>[
              Expanded(child: Text('Nearby sessions', style: Theme.of(context).textTheme.titleLarge)),
              TextButton.icon(
                onPressed: _scanning ? null : _scanNearby,
                icon: const Icon(Icons.bluetooth_searching, size: 16),
                label: Text(_scanning ? 'Scanning...' : 'Scan'),
              ),
            ]),
            const SizedBox(height: 8),
            if (_nearbyPeers.isEmpty)
              Text(_scanning
                  ? 'Looking for nearby hosts...'
                  : 'Tap Scan to discover nearby P2P sessions.')
            else
              ...List<Widget>.generate(_nearbyPeers.length, (int i) {
                final P2pPeer peer = _nearbyPeers[i];
                final List<String> parts = peer.displayName.split('|');
                final String roomName = parts.isNotEmpty ? parts.first : peer.displayName;
                return Padding(
                  padding: const EdgeInsets.only(bottom: 6),
                  child: InkWell(
                    onTap: () {
                      unawaited(ref.read(appPrefsControllerProvider.notifier).queueGuideBranch('guest'));
                      context.goNamed('join-room');
                    },
                    child: Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: Colors.white,
                        border: Border.all(color: const Color(0xFFD4D4D4)),
                      ),
                      child: Text(roomName),
                    ),
                  ),
                );
              }),
          ]),
        ),
        const SizedBox(height: 24),
        // recent rooms section
        Text('Recent rooms', style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 12),
        if (!prefs.settings.recentRoomsEnabled)
          Container(
            width: double.infinity,
            decoration: BoxDecoration(
              color: const Color(0xFFF5F5F5),
              border: Border.all(color: const Color(0xFFD4D4D4)),
            ),
            padding: const EdgeInsets.all(20),
            child: const Text('Recent rooms are disabled in settings.'),
          )
        else if (prefs.recentRooms.isEmpty)
          Container(
            width: double.infinity,
            decoration: BoxDecoration(
              color: const Color(0xFFF5F5F5),
              border: Border.all(color: const Color(0xFFD4D4D4)),
            ),
            padding: const EdgeInsets.all(20),
            child: const Text('No recent rooms saved on this device yet.'),
          )
        else
          Column(
            children: previewRecentRooms.map((RecentRoom room) => Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: _RecentRoomTile(room: room),
            )).toList(growable: false),
          ),
      ]),
    );
  }
}

class _RecentRoomTile extends ConsumerWidget {
  const _RecentRoomTile({required this.room});
  final RecentRoom room;
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final String roomLabel = room.roomName ?? 'Room ${room.slug}';
    final String providerLabel = _providerLabel(room.providerId);
    final String surfaceLabel = (room.surfaceName ?? '').trim().isEmpty
        ? 'Surface not chosen yet' : room.surfaceName!;
    final String lastSeen = _formatRelativeTime(room.lastVisitedAt);
    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        border: Border.all(color: const Color(0xFFD4D4D4)),
      ),
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: <Widget>[
          Text(roomLabel, style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 6),
          Text('$providerLabel \u00b7 $surfaceLabel'),
          const SizedBox(height: 4),
          Text('Last seen $lastSeen', style: Theme.of(context).textTheme.bodySmall),
        ]),
      ),
    );
  }
}
