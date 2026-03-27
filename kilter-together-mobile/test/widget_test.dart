import 'package:flutter_test/flutter_test.dart';
import 'package:kilter_together_mobile/core/deep_links/invite_links.dart';
import 'package:kilter_together_mobile/core/models/room_models.dart';
import 'package:kilter_together_mobile/core/p2p/p2p_message_types.dart';
import 'package:kilter_together_mobile/core/p2p/host_room_service.dart';

void main() {
  group('P2pMessage', () {
    test('encode/decode roundtrip', () {
      const P2pMessage msg = P2pMessage(
        type: P2pMessageType.joinRequest,
        payload: <String, dynamic>{'display_name': 'Alice'},
      );
      final List<int> bytes = msg.encode();
      final P2pMessage? decoded = P2pMessage.decode(bytes);
      expect(decoded, isNotNull);
      expect(decoded!.type, P2pMessageType.joinRequest);
      expect(decoded.payload['display_name'], 'Alice');
    });

    test('decode invalid returns null', () {
      expect(P2pMessage.decode(<int>[0, 1, 2]), isNull);
    });
  });

  group('InviteLink', () {
    test('parse join link', () {
      final InviteLink? link =
          InviteLink.parse('kiltertogether://join?slug=abc123');
      expect(link, isNotNull);
      expect(link!.kind, InviteKind.join);
      expect(link.slug, 'abc123');
    });

    test('parse recap link', () {
      final InviteLink? link =
          InviteLink.parse('kiltertogether://recap?share_id=xyz');
      expect(link, isNotNull);
      expect(link!.kind, InviteKind.recap);
      expect(link.shareId, 'xyz');
    });

    test('toUri roundtrip', () {
      const InviteLink link =
          InviteLink(kind: InviteKind.join, slug: 'test123');
      final String raw = link.toUri().toString();
      final InviteLink? parsed = InviteLink.parse(raw);
      expect(parsed, isNotNull);
      expect(parsed!.slug, 'test123');
    });
  });

  group('HostRoomService', () {
    late HostRoomService service;

    setUp(() {
      service = HostRoomService(
        state: HostRoomState(slug: 'test', providerId: 'kilter'),
      );
    });

    test('add participant', () {
      final int id = service.addParticipant(displayName: 'Host', role: 'host');
      expect(id, greaterThan(0));
      expect(service.state.participants.length, 1);
    });

    test('reject duplicate display name', () {
      service.addParticipant(displayName: 'Alice', role: 'host');
      final int id =
          service.addParticipant(displayName: 'Alice', role: 'participant');
      expect(id, -1);
    });

    test('toggle vote', () {
      final int id = service.addParticipant(displayName: 'Alice', role: 'host');
      service.toggleVote(id, 'climb1');
      expect(service.state.voteCounts['climb1'], 1);
      service.toggleVote(id, 'climb1');
      expect(service.state.voteCounts.containsKey('climb1'), false);
    });

    test('snapshot includes participants', () {
      final int id = service.addParticipant(displayName: 'Host', role: 'host');
      final RoomSnapshot snapshot = service.toSnapshot(forParticipantId: id);
      expect(snapshot.slug, 'test');
      expect(snapshot.participants.length, 1);
      expect(snapshot.canManage, true);
    });

    test('close room', () {
      service.closeRoom();
      expect(service.state.status, 'closed');
    });
  });
}
