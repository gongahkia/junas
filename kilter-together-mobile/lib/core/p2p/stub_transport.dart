import 'dart:async';
import 'p2p_message_types.dart';
import 'p2p_transport.dart';

/// fallback transport for platforms where nearby_connections is unavailable (iOS).
/// all methods throw a clear error so the UI can surface it.
class StubTransport implements P2pTransport {
  final StreamController<P2pMessage> _msg =
      StreamController<P2pMessage>.broadcast();
  final StreamController<P2pPeer> _disc = StreamController<P2pPeer>.broadcast();
  final StreamController<P2pConnectionChange> _conn =
      StreamController<P2pConnectionChange>.broadcast();

  @override
  Stream<P2pMessage> get messages => _msg.stream;
  @override
  Stream<P2pPeer> get discoveredPeers => _disc.stream;
  @override
  Stream<P2pConnectionChange> get connectionChanges => _conn.stream;
  @override
  List<P2pPeer> get connectedPeers => const <P2pPeer>[];

  @override
  Future<void> startAdvertising(
      {required String displayName, required String serviceId}) async {
    throw UnsupportedError(
        'P2P advertising is not supported on this platform. nearby_connections requires Android.');
  }

  @override
  Future<void> stopAdvertising() async {}
  @override
  Future<void> startDiscovery({required String serviceId}) async {
    throw UnsupportedError(
        'P2P discovery is not supported on this platform. nearby_connections requires Android.');
  }

  @override
  Future<void> stopDiscovery() async {}
  @override
  Future<void> connectToPeer(P2pPeer peer) async {
    throw UnsupportedError(
        'P2P connections are not supported on this platform.');
  }

  @override
  Future<void> disconnectFromPeer(String peerId) async {}
  @override
  Future<void> disconnectAll() async {}
  @override
  Future<void> send(String peerId, P2pMessage message) async {
    throw UnsupportedError('P2P messaging is not supported on this platform.');
  }

  @override
  Future<void> broadcast(P2pMessage message) async {
    throw UnsupportedError('P2P broadcast is not supported on this platform.');
  }

  @override
  Future<void> dispose() async {
    await _msg.close();
    await _disc.close();
    await _conn.close();
  }
}
