class ClimbLogEntry {
  const ClimbLogEntry({
    required this.id,
    required this.climbId,
    required this.providerId,
    required this.surfaceContext,
    required this.timestamp,
    required this.status,
    this.note,
    this.climbName,
  });

  final String id;
  final String climbId;
  final String providerId;
  final Map<String, String> surfaceContext;
  final String timestamp;
  final String status; // seen, attempted, sent, completed
  final String? note;
  final String? climbName;

  factory ClimbLogEntry.fromJson(Map<String, dynamic> json) {
    final Map<String, dynamic> rawContext =
        (json['surface_context'] as Map<String, dynamic>?) ??
            <String, dynamic>{};
    return ClimbLogEntry(
      id: json['id'] as String? ?? '',
      climbId: json['climb_id'] as String? ?? '',
      providerId: json['provider_id'] as String? ?? '',
      surfaceContext: rawContext
          .map((String key, dynamic value) => MapEntry(key, '$value')),
      timestamp: json['timestamp'] as String? ?? '',
      status: json['status'] as String? ?? 'seen',
      note: json['note'] as String?,
      climbName: json['climb_name'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'id': id,
      'climb_id': climbId,
      'provider_id': providerId,
      'surface_context': surfaceContext,
      'timestamp': timestamp,
      'status': status,
      'note': note,
      'climb_name': climbName,
    };
  }
}
