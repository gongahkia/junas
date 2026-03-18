enum InviteKind { join, recap, plan }

class InviteLink {
  const InviteLink({
    required this.kind,
    this.slug,
    this.shareId,
  });
  final InviteKind kind;
  final String? slug;
  final String? shareId;

  static InviteLink? parse(String raw) {
    final String trimmed = raw.trim();
    if (trimmed.isEmpty) return null;
    final Uri? uri = Uri.tryParse(trimmed);
    if (uri == null || uri.scheme != 'kiltertogether') return null;
    switch (uri.host) {
      case 'join':
        return InviteLink(
          kind: InviteKind.join,
          slug: uri.queryParameters['slug'],
        );
      case 'recap':
        return InviteLink(
          kind: InviteKind.recap,
          shareId: uri.queryParameters['share_id'] ?? uri.queryParameters['shareId'],
        );
      case 'plan':
        return InviteLink(
          kind: InviteKind.plan,
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
        if (slug != null && slug!.isNotEmpty) 'slug': slug!,
        if (shareId != null && shareId!.isNotEmpty) 'share_id': shareId!,
      },
    );
  }

  Map<String, String> toRouteQueryParameters() {
    return <String, String>{
      if (slug != null && slug!.isNotEmpty) 'slug': slug!,
      if (shareId != null && shareId!.isNotEmpty) 'share_id': shareId!,
    };
  }
}
