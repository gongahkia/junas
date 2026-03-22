import 'package:flutter_test/flutter_test.dart';
import 'package:kilter_together_mobile/core/models/room_models.dart';

void main() {
  group('Participant.fromJson', () {
    test('parses complete json', () {
      final Participant p = Participant.fromJson(const <String, dynamic>{
        'id': 5,
        'display_name': 'Alice',
        'role': 'host',
        'status': 'ready',
        'is_online': true,
      });
      expect(p.id, 5);
      expect(p.displayName, 'Alice');
      expect(p.role, 'host');
      expect(p.status, 'ready');
      expect(p.isOnline, true);
    });

    test('uses defaults for missing fields', () {
      final Participant p = Participant.fromJson(const <String, dynamic>{});
      expect(p.id, 0);
      expect(p.displayName, '');
      expect(p.role, 'participant');
      expect(p.status, 'watching');
      expect(p.isOnline, false);
    });
  });

  group('RoomPermissions.fromJson', () {
    test('parses all true permissions', () {
      final RoomPermissions perms = RoomPermissions.fromJson(const <String, dynamic>{
        'manage_session': true,
        'manage_surface': true,
        'manage_queue': true,
        'manage_finalists': true,
        'edit_room_settings': true,
        'manage_participants': true,
        'assign_co_hosts': true,
        'close_room': true,
      });
      expect(perms.manageSession, true);
      expect(perms.manageSurface, true);
      expect(perms.manageQueue, true);
      expect(perms.manageFinalists, true);
      expect(perms.editRoomSettings, true);
      expect(perms.manageParticipants, true);
      expect(perms.assignCoHosts, true);
      expect(perms.closeRoom, true);
    });

    test('defaults all to false', () {
      final RoomPermissions perms = RoomPermissions.fromJson(const <String, dynamic>{});
      expect(perms.manageSession, false);
      expect(perms.manageSurface, false);
      expect(perms.closeRoom, false);
    });
  });

  group('QueueEntry.fromJson', () {
    test('parses complete json', () {
      final QueueEntry entry = QueueEntry.fromJson(<String, dynamic>{
        'id': 3,
        'status': 'current',
        'position': 1,
        'added_by': 'Bob',
        'climb': <String, dynamic>{'id': 'c1', 'name': 'Test'},
      });
      expect(entry.id, 3);
      expect(entry.status, 'current');
      expect(entry.position, 1);
      expect(entry.addedBy, 'Bob');
      expect(entry.climb.id, 'c1');
    });

    test('handles missing climb gracefully', () {
      final QueueEntry entry = QueueEntry.fromJson(const <String, dynamic>{});
      expect(entry.id, 0);
      expect(entry.status, 'queued');
      expect(entry.climb.id, '');
    });
  });

  group('FinalistEntry.fromJson', () {
    test('parses complete json', () {
      final FinalistEntry entry = FinalistEntry.fromJson(<String, dynamic>{
        'id': 7,
        'position': 2,
        'added_by': 'Alice',
        'climb': <String, dynamic>{'id': 'c5', 'name': 'Hard Route'},
      });
      expect(entry.id, 7);
      expect(entry.position, 2);
      expect(entry.addedBy, 'Alice');
      expect(entry.climb.id, 'c5');
    });

    test('defaults for empty json', () {
      final FinalistEntry entry = FinalistEntry.fromJson(const <String, dynamic>{});
      expect(entry.id, 0);
      expect(entry.position, 0);
      expect(entry.addedBy, '');
    });
  });

  group('AssistantState.fromJson', () {
    test('parses with suggestion', () {
      final AssistantState state = AssistantState.fromJson(<String, dynamic>{
        'mode': 'auto',
        'message': 'Try this!',
        'suggestion': <String, dynamic>{
          'source': 'queue',
          'ready_count': 3,
          'climb': <String, dynamic>{'id': 'c1', 'name': 'Test'},
        },
      });
      expect(state.mode, 'auto');
      expect(state.message, 'Try this!');
      expect(state.suggestion, isNotNull);
      expect(state.suggestion!.source, 'queue');
      expect(state.suggestion!.readyCount, 3);
    });

    test('defaults to manual mode', () {
      final AssistantState state = AssistantState.fromJson(const <String, dynamic>{});
      expect(state.mode, 'manual');
      expect(state.message, isNull);
      expect(state.suggestion, isNull);
    });
  });

  group('RoomSnapshot.fromJson', () {
    test('handles current_climb and surface', () {
      final RoomSnapshot snap = RoomSnapshot.fromJson(<String, dynamic>{
        'slug': 's1',
        'status': 'open',
        'provider_id': 'kilter',
        'version': 5,
        'room_name': 'My Room',
        'current_climb': <String, dynamic>{
          'id': 'c1',
          'name': 'Boulder Problem',
        },
        'surface': <String, dynamic>{
          'id': 'board-1',
          'kind': 'board',
          'name': 'Original 40',
        },
      });
      expect(snap.roomName, 'My Room');
      expect(snap.currentClimb, isNotNull);
      expect(snap.currentClimb!.id, 'c1');
      expect(snap.surface, isNotNull);
      expect(snap.surface!.name, 'Original 40');
    });

    test('handles connection state', () {
      final RoomSnapshot snap = RoomSnapshot.fromJson(<String, dynamic>{
        'slug': 's1',
        'status': 'open',
        'provider_id': 'kilter',
        'version': 1,
        'connection': <String, dynamic>{
          'connected': true,
          'provider_id': 'kilter',
        },
      });
      expect(snap.connection.connected, true);
    });

    test('fistBumpsEnabled defaults to true', () {
      final RoomSnapshot snap = RoomSnapshot.fromJson(const <String, dynamic>{
        'slug': 's1',
        'status': 'open',
        'provider_id': 'kilter',
        'version': 1,
      });
      expect(snap.fistBumpsEnabled, true);
    });

    test('filters non-map entries in lists', () {
      final RoomSnapshot snap = RoomSnapshot.fromJson(<String, dynamic>{
        'slug': 's1',
        'status': 'open',
        'provider_id': 'kilter',
        'version': 1,
        'participants': <dynamic>[
          <String, dynamic>{'id': 1, 'display_name': 'Alice'},
          'not a map',
          42,
        ],
      });
      expect(snap.participants.length, 1);
    });

    test('display_name passed through', () {
      final RoomSnapshot snap = RoomSnapshot.fromJson(const <String, dynamic>{
        'slug': 's1',
        'status': 'open',
        'provider_id': 'kilter',
        'version': 1,
        'display_name': 'Bob',
      });
      expect(snap.displayName, 'Bob');
    });
  });

  group('RoomCatalogClimbsResponse.fromJson', () {
    test('parses climbs and votes', () {
      final RoomCatalogClimbsResponse resp = RoomCatalogClimbsResponse.fromJson(<String, dynamic>{
        'climbs': <Map<String, dynamic>>[
          <String, dynamic>{'id': 'c1', 'name': 'Route A'},
          <String, dynamic>{'id': 'c2', 'name': 'Route B'},
        ],
        'has_more': true,
        'page_size': 20,
        'vote_counts': <String, dynamic>{'c1': 3},
        'my_votes': <String>['c1'],
        'next_cursor': 'abc',
      });
      expect(resp.climbs.length, 2);
      expect(resp.hasMore, true);
      expect(resp.pageSize, 20);
      expect(resp.voteCounts['c1'], 3);
      expect(resp.myVotes, contains('c1'));
      expect(resp.nextCursor, 'abc');
    });

    test('defaults for empty json', () {
      final RoomCatalogClimbsResponse resp = RoomCatalogClimbsResponse.fromJson(const <String, dynamic>{});
      expect(resp.climbs.isEmpty, true);
      expect(resp.hasMore, false);
      expect(resp.pageSize, 10);
      expect(resp.nextCursor, isNull);
    });
  });

  group('RoomCatalogClimbResponse.fromJson', () {
    test('parses single climb response', () {
      final RoomCatalogClimbResponse resp = RoomCatalogClimbResponse.fromJson(<String, dynamic>{
        'climb': <String, dynamic>{'id': 'c1', 'name': 'Test'},
        'vote_count': 5,
        'my_vote': true,
        'is_queued': true,
      });
      expect(resp.climb.id, 'c1');
      expect(resp.voteCount, 5);
      expect(resp.myVote, true);
      expect(resp.isQueued, true);
    });
  });
}
