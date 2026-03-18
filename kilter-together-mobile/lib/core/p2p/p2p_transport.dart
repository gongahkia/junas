import 'dart:async';
import 'p2p_message_types.dart';

enum P2pRole { host, guest }

class P2pPeer {
  const P2pPeer({
    required this.id,
    required this.displayName,
  });
  final String id;
  final String displayName;
}

enum P2pConnectionEvent { connected, disconnected }

class P2pConnectionChange {
  const P2pConnectionChange({
    required this.peer,
    required this.event,
  });
  final P2pPeer peer;
  final P2pConnectionEvent event;
}

abstract class P2pTransport {
  Future<void> startAdvertising({
    required String displayName,
    required String serviceId,
  });
  Future<void> stopAdvertising();
  Future<void> startDiscovery({
    required String serviceId,
  });
  Future<void> stopDiscovery();
  Future<void> connectToPeer(P2pPeer peer);
  Future<void> disconnectFromPeer(String peerId);
  Future<void> disconnectAll();
  Future<void> send(String peerId, P2pMessage message);
  Future<void> broadcast(P2pMessage message);
  Stream<P2pMessage> get messages;
  Stream<P2pPeer> get discoveredPeers;
  Stream<P2pConnectionChange> get connectionChanges;
  List<P2pPeer> get connectedPeers;
  Future<void> dispose();
}
