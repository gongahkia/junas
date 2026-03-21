import 'dart:async';
import 'package:flutter_test/flutter_test.dart';
import 'package:kilter_together_mobile/core/models/provider_models.dart';
import 'package:kilter_together_mobile/core/models/room_models.dart';
import 'package:kilter_together_mobile/core/p2p/guest_room_service.dart';
import 'package:kilter_together_mobile/core/p2p/host_room_service.dart';
import 'package:kilter_together_mobile/core/p2p/p2p_message_types.dart';
import 'package:kilter_together_mobile/core/p2p/p2p_transport.dart';
import 'fake_transport.dart';

ProviderClimb _testClimb(String id) => ProviderClimb(
  id: id, externalId: id, providerId: 'kilter', surfaceId: 'board-1',
  name: 'Climb $id',
);

void main() {
  group('P2pMessage', () {
    test('encode/decode all message types', () {
      for (final P2pMessageType type in P2pMessageType.values) {
        final P2pMessage msg = P2pMessage(
          type: type,
          payload: const <String, dynamic>{'key': 'value'},
          senderId: 'test',
        );
        final P2pMessage? decoded = P2pMessage.decode(msg.encode());
        expect(decoded, isNotNull, reason: 'Failed to decode $type');
        expect(decoded!.type, type);
        expect(decoded.payload['key'], 'value');
        expect(decoded.senderId, 'test');
      }
    });

    test('decode preserves nested payload', () {
      final P2pMessage msg = P2pMessage(
        type: P2pMessageType.queueAdd,
        payload: <String, dynamic>{
          'climb': <String, dynamic>{'id': 'c1', 'name': 'Test Climb'},
        },
      );
      final P2pMessage? decoded = P2pMessage.decode(msg.encode());
      expect(decoded, isNotNull);
      final Map<String, dynamic> climb = decoded!.payload['climb'] as Map<String, dynamic>;
      expect(climb['id'], 'c1');
    });

    test('decode empty bytes returns null', () {
      expect(P2pMessage.decode(const <int>[]), isNull);
    });

    test('decode garbage returns null', () {
      expect(P2pMessage.decode(<int>[255, 254, 253, 252]), isNull);
    });

    test('decode unknown type returns null', () {
      final String tampered = '{"type":"nonExistentType","payload":{}}';
      expect(P2pMessage.decode(tampered.codeUnits), isNull);
    });
  });

  group('HostRoomService', () {
    late HostRoomService service;

    setUp(() {
      service = HostRoomService(
        state: HostRoomState(slug: 'test-slug', providerId: 'kilter', roomName: 'Test Room'),
      );
    });

    test('add participant assigns sequential ids', () {
      final int id1 = service.addParticipant(displayName: 'Alice', role: 'host');
      final int id2 = service.addParticipant(displayName: 'Bob', role: 'participant');
      expect(id1, 1);
      expect(id2, 2);
      expect(service.state.participants.length, 2);
    });

    test('reject duplicate display name', () {
      service.addParticipant(displayName: 'Alice', role: 'host');
      expect(service.addParticipant(displayName: 'Alice', role: 'participant'), -1);
      expect(service.state.participants.length, 1);
    });

    test('remove participant clears votes', () {
      final int id = service.addParticipant(displayName: 'Alice', role: 'host');
      service.toggleVote(id, 'climb1');
      service.removeParticipant(id);
      expect(service.state.participants.isEmpty, true);
      expect(service.state.participantVotes.containsKey(id), false);
    });

    test('toggle vote on and off', () {
      final int id = service.addParticipant(displayName: 'Alice', role: 'host');
      service.toggleVote(id, 'climb1');
      expect(service.state.voteCounts['climb1'], 1);
      service.toggleVote(id, 'climb1');
      expect(service.state.voteCounts.containsKey('climb1'), false);
    });

    test('toggle vote disabled when fistBumps off', () {
      service.state.fistBumpsEnabled = false;
      final int id = service.addParticipant(displayName: 'Alice', role: 'host');
      expect(service.toggleVote(id, 'climb1'), false);
    });

    test('multiple participants vote independently', () {
      final int id1 = service.addParticipant(displayName: 'Alice', role: 'host');
      final int id2 = service.addParticipant(displayName: 'Bob', role: 'participant');
      service.toggleVote(id1, 'climb1');
      service.toggleVote(id2, 'climb1');
      expect(service.state.voteCounts['climb1'], 2);
      service.toggleVote(id1, 'climb1');
      expect(service.state.voteCounts['climb1'], 1);
    });

    test('clear votes resets all', () {
      final int id = service.addParticipant(displayName: 'Alice', role: 'host');
      service.toggleVote(id, 'climb1');
      service.toggleVote(id, 'climb2');
      service.clearVotes();
      expect(service.state.voteCounts.isEmpty, true);
      expect(service.state.participantVotes.isEmpty, true);
    });

    test('add queue entry prevents duplicates', () {
      expect(service.addQueueEntry(climbId: 'c1', addedBy: 'Alice', climb: _testClimb('c1')), true);
      expect(service.addQueueEntry(climbId: 'c1', addedBy: 'Bob', climb: _testClimb('c1')), false);
      expect(service.state.queue.length, 1);
    });

    test('delete queue entry reindexes positions', () {
      service.addQueueEntry(climbId: 'c1', addedBy: 'A', climb: _testClimb('c1'));
      service.addQueueEntry(climbId: 'c2', addedBy: 'A', climb: _testClimb('c2'));
      service.addQueueEntry(climbId: 'c3', addedBy: 'A', climb: _testClimb('c3'));
      service.deleteQueueEntry(service.state.queue[0].id);
      expect(service.state.queue.length, 2);
      expect(service.state.queue[0].position, 0);
      expect(service.state.queue[1].position, 1);
    });

    test('reorder queue with invalid id fails', () {
      service.addQueueEntry(climbId: 'c1', addedBy: 'A', climb: _testClimb('c1'));
      expect(service.reorderQueue(<int>[999]), false);
    });

    test('reorder queue succeeds', () {
      service.addQueueEntry(climbId: 'c1', addedBy: 'A', climb: _testClimb('c1'));
      service.addQueueEntry(climbId: 'c2', addedBy: 'A', climb: _testClimb('c2'));
      final int id1 = service.state.queue[0].id;
      final int id2 = service.state.queue[1].id;
      expect(service.reorderQueue(<int>[id2, id1]), true);
      expect(service.state.queue[0].climb.id, 'c2');
      expect(service.state.queue[1].climb.id, 'c1');
    });

    test('add and delete finalist', () {
      service.addFinalist(climbId: 'c1', addedBy: 'A', climb: _testClimb('c1'));
      expect(service.state.finalists.length, 1);
      service.deleteFinalist(service.state.finalists[0].id);
      expect(service.state.finalists.isEmpty, true);
    });

    test('promote climb moves from queue to current', () {
      service.addQueueEntry(climbId: 'c1', addedBy: 'A', climb: _testClimb('c1'));
      service.promoteClimb('c1', 'current');
      expect(service.state.currentClimb?.id, 'c1');
      expect(service.state.queue.isEmpty, true);
    });

    test('update participant role', () {
      final int id = service.addParticipant(displayName: 'Alice', role: 'participant');
      service.updateParticipantRole(id, 'co_host');
      expect(service.state.participants[0].role, 'co_host');
    });

    test('set participant online/offline', () {
      final int id = service.addParticipant(displayName: 'Alice', role: 'host');
      service.setParticipantOnline(id, false);
      expect(service.state.participants[0].isOnline, false);
      service.setParticipantOnline(id, true);
      expect(service.state.participants[0].isOnline, true);
    });

    test('snapshot permissions for host vs participant', () {
      final int hostId = service.addParticipant(displayName: 'Host', role: 'host');
      final int guestId = service.addParticipant(displayName: 'Guest', role: 'participant');
      final RoomSnapshot hostSnap = service.toSnapshot(forParticipantId: hostId);
      final RoomSnapshot guestSnap = service.toSnapshot(forParticipantId: guestId);
      expect(hostSnap.canManage, true);
      expect(hostSnap.permissions.closeRoom, true);
      expect(guestSnap.canManage, false);
      expect(guestSnap.permissions.closeRoom, false);
      expect(guestSnap.permissions.manageQueue, true);
    });

    test('snapshot my_votes scoped to participant', () {
      final int id1 = service.addParticipant(displayName: 'Alice', role: 'host');
      final int id2 = service.addParticipant(displayName: 'Bob', role: 'participant');
      service.toggleVote(id1, 'climb1');
      service.toggleVote(id2, 'climb2');
      final RoomSnapshot snap1 = service.toSnapshot(forParticipantId: id1);
      final RoomSnapshot snap2 = service.toSnapshot(forParticipantId: id2);
      expect(snap1.myVotes, contains('climb1'));
      expect(snap1.myVotes, isNot(contains('climb2')));
      expect(snap2.myVotes, contains('climb2'));
    });

    test('update room name and settings', () {
      service.updateRoomName('New Name');
      expect(service.state.roomName, 'New Name');
      service.setFistBumpsEnabled(false);
      expect(service.state.fistBumpsEnabled, false);
    });

    test('close room sets status', () {
      service.closeRoom();
      expect(service.state.status, 'closed');
    });

    test('version bumps on each mutation', () {
      final int v0 = service.state.version;
      service.addParticipant(displayName: 'Alice', role: 'host');
      expect(service.state.version, v0 + 1);
      service.updateRoomName('x');
      expect(service.state.version, v0 + 2);
    });

    test('pick random from empty pool returns null', () {
      expect(service.pickRandom('queue'), isNull);
      expect(service.pickRandom('finalists'), isNull);
    });

    test('pick random from queue returns valid climb', () {
      service.addQueueEntry(climbId: 'c1', addedBy: 'A', climb: _testClimb('c1'));
      expect(service.pickRandom('queue'), isNotNull);
      expect(service.pickRandom('queue')!.id, 'c1');
    });

    test('update queue entry status', () {
      service.addQueueEntry(climbId: 'c1', addedBy: 'A', climb: _testClimb('c1'));
      final int entryId = service.state.queue[0].id;
      service.updateQueueEntryStatus(entryId, 'current');
      expect(service.state.queue[0].status, 'current');
    });

    test('finalist prevents duplicates', () {
      expect(service.addFinalist(climbId: 'c1', addedBy: 'A', climb: _testClimb('c1')), true);
      expect(service.addFinalist(climbId: 'c1', addedBy: 'B', climb: _testClimb('c1')), false);
    });

    test('reorder finalists', () {
      service.addFinalist(climbId: 'c1', addedBy: 'A', climb: _testClimb('c1'));
      service.addFinalist(climbId: 'c2', addedBy: 'A', climb: _testClimb('c2'));
      final int id1 = service.state.finalists[0].id;
      final int id2 = service.state.finalists[1].id;
      expect(service.reorderFinalists(<int>[id2, id1]), true);
      expect(service.state.finalists[0].climb.id, 'c2');
    });
  });

  group('GuestRoomService', () {
    late FakeTransport transport;
    late GuestRoomService service;

    setUp(() {
      transport = FakeTransport();
      service = GuestRoomService(transport: transport, hostPeerId: 'host-1');
    });

    tearDown(() async { await transport.dispose(); });

    test('sendJoinRequest sends correct message', () {
      service.sendJoinRequest('Alice');
      expect(transport.sentMessages.length, 1);
      expect(transport.sentMessages[0].type, P2pMessageType.joinRequest);
      expect(transport.sentMessages[0].payload['display_name'], 'Alice');
    });

    test('toggleVote sends message', () {
      service.toggleVote('climb1');
      expect(transport.sentMessages.last.type, P2pMessageType.voteToggle);
    });

    test('addQueueEntry sends climb', () {
      service.addQueueEntry(_testClimb('c1'));
      expect(transport.sentMessages.last.type, P2pMessageType.queueAdd);
    });

    test('deleteQueueEntry sends entry id', () {
      service.deleteQueueEntry(42);
      expect(transport.sentMessages.last.payload['entry_id'], 42);
    });

    test('reorderQueue sends entry ids', () {
      service.reorderQueue(<int>[3, 1, 2]);
      expect(transport.sentMessages.last.payload['entry_ids'], <int>[3, 1, 2]);
    });

    test('addFinalist sends climb', () {
      service.addFinalist(_testClimb('c1'));
      expect(transport.sentMessages.last.type, P2pMessageType.finalistAdd);
    });

    test('deleteFinalist sends entry id', () {
      service.deleteFinalist(5);
      expect(transport.sentMessages.last.type, P2pMessageType.finalistDelete);
    });

    test('reorderFinalists sends entry ids', () {
      service.reorderFinalists(<int>[2, 1]);
      expect(transport.sentMessages.last.type, P2pMessageType.finalistReorder);
    });

    test('updateMyStatus sends status', () {
      service.updateMyStatus('ready');
      expect(transport.sentMessages.last.payload['status'], 'ready');
    });

    test('promoteClimb sends climb id and status', () {
      service.promoteClimb('c1', 'current');
      expect(transport.sentMessages.last.payload['climb_id'], 'c1');
      expect(transport.sentMessages.last.payload['status'], 'current');
    });

    test('clearVotes sends message', () {
      service.clearVotes();
      expect(transport.sentMessages.last.type, P2pMessageType.clearVotes);
    });

    test('updateRoomName sends name', () {
      service.updateRoomName('New Room');
      expect(transport.sentMessages.last.payload['room_name'], 'New Room');
    });

    test('setFistBumpsEnabled sends flag', () {
      service.setFistBumpsEnabled(false);
      expect(transport.sentMessages.last.payload['enabled'], false);
    });

    test('closeRoom sends message', () {
      service.closeRoom();
      expect(transport.sentMessages.last.type, P2pMessageType.closeRoom);
    });

    test('leaveRoom sends message', () {
      service.leaveRoom();
      expect(transport.sentMessages.last.type, P2pMessageType.leaveRoom);
    });

    test('queryCatalog sends query payload', () {
      service.queryCatalog(<String, dynamic>{'board_id': 'b1', 'page': 1});
      expect(transport.sentMessages.last.type, P2pMessageType.catalogQuery);
      expect(transport.sentMessages.last.payload['board_id'], 'b1');
    });

    test('onSendError fires on failure', () async {
      transport.shouldFailSend = true;
      Object? error;
      service.onSendError = (Object e) { error = e; };
      service.toggleVote('c1');
      await Future<void>.delayed(const Duration(milliseconds: 50));
      expect(error, isNotNull);
    });
  });

  group('RoomSnapshot.fromJson', () {
    test('parses minimal json', () {
      final RoomSnapshot snap = RoomSnapshot.fromJson(const <String, dynamic>{
        'slug': 's1', 'status': 'open', 'provider_id': 'kilter', 'version': 3,
      });
      expect(snap.slug, 's1');
      expect(snap.version, 3);
      expect(snap.participants.isEmpty, true);
    });

    test('parses full json', () {
      final RoomSnapshot snap = RoomSnapshot.fromJson(<String, dynamic>{
        'slug': 's1', 'status': 'open', 'provider_id': 'kilter', 'version': 1,
        'fist_bumps_enabled': true, 'can_manage': true,
        'participants': <Map<String, dynamic>>[
          <String, dynamic>{'id': 1, 'display_name': 'Alice', 'role': 'host', 'status': 'ready', 'is_online': true},
        ],
        'queue': <Map<String, dynamic>>[
          <String, dynamic>{
            'id': 1, 'status': 'queued', 'position': 0, 'added_by': 'Alice',
            'climb': <String, dynamic>{'id': 'c1', 'name': 'Test'},
          },
        ],
        'finalists': <dynamic>[],
        'vote_counts': <String, dynamic>{'c1': 2},
        'my_votes': <String>['c1'],
        'permissions': <String, dynamic>{'close_room': true, 'manage_queue': true},
      });
      expect(snap.participants.length, 1);
      expect(snap.queue.length, 1);
      expect(snap.voteCounts['c1'], 2);
      expect(snap.permissions.closeRoom, true);
    });
  });

  group('FakeTransport', () {
    late FakeTransport transport;
    setUp(() { transport = FakeTransport(); });
    tearDown(() async { await transport.dispose(); });

    test('simulateMessage delivers to stream', () async {
      final List<P2pMessage> received = <P2pMessage>[];
      transport.messages.listen(received.add);
      transport.simulateMessage(const P2pMessage(
        type: P2pMessageType.joinRequest, payload: <String, dynamic>{}, senderId: 'p1',
      ));
      await Future<void>.delayed(const Duration(milliseconds: 10));
      expect(received.length, 1);
    });

    test('simulateConnection and disconnection', () async {
      final List<P2pConnectionChange> changes = <P2pConnectionChange>[];
      transport.connectionChanges.listen(changes.add);
      const P2pPeer peer = P2pPeer(id: 'p1', displayName: 'Alice');
      transport.simulateConnection(peer);
      await Future<void>.delayed(const Duration(milliseconds: 10));
      expect(changes.length, 1);
      expect(changes[0].event, P2pConnectionEvent.connected);
      transport.simulateDisconnection(peer);
      await Future<void>.delayed(const Duration(milliseconds: 10));
      expect(changes.length, 2);
      expect(changes[1].event, P2pConnectionEvent.disconnected);
    });

    test('send records messages', () async {
      await transport.send('p1', const P2pMessage(
        type: P2pMessageType.voteToggle, payload: <String, dynamic>{},
      ));
      expect(transport.sentMessages.length, 1);
    });

    test('send throws when shouldFailSend', () {
      transport.shouldFailSend = true;
      expect(
        () => transport.send('p1', const P2pMessage(
          type: P2pMessageType.voteToggle, payload: <String, dynamic>{},
        )),
        throwsException,
      );
    });
  });
}
