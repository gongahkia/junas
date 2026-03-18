import 'dart:async';
import 'package:flutter/services.dart';
import 'p2p_message_types.dart';
import 'p2p_transport.dart';

const MethodChannel _method = MethodChannel('kilter_together/multipeer');
const EventChannel _events = EventChannel('kilter_together/multipeer_events');

class MultipeerTransport implements P2pTransport {
  final StreamController<P2pMessage> _messageController = StreamController<P2pMessage>.broadcast();
  final StreamController<P2pPeer> _discoveredController = StreamController<P2pPeer>.broadcast();
  final StreamController<P2pConnectionChange> _connectionController = StreamController<P2pConnectionChange>.broadcast();
  final Map<String, P2pPeer> _peers = <String, P2pPeer>{};
  StreamSubscription<dynamic>? _eventSub;
  bool _disposed = false;
  bool _listening = false;

  void _ensureListening() {
    if (_listening) return;
    _listening = true;
    _eventSub = _events.receiveBroadcastStream().listen(
      _handleEvent,
      onError: (Object e) { /* channel error — safe to ignore */ },
    );
  }

  @override
  Stream<P2pMessage> get messages => _messageController.stream;
  @override
  Stream<P2pPeer> get discoveredPeers => _discoveredController.stream;
  @override
  Stream<P2pConnectionChange> get connectionChanges => _connectionController.stream;
  @override
  List<P2pPeer> get connectedPeers => _peers.values.toList(growable: false);

  void _handleEvent(dynamic event) {
    if (event is! Map) return;
    final Map<Object?, Object?> raw = event;
    final String type = raw['type'] as String? ?? '';
    switch (type) {
      case 'peerFound':
        final String peerId = raw['peerId'] as String? ?? '';
        final String displayName = raw['displayName'] as String? ?? peerId;
        _discoveredController.add(P2pPeer(id: peerId, displayName: displayName));
      case 'connected':
        final String peerId = raw['peerId'] as String? ?? '';
        final String displayName = raw['displayName'] as String? ?? peerId;
        final P2pPeer peer = P2pPeer(id: peerId, displayName: displayName);
        _peers[peerId] = peer;
        _connectionController.add(P2pConnectionChange(peer: peer, event: P2pConnectionEvent.connected));
      case 'disconnected':
        final String peerId = raw['peerId'] as String? ?? '';
        final P2pPeer? peer = _peers.remove(peerId);
        if (peer != null) {
          _connectionController.add(P2pConnectionChange(peer: peer, event: P2pConnectionEvent.disconnected));
        }
      case 'data':
        final String peerId = raw['peerId'] as String? ?? '';
        final Uint8List? bytes = (raw['data'] as Uint8List?);
        if (bytes == null) return;
        final P2pMessage? msg = P2pMessage.decode(bytes);
        if (msg == null) return;
        _messageController.add(P2pMessage(type: msg.type, payload: msg.payload, senderId: peerId));
      case 'error':
        break; // logged on native side
    }
  }

  @override
  Future<void> startAdvertising({required String displayName, required String serviceId}) async {
    _ensureListening();
    await _method.invokeMethod<void>('startAdvertising', <String, dynamic>{
      'displayName': displayName,
      'serviceId': serviceId,
    });
  }

  @override
  Future<void> stopAdvertising() async {
    await _method.invokeMethod<void>('stopAdvertising');
  }

  @override
  Future<void> startDiscovery({required String serviceId}) async {
    _ensureListening();
    await _method.invokeMethod<void>('startDiscovery', <String, dynamic>{
      'serviceId': serviceId,
    });
  }

  @override
  Future<void> stopDiscovery() async {
    await _method.invokeMethod<void>('stopDiscovery');
  }

  @override
  Future<void> connectToPeer(P2pPeer peer) async {
    await _method.invokeMethod<void>('connectToPeer', <String, dynamic>{
      'peerId': peer.id,
      'displayName': peer.displayName,
    });
  }

  @override
  Future<void> disconnectFromPeer(String peerId) async {
    await _method.invokeMethod<void>('disconnectFromPeer', <String, dynamic>{'peerId': peerId});
    final P2pPeer? peer = _peers.remove(peerId);
    if (peer != null) {
      _connectionController.add(P2pConnectionChange(peer: peer, event: P2pConnectionEvent.disconnected));
    }
  }

  @override
  Future<void> disconnectAll() async {
    await _method.invokeMethod<void>('disconnectAll');
    for (final P2pPeer peer in _peers.values.toList()) {
      _connectionController.add(P2pConnectionChange(peer: peer, event: P2pConnectionEvent.disconnected));
    }
    _peers.clear();
  }

  @override
  Future<void> send(String peerId, P2pMessage message) async {
    final Uint8List bytes = Uint8List.fromList(message.encode());
    await _method.invokeMethod<void>('send', <String, dynamic>{
      'peerId': peerId,
      'data': bytes,
    });
  }

  @override
  Future<void> broadcast(P2pMessage message) async {
    final Uint8List bytes = Uint8List.fromList(message.encode());
    await _method.invokeMethod<void>('broadcast', <String, dynamic>{
      'data': bytes,
    });
  }

  @override
  Future<void> dispose() async {
    if (_disposed) return;
    _disposed = true;
    await _eventSub?.cancel();
    await disconnectAll();
    await stopAdvertising();
    await stopDiscovery();
    await _messageController.close();
    await _discoveredController.close();
    await _connectionController.close();
  }
}
