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
          shareId:
              uri.queryParameters['share_id'] ?? uri.queryParameters['shareId'],
        );
      case 'plan':
        return InviteLink(
          kind: InviteKind.plan,
          server: server,
          shareId:
              uri.queryParameters['share_id'] ?? uri.queryParameters['shareId'],
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

class RoomJoinTarget {
  const RoomJoinTarget({
    required this.slug,
    this.server,
  });

  final String slug;
  final Uri? server;
}

String? extractRoomSlugFromValue(String value) {
  final String trimmedValue = value.trim();
  if (trimmedValue.isEmpty) {
    return null;
  }

  final InviteLink? invite = InviteLink.parse(trimmedValue);
  if (invite != null &&
      invite.kind == InviteKind.join &&
      (invite.slug ?? '').trim().isNotEmpty) {
    return invite.slug!.trim();
  }

  final Uri? parsedUrl = Uri.tryParse(trimmedValue);
  if (parsedUrl != null &&
      (parsedUrl.scheme == 'http' || parsedUrl.scheme == 'https') &&
      parsedUrl.host.isNotEmpty) {
    return _extractRoomSlugFromPath(parsedUrl.path);
  }

  return _extractRoomSlugFromPath(trimmedValue);
}

RoomJoinTarget? parseRoomJoinTarget(
  String raw, {
  Uri? fallbackServer,
}) {
  final String trimmed = raw.trim();
  if (trimmed.isEmpty) {
    return null;
  }

  final InviteLink? invite = InviteLink.parse(trimmed);
  if (invite != null) {
    if (invite.kind != InviteKind.join || (invite.slug ?? '').trim().isEmpty) {
      return null;
    }
    return RoomJoinTarget(
      slug: invite.slug!.trim(),
      server: invite.server,
    );
  }

  final Uri? parsedUrl = Uri.tryParse(trimmed);
  if (parsedUrl != null &&
      (parsedUrl.scheme == 'http' || parsedUrl.scheme == 'https') &&
      parsedUrl.host.isNotEmpty) {
    final String? slug = _extractRoomSlugFromPath(parsedUrl.path);
    if (slug == null) {
      return null;
    }
    final Uri server = normalizeServerUri(
      parsedUrl.hasPort
          ? '${parsedUrl.scheme}://${parsedUrl.host}:${parsedUrl.port}'
          : '${parsedUrl.scheme}://${parsedUrl.host}',
    );
    return RoomJoinTarget(
      slug: slug,
      server: server,
    );
  }

  final String? slug = _extractRoomSlugFromPath(trimmed);
  if (slug == null) {
    return null;
  }
  return RoomJoinTarget(
    slug: slug,
    server: fallbackServer,
  );
}

String? _extractRoomSlugFromPath(String rawPath) {
  final String normalized = rawPath.trim().replaceFirst(RegExp(r'^/+'), '');
  final RegExpMatch? matched = RegExp(
    r'^(?:join/|rooms/)?([^/?#]+)$',
    caseSensitive: false,
  ).firstMatch(normalized);
  if (matched == null) {
    return null;
  }
  return Uri.decodeComponent(matched.group(1)!);
}
