import 'dart:async';
import 'dart:typed_data';
import 'package:nearby_connections/nearby_connections.dart';
import 'p2p_message_types.dart';
import 'p2p_transport.dart';

const Strategy _strategy = Strategy.P2P_STAR;

class NearbyTransport implements P2pTransport {
  NearbyTransport() : _nearby = Nearby();
  final Nearby _nearby;
  final StreamController<P2pMessage> _messageController = StreamController<P2pMessage>.broadcast();
  final StreamController<P2pPeer> _discoveredController = StreamController<P2pPeer>.broadcast();
  final StreamController<P2pConnectionChange> _connectionController = StreamController<P2pConnectionChange>.broadcast();
  final Map<String, P2pPeer> _peers = <String, P2pPeer>{};
  final Map<String, String> _endpointNames = <String, String>{};
  bool _disposed = false;

  @override
  Stream<P2pMessage> get messages => _messageController.stream;
  @override
  Stream<P2pPeer> get discoveredPeers => _discoveredController.stream;
  @override
  Stream<P2pConnectionChange> get connectionChanges => _connectionController.stream;
  @override
  List<P2pPeer> get connectedPeers => _peers.values.toList(growable: false);

  void _onPayloadReceived(String endpointId, Payload payload) {
    if (payload.type != PayloadType.BYTES || payload.bytes == null) return;
    final P2pMessage? message = P2pMessage.decode(payload.bytes!);
    if (message == null) return;
    final P2pMessage tagged = P2pMessage(
      type: message.type,
      payload: message.payload,
      senderId: endpointId,
    );
    _messageController.add(tagged);
  }

  void _onConnectionInitiated(String endpointId, ConnectionInfo info) {
    _endpointNames[endpointId] = info.endpointName;
    _nearby.acceptConnection(
      endpointId,
      onPayLoadRecieved: _onPayloadReceived,
    );
  }

  void _onConnectionResult(String endpointId, Status status) {
    if (status == Status.CONNECTED) {
      final P2pPeer peer = P2pPeer(
        id: endpointId,
        displayName: _endpointNames[endpointId] ?? endpointId,
      );
      _peers[endpointId] = peer;
      _connectionController.add(P2pConnectionChange(
        peer: peer,
        event: P2pConnectionEvent.connected,
      ));
    }
  }

  void _onDisconnected(String endpointId) {
    final P2pPeer? peer = _peers.remove(endpointId);
    _endpointNames.remove(endpointId);
    if (peer != null) {
      _connectionController.add(P2pConnectionChange(
        peer: peer,
        event: P2pConnectionEvent.disconnected,
      ));
    }
  }

  @override
  Future<void> startAdvertising({
    required String displayName,
    required String serviceId,
  }) async {
    await _nearby.startAdvertising(
      displayName,
      _strategy,
      onConnectionInitiated: _onConnectionInitiated,
      onConnectionResult: _onConnectionResult,
      onDisconnected: _onDisconnected,
      serviceId: serviceId,
    );
  }

  @override
  Future<void> stopAdvertising() => _nearby.stopAdvertising();

  @override
  Future<void> startDiscovery({required String serviceId}) async {
    await _nearby.startDiscovery(
      _nearby.toString(), // unused user name for discovery
      _strategy,
      onEndpointFound: (String endpointId, String endpointName, String serviceId) {
        final P2pPeer peer = P2pPeer(id: endpointId, displayName: endpointName);
        _discoveredController.add(peer);
      },
      onEndpointLost: (String? endpointId) {},
      serviceId: serviceId,
    );
  }

  @override
  Future<void> stopDiscovery() => _nearby.stopDiscovery();

  @override
  Future<void> connectToPeer(P2pPeer peer) async {
    await _nearby.requestConnection(
      peer.displayName,
      peer.id,
      onConnectionInitiated: _onConnectionInitiated,
      onConnectionResult: _onConnectionResult,
      onDisconnected: _onDisconnected,
    );
  }

  @override
  Future<void> disconnectFromPeer(String peerId) async {
    _nearby.disconnectFromEndpoint(peerId);
    _onDisconnected(peerId);
  }

  @override
  Future<void> disconnectAll() async {
    _nearby.stopAllEndpoints();
    for (final String id in _peers.keys.toList()) {
      _onDisconnected(id);
    }
  }

  @override
  Future<void> send(String peerId, P2pMessage message) async {
    await _nearby.sendBytesPayload(peerId, Uint8List.fromList(message.encode()));
  }

  @override
  Future<void> broadcast(P2pMessage message) async {
    final Uint8List bytes = Uint8List.fromList(message.encode());
    for (final String peerId in _peers.keys) {
      await _nearby.sendBytesPayload(peerId, bytes);
    }
  }

  @override
  Future<void> dispose() async {
    if (_disposed) return;
    _disposed = true;
    await disconnectAll();
    await stopAdvertising();
    await stopDiscovery();
    await _messageController.close();
    await _discoveredController.close();
    await _connectionController.close();
  }
}
