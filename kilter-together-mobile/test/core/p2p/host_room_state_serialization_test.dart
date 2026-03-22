import 'package:flutter_test/flutter_test.dart';
import 'package:kilter_together_mobile/core/models/provider_models.dart';
import 'package:kilter_together_mobile/core/models/room_models.dart';
import 'package:kilter_together_mobile/core/p2p/host_room_service.dart';

ProviderClimb _testClimb(String id) => ProviderClimb(
  id: id, externalId: id, providerId: 'kilter', surfaceId: 'board-1',
  name: 'Climb $id',
);

void main() {
  group('HostRoomState serialization', () {
    test('empty state roundtrip', () {
      final HostRoomState original = HostRoomState(
        slug: 'test-slug',
        providerId: 'kilter',
        roomName: 'Test Room',
      );
      final String json = original.serialize();
      final HostRoomState restored = HostRoomState.deserialize(json);
      expect(restored.slug, 'test-slug');
      expect(restored.providerId, 'kilter');
      expect(restored.roomName, 'Test Room');
      expect(restored.status, 'open');
      expect(restored.fistBumpsEnabled, true);
      expect(restored.version, 1);
      expect(restored.participants.isEmpty, true);
      expect(restored.queue.isEmpty, true);
      expect(restored.finalists.isEmpty, true);
    });

    test('roundtrip preserves participants', () {
      final HostRoomService service = HostRoomService(
        state: HostRoomState(slug: 'test', providerId: 'kilter'),
      );
      service.addParticipant(displayName: 'Alice', role: 'host');
      service.addParticipant(displayName: 'Bob', role: 'participant');

      final String json = service.state.serialize();
      final HostRoomState restored = HostRoomState.deserialize(json);
      expect(restored.participants.length, 2);
      expect(restored.participants[0].displayName, 'Alice');
      expect(restored.participants[0].role, 'host');
      expect(restored.participants[1].displayName, 'Bob');
      expect(restored.participants[1].isOnline, true);
    });

    test('roundtrip preserves queue with positions', () {
      final HostRoomService service = HostRoomService(
        state: HostRoomState(slug: 'test', providerId: 'kilter'),
      );
      service.addQueueEntry(climbId: 'c1', addedBy: 'Alice', climb: _testClimb('c1'));
      service.addQueueEntry(climbId: 'c2', addedBy: 'Bob', climb: _testClimb('c2'));

      final String json = service.state.serialize();
      final HostRoomState restored = HostRoomState.deserialize(json);
      expect(restored.queue.length, 2);
      expect(restored.queue[0].climb.id, 'c1');
      expect(restored.queue[0].position, 0);
      expect(restored.queue[1].climb.id, 'c2');
      expect(restored.queue[1].position, 1);
    });

    test('roundtrip preserves finalists', () {
      final HostRoomService service = HostRoomService(
        state: HostRoomState(slug: 'test', providerId: 'kilter'),
      );
      service.addFinalist(climbId: 'c1', addedBy: 'Alice', climb: _testClimb('c1'));

      final String json = service.state.serialize();
      final HostRoomState restored = HostRoomState.deserialize(json);
      expect(restored.finalists.length, 1);
      expect(restored.finalists[0].climb.id, 'c1');
      expect(restored.finalists[0].addedBy, 'Alice');
    });

    test('roundtrip preserves votes', () {
      final HostRoomService service = HostRoomService(
        state: HostRoomState(slug: 'test', providerId: 'kilter'),
      );
      final int id1 = service.addParticipant(displayName: 'Alice', role: 'host');
      final int id2 = service.addParticipant(displayName: 'Bob', role: 'participant');
      service.toggleVote(id1, 'c1');
      service.toggleVote(id2, 'c1');
      service.toggleVote(id2, 'c2');

      final String json = service.state.serialize();
      final HostRoomState restored = HostRoomState.deserialize(json);
      expect(restored.voteCounts['c1'], 2);
      expect(restored.voteCounts['c2'], 1);
      expect(restored.participantVotes[id1], contains('c1'));
      expect(restored.participantVotes[id2], contains('c2'));
    });

    test('roundtrip preserves next ID counters', () {
      final HostRoomService service = HostRoomService(
        state: HostRoomState(slug: 'test', providerId: 'kilter'),
      );
      service.addParticipant(displayName: 'Alice', role: 'host');
      service.addParticipant(displayName: 'Bob', role: 'participant');
      service.addQueueEntry(climbId: 'c1', addedBy: 'A', climb: _testClimb('c1'));
      service.addFinalist(climbId: 'f1', addedBy: 'A', climb: _testClimb('f1'));

      final String json = service.state.serialize();
      final HostRoomState restored = HostRoomState.deserialize(json);
      // Next IDs should continue from where they left off
      final HostRoomService restoredService = HostRoomService(state: restored);
      final int nextId = restoredService.addParticipant(displayName: 'Charlie', role: 'participant');
      expect(nextId, 3); // Alice=1, Bob=2, Charlie=3
    });

    test('roundtrip preserves closed status', () {
      final HostRoomService service = HostRoomService(
        state: HostRoomState(slug: 'test', providerId: 'kilter'),
      );
      service.closeRoom();

      final String json = service.state.serialize();
      final HostRoomState restored = HostRoomState.deserialize(json);
      expect(restored.status, 'closed');
    });

    test('roundtrip preserves surface', () {
      final HostRoomService service = HostRoomService(
        state: HostRoomState(slug: 'test', providerId: 'kilter'),
      );
      service.setSurface(const ProviderSurface(
        id: 'board-1', kind: 'board', name: 'Original 40',
        meta: <String, String>{'angle': '40'},
      ));

      final String json = service.state.serialize();
      final HostRoomState restored = HostRoomState.deserialize(json);
      expect(restored.surface, isNotNull);
      expect(restored.surface!.name, 'Original 40');
      expect(restored.surface!.meta['angle'], '40');
    });

    test('roundtrip preserves current climb', () {
      final HostRoomService service = HostRoomService(
        state: HostRoomState(slug: 'test', providerId: 'kilter'),
      );
      service.addQueueEntry(climbId: 'c1', addedBy: 'A', climb: _testClimb('c1'));
      service.promoteClimb('c1', 'current');

      final String json = service.state.serialize();
      final HostRoomState restored = HostRoomState.deserialize(json);
      expect(restored.currentClimb, isNotNull);
      expect(restored.currentClimb!.id, 'c1');
    });

    test('roundtrip with fistBumps disabled', () {
      final HostRoomService service = HostRoomService(
        state: HostRoomState(slug: 'test', providerId: 'kilter'),
      );
      service.setFistBumpsEnabled(false);

      final String json = service.state.serialize();
      final HostRoomState restored = HostRoomState.deserialize(json);
      expect(restored.fistBumpsEnabled, false);
    });
  });
}
