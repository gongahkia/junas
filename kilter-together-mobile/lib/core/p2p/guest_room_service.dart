import '../models/provider_models.dart';
import 'p2p_message_types.dart';
import 'p2p_transport.dart';

class GuestRoomService {
  GuestRoomService({
    required this.transport,
    required this.hostPeerId,
  });
  final P2pTransport transport;
  final String hostPeerId;

  void sendJoinRequest(String displayName) {
    _send(P2pMessage(
      type: P2pMessageType.joinRequest,
      payload: <String, dynamic>{'display_name': displayName},
    ));
  }

  void toggleVote(String climbId) {
    _send(P2pMessage(
      type: P2pMessageType.voteToggle,
      payload: <String, dynamic>{'climb_id': climbId},
    ));
  }

  void addQueueEntry(ProviderClimb climb) {
    _send(P2pMessage(
      type: P2pMessageType.queueAdd,
      payload: <String, dynamic>{'climb': climb.toJson()},
    ));
  }

  void deleteQueueEntry(int entryId) {
    _send(P2pMessage(
      type: P2pMessageType.queueDelete,
      payload: <String, dynamic>{'entry_id': entryId},
    ));
  }

  void reorderQueue(List<int> entryIds) {
    _send(P2pMessage(
      type: P2pMessageType.queueReorder,
      payload: <String, dynamic>{'entry_ids': entryIds},
    ));
  }

  void addFinalist(ProviderClimb climb) {
    _send(P2pMessage(
      type: P2pMessageType.finalistAdd,
      payload: <String, dynamic>{'climb': climb.toJson()},
    ));
  }

  void deleteFinalist(int entryId) {
    _send(P2pMessage(
      type: P2pMessageType.finalistDelete,
      payload: <String, dynamic>{'entry_id': entryId},
    ));
  }

  void reorderFinalists(List<int> entryIds) {
    _send(P2pMessage(
      type: P2pMessageType.finalistReorder,
      payload: <String, dynamic>{'entry_ids': entryIds},
    ));
  }

  void updateMyStatus(String status) {
    _send(P2pMessage(
      type: P2pMessageType.statusUpdate,
      payload: <String, dynamic>{'status': status},
    ));
  }

  void promoteClimb(String climbId, String status) {
    _send(P2pMessage(
      type: P2pMessageType.promoteClimb,
      payload: <String, dynamic>{'climb_id': climbId, 'status': status},
    ));
  }

  void clearVotes() {
    _send(const P2pMessage(type: P2pMessageType.clearVotes, payload: <String, dynamic>{}));
  }

  void updateRoomName(String roomName) {
    _send(P2pMessage(
      type: P2pMessageType.updateRoomName,
      payload: <String, dynamic>{'room_name': roomName},
    ));
  }

  void setFistBumpsEnabled(bool enabled) {
    _send(P2pMessage(
      type: P2pMessageType.setFistBumps,
      payload: <String, dynamic>{'enabled': enabled},
    ));
  }

  void setSurface(ProviderSurface surface) {
    _send(P2pMessage(
      type: P2pMessageType.setSurface,
      payload: <String, dynamic>{'surface': surface.toJson()},
    ));
  }

  void pickRandom(String source) {
    _send(P2pMessage(
      type: P2pMessageType.pickRandom,
      payload: <String, dynamic>{'source': source},
    ));
  }

  void updateParticipantRole(int participantId, String role) {
    _send(P2pMessage(
      type: P2pMessageType.updateRole,
      payload: <String, dynamic>{'participant_id': participantId, 'role': role},
    ));
  }

  void removeParticipant(int participantId) {
    _send(P2pMessage(
      type: P2pMessageType.removeParticipant,
      payload: <String, dynamic>{'participant_id': participantId},
    ));
  }

  void closeRoom() {
    _send(const P2pMessage(type: P2pMessageType.closeRoom, payload: <String, dynamic>{}));
  }

  void leaveRoom() {
    _send(const P2pMessage(type: P2pMessageType.leaveRoom, payload: <String, dynamic>{}));
  }

  void queryCatalog(Map<String, dynamic> query) {
    _send(P2pMessage(type: P2pMessageType.catalogQuery, payload: query));
  }

  void _send(P2pMessage message) {
    transport.send(hostPeerId, message);
  }
}
