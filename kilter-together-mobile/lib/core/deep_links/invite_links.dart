import '../models/session_models.dart';

enum InviteKind {
  join,
  recap,
  plan,
}

class InviteLink {
  const InviteLink({
    required this.kind,
    required this.server,
    this.slug,
    this.shareId,
  });

  final InviteKind kind;
  final Uri server;
  final String? slug;
  final String? shareId;

  static InviteLink? parse(String raw) {
    final String trimmed = raw.trim();
    if (trimmed.isEmpty) {
      return null;
    }

    final Uri uri = Uri.parse(trimmed);
    if (uri.scheme != 'kiltertogether') {
      return null;
    }

    final Uri server = normalizeServerUri(uri.queryParameters['server'] ?? '');
    switch (uri.host) {
      case 'join':
        return InviteLink(
          kind: InviteKind.join,
          server: server,
          slug: uri.queryParameters['slug'],
        );
      case 'recap':
        return InviteLink(
          kind: InviteKind.recap,
          server: server,
          shareId: uri.queryParameters['share_id'],
        );
      case 'plan':
        return InviteLink(
          kind: InviteKind.plan,
          server: server,
          shareId: uri.queryParameters['share_id'],
        );
      default:
        return null;
    }
  }
}

