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

    final String? rawServer = uri.queryParameters['server'];
    if (rawServer == null || rawServer.trim().isEmpty) {
      return null;
    }

    final Uri server;
    try {
      server = normalizeServerUri(rawServer);
    } on FormatException {
      return null;
    }

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
          shareId: uri.queryParameters['share_id'] ?? uri.queryParameters['shareId'],
        );
      case 'plan':
        return InviteLink(
          kind: InviteKind.plan,
          server: server,
          shareId: uri.queryParameters['share_id'] ?? uri.queryParameters['shareId'],
        );
      default:
        return null;
    }
  }

  Uri toUri() {
    return Uri(
      scheme: 'kiltertogether',
      host: switch (kind) {
        InviteKind.join => 'join',
        InviteKind.recap => 'recap',
        InviteKind.plan => 'plan',
      },
      queryParameters: <String, String>{
        'server': server.toString(),
        if (slug != null && slug!.isNotEmpty) 'slug': slug!,
        if (shareId != null && shareId!.isNotEmpty) 'share_id': shareId!,
      },
    );
  }

  Map<String, String> toRouteQueryParameters() {
    return <String, String>{
      'server': server.toString(),
      if (slug != null && slug!.isNotEmpty) 'slug': slug!,
      if (shareId != null && shareId!.isNotEmpty) 'share_id': shareId!,
    };
  }
}
