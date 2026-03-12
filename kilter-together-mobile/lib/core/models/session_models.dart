import 'dart:convert';

Uri normalizeServerUri(String input) {
  final String trimmed = input.trim();
  if (trimmed.isEmpty) {
    throw const FormatException('Server URL is required.');
  }

  final String withScheme = trimmed.contains('://') ? trimmed : 'https://$trimmed';
  final Uri uri = Uri.parse(withScheme);
  final String normalizedPath = uri.path == '/' ? '' : uri.path.replaceFirst(RegExp(r'/+$'), '');
  return uri.replace(path: normalizedPath);
}

String describeServer(Uri server) {
  if (server.hasPort) {
    return '${server.host}:${server.port}';
  }
  return server.host;
}

class RoomSession {
  const RoomSession({
    required this.token,
    required this.role,
    required this.expiresAt,
  });

  final String token;
  final String role;
  final DateTime expiresAt;

  factory RoomSession.fromJson(Map<String, dynamic> json) {
    return RoomSession(
      token: json['token'] as String? ?? '',
      role: json['role'] as String? ?? '',
      expiresAt: DateTime.tryParse(json['expires_at'] as String? ?? '') ?? DateTime.now().toUtc(),
    );
  }

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'token': token,
      'role': role,
      'expires_at': expiresAt.toUtc().toIso8601String(),
    };
  }

  String encode() => jsonEncode(toJson());

  static RoomSession decode(String raw) {
    return RoomSession.fromJson(jsonDecode(raw) as Map<String, dynamic>);
  }
}

