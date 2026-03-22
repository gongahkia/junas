import 'package:flutter_test/flutter_test.dart';
import 'package:kilter_together_mobile/core/p2p/p2p_message_types.dart';
import 'package:kilter_together_mobile/core/p2p/p2p_transport.dart';
import 'package:kilter_together_mobile/core/p2p/stub_transport.dart';

void main() {
  group('StubTransport', () {
    late StubTransport transport;

    setUp(() {
      transport = StubTransport();
    });

    tearDown(() async {
      await transport.dispose();
    });

    test('startAdvertising throws UnsupportedError', () {
      expect(
        () => transport.startAdvertising(displayName: 'Test', serviceId: 'test'),
        throwsA(isA<UnsupportedError>()),
      );
    });

    test('startDiscovery throws UnsupportedError', () {
      expect(
        () => transport.startDiscovery(serviceId: 'test'),
        throwsA(isA<UnsupportedError>()),
      );
    });

    test('connectToPeer throws UnsupportedError', () {
      expect(
        () => transport.connectToPeer(const P2pPeer(id: 'p1', displayName: 'Alice')),
        throwsA(isA<UnsupportedError>()),
      );
    });

    test('send throws UnsupportedError', () {
      expect(
        () => transport.send('p1', const P2pMessage(
          type: P2pMessageType.joinRequest, payload: <String, dynamic>{},
        )),
        throwsA(isA<UnsupportedError>()),
      );
    });

    test('broadcast throws UnsupportedError', () {
      expect(
        () => transport.broadcast(const P2pMessage(
          type: P2pMessageType.joinRequest, payload: <String, dynamic>{},
        )),
        throwsA(isA<UnsupportedError>()),
      );
    });

    test('stopAdvertising does not throw', () async {
      await transport.stopAdvertising();
    });

    test('stopDiscovery does not throw', () async {
      await transport.stopDiscovery();
    });

    test('disconnectFromPeer does not throw', () async {
      await transport.disconnectFromPeer('p1');
    });

    test('disconnectAll does not throw', () async {
      await transport.disconnectAll();
    });

    test('connectedPeers is empty', () {
      expect(transport.connectedPeers, isEmpty);
    });

    test('streams are available before dispose', () {
      expect(transport.messages, isNotNull);
      expect(transport.discoveredPeers, isNotNull);
      expect(transport.connectionChanges, isNotNull);
    });
  });
}
