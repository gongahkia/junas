Uri normalizeServerUri(String input) {
  final String trimmed = input.trim();
  if (trimmed.isEmpty) throw const FormatException('Server URL is required.');
  final String withScheme =
      trimmed.contains('://') ? trimmed : 'https://$trimmed';
  final Uri uri = Uri.parse(withScheme);
  final String normalizedPath =
      uri.path == '/' ? '' : uri.path.replaceFirst(RegExp(r'/+$'), '');
  return uri.replace(path: normalizedPath);
}

String describeServer(Uri server) {
  if (server.hasPort) return '${server.host}:${server.port}';
  return server.host;
}
