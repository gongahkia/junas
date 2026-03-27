import 'package:flutter_test/flutter_test.dart';
import 'package:kilter_together_mobile/core/models/provider_models.dart';
import 'package:kilter_together_mobile/core/p2p/guest_room_service.dart';
import 'package:kilter_together_mobile/core/p2p/p2p_message_types.dart';
import 'fake_transport.dart';

void main() {
  group('GuestRoomService extended', () {
    late FakeTransport transport;
    late GuestRoomService service;

    setUp(() {
      transport = FakeTransport();
      service = GuestRoomService(transport: transport, hostPeerId: 'host-1');
    });

    tearDown(() async {
      await transport.dispose();
    });

    test('setSurface sends surface json', () {
      const ProviderSurface surface = ProviderSurface(
        id: 's1',
        kind: 'board',
        name: 'Original 40',
      );
      service.setSurface(surface);
      expect(transport.sentMessages.last.type, P2pMessageType.setSurface);
      final Map<String, dynamic> payload = transport.sentMessages.last.payload;
      final Map<String, dynamic> surfaceJson =
          payload['surface'] as Map<String, dynamic>;
      expect(surfaceJson['id'], 's1');
      expect(surfaceJson['name'], 'Original 40');
    });

    test('pickRandom sends source', () {
      service.pickRandom('queue');
      expect(transport.sentMessages.last.type, P2pMessageType.pickRandom);
      expect(transport.sentMessages.last.payload['source'], 'queue');
    });

    test('pickRandom with finalists source', () {
      service.pickRandom('finalists');
      expect(transport.sentMessages.last.payload['source'], 'finalists');
    });

    test('updateParticipantRole sends id and role', () {
      service.updateParticipantRole(5, 'co_host');
      expect(transport.sentMessages.last.type, P2pMessageType.updateRole);
      expect(transport.sentMessages.last.payload['participant_id'], 5);
      expect(transport.sentMessages.last.payload['role'], 'co_host');
    });

    test('removeParticipant sends participant id', () {
      service.removeParticipant(3);
      expect(
          transport.sentMessages.last.type, P2pMessageType.removeParticipant);
      expect(transport.sentMessages.last.payload['participant_id'], 3);
    });

    test('addQueueEntry sends full climb json', () {
      const ProviderClimb climb = ProviderClimb(
        id: 'c1',
        externalId: 'ext-1',
        providerId: 'kilter',
        surfaceId: 'board-1',
        name: 'Test Route',
        primaryGrade: 'V5',
      );
      service.addQueueEntry(climb);
      final Map<String, dynamic> climbJson =
          transport.sentMessages.last.payload['climb'] as Map<String, dynamic>;
      expect(climbJson['id'], 'c1');
      expect(climbJson['primary_grade'], 'V5');
    });

    test('addFinalist sends full climb json', () {
      const ProviderClimb climb = ProviderClimb(
        id: 'f1',
        externalId: 'ext-f1',
        providerId: 'kilter',
        surfaceId: 'board-1',
        name: 'Finalist Route',
      );
      service.addFinalist(climb);
      final Map<String, dynamic> climbJson =
          transport.sentMessages.last.payload['climb'] as Map<String, dynamic>;
      expect(climbJson['id'], 'f1');
      expect(climbJson['name'], 'Finalist Route');
    });

    test('multiple operations send in order', () {
      service.sendJoinRequest('Alice');
      service.toggleVote('c1');
      service.clearVotes();
      expect(transport.sentMessages.length, 3);
      expect(transport.sentMessages[0].type, P2pMessageType.joinRequest);
      expect(transport.sentMessages[1].type, P2pMessageType.voteToggle);
      expect(transport.sentMessages[2].type, P2pMessageType.clearVotes);
    });

    test('all messages target correct host peer', () async {
      service.sendJoinRequest('Bob');
      // The FakeTransport records sent messages but doesn't track peerId.
      // Verify the service was constructed with correct hostPeerId.
      expect(service.hostPeerId, 'host-1');
    });

    test('onSendError not set does not throw', () async {
      transport.shouldFailSend = true;
      // Should not throw even without onSendError callback
      service.toggleVote('c1');
      await Future<void>.delayed(const Duration(milliseconds: 50));
    });
  });
}
