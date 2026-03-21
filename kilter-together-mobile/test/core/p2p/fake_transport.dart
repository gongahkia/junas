import 'dart:async';
import 'package:kilter_together_mobile/core/p2p/p2p_message_types.dart';
import 'package:kilter_together_mobile/core/p2p/p2p_transport.dart';

class FakeTransport implements P2pTransport {
  final StreamController<P2pMessage> messageController = StreamController<P2pMessage>.broadcast();
  final StreamController<P2pPeer> discoveredController = StreamController<P2pPeer>.broadcast();
  final StreamController<P2pConnectionChange> connectionController = StreamController<P2pConnectionChange>.broadcast();
  final Map<String, P2pPeer> peers = <String, P2pPeer>{};
  final List<P2pMessage> sentMessages = <P2pMessage>[];
  final List<P2pMessage> broadcastMessages = <P2pMessage>[];
  bool advertising = false;
  bool discovering = false;
  String? advertisingDisplayName;
  String? advertisingServiceId;
  bool shouldFailSend = false;

  @override
  Stream<P2pMessage> get messages => messageController.stream;
  @override
  Stream<P2pPeer> get discoveredPeers => discoveredController.stream;
  @override
  Stream<P2pConnectionChange> get connectionChanges => connectionController.stream;
  @override
  List<P2pPeer> get connectedPeers => peers.values.toList(growable: false);

  @override
  Future<void> startAdvertising({required String displayName, required String serviceId}) async {
    advertising = true;
    advertisingDisplayName = displayName;
    advertisingServiceId = serviceId;
  }
  @override
  Future<void> stopAdvertising() async { advertising = false; }
  @override
  Future<void> startDiscovery({required String serviceId}) async { discovering = true; }
  @override
  Future<void> stopDiscovery() async { discovering = false; }
  @override
  Future<void> connectToPeer(P2pPeer peer) async { peers[peer.id] = peer; }
  @override
  Future<void> disconnectFromPeer(String peerId) async { peers.remove(peerId); }
  @override
  Future<void> disconnectAll() async { peers.clear(); }
  @override
  Future<void> send(String peerId, P2pMessage message) async {
    if (shouldFailSend) throw Exception('send failed');
    sentMessages.add(message);
  }
  @override
  Future<void> broadcast(P2pMessage message) async {
    if (shouldFailSend) throw Exception('broadcast failed');
    broadcastMessages.add(message);
  }
  @override
  Future<void> dispose() async {
    await messageController.close();
    await discoveredController.close();
    await connectionController.close();
  }

  void simulateMessage(P2pMessage message) { messageController.add(message); }
  void simulateConnection(P2pPeer peer) {
    peers[peer.id] = peer;
    connectionController.add(P2pConnectionChange(peer: peer, event: P2pConnectionEvent.connected));
  }
  void simulateDisconnection(P2pPeer peer) {
    peers.remove(peer.id);
    connectionController.add(P2pConnectionChange(peer: peer, event: P2pConnectionEvent.disconnected));
  }
}
