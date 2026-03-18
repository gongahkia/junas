import 'dart:convert';

enum P2pMessageType {
  // guest -> host
  joinRequest,
  voteToggle,
  queueAdd,
  queueDelete,
  queueReorder,
  finalistAdd,
  finalistDelete,
  finalistReorder,
  statusUpdate,
  catalogQuery,
  leaveRoom,
  promoteClimb,
  clearVotes,
  updateRoomName,
  setFistBumps,
  setSurface,
  pickRandom,
  updateRole,
  removeParticipant,
  closeRoom,
  // host -> guest
  joinAccepted,
  joinRejected,
  roomStateUpdate,
  catalogResponse,
  kicked,
  roomClosed,
}

class P2pMessage {
  const P2pMessage({
    required this.type,
    required this.payload,
    this.senderId,
  });
  final P2pMessageType type;
  final Map<String, dynamic> payload;
  final String? senderId;

  List<int> encode() => utf8.encode(jsonEncode(<String, dynamic>{
    'type': type.name,
    'payload': payload,
    if (senderId != null) 'sender_id': senderId,
  }));

  static P2pMessage? decode(List<int> bytes) {
    try {
      final Map<String, dynamic> json =
          jsonDecode(utf8.decode(bytes)) as Map<String, dynamic>;
      final String typeName = json['type'] as String? ?? '';
      final P2pMessageType? type = P2pMessageType.values
          .cast<P2pMessageType?>()
          .firstWhere(
            (P2pMessageType? t) => t!.name == typeName,
            orElse: () => null,
          );
      if (type == null) return null;
      return P2pMessage(
        type: type,
        payload: (json['payload'] as Map<String, dynamic>?) ?? <String, dynamic>{},
        senderId: json['sender_id'] as String?,
      );
    } catch (_) {
      return null;
    }
  }
}
