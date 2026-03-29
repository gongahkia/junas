class ProviderAuthField {
  const ProviderAuthField({
    required this.key,
    required this.label,
    required this.type,
    this.placeholder,
    this.autocomplete,
  });

  final String key;
  final String label;
  final String type;
  final String? placeholder;
  final String? autocomplete;

  factory ProviderAuthField.fromJson(Map<String, dynamic> json) {
    return ProviderAuthField(
      key: json['key'] as String? ?? '',
      label: json['label'] as String? ?? '',
      type: json['type'] as String? ?? 'text',
      placeholder: json['placeholder'] as String?,
      autocomplete: json['autocomplete'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'key': key,
      'label': label,
      'type': type,
      'placeholder': placeholder,
      'autocomplete': autocomplete,
    };
  }
}

class ProviderCapability {
  const ProviderCapability({
    required this.id,
    required this.label,
    required this.roomSupported,
    required this.soloSupported,
    required this.surfaceHierarchy,
    required this.authFields,
    this.features = const <String>[],
  });

  final String id;
  final String label;
  final bool roomSupported;
  final bool soloSupported;
  final String surfaceHierarchy;
  final List<ProviderAuthField> authFields;
  final List<String> features;

  factory ProviderCapability.fromJson(Map<String, dynamic> json) {
    final List<dynamic> rawFields =
        (json['auth_fields'] as List<dynamic>?) ?? <dynamic>[];
    final List<dynamic> rawFeatures =
        (json['features'] as List<dynamic>?) ?? <dynamic>[];
    return ProviderCapability(
      id: json['id'] as String? ?? '',
      label: json['label'] as String? ?? '',
      roomSupported: json['room_supported'] as bool? ?? false,
      soloSupported: json['solo_supported'] as bool? ?? false,
      surfaceHierarchy: json['surface_hierarchy'] as String? ?? 'board',
      authFields: rawFields
          .whereType<Map<String, dynamic>>()
          .map(ProviderAuthField.fromJson)
          .toList(growable: false),
      features:
          rawFeatures.map((dynamic value) => '$value').toList(growable: false),
    );
  }

  bool supportsFeature(String feature) => features.contains(feature);
}

class ProviderConnectionState {
  const ProviderConnectionState({
    required this.connected,
    required this.providerId,
    this.metadata = const <String, String>{},
  });

  final bool connected;
  final String providerId;
  final Map<String, String> metadata;

  factory ProviderConnectionState.fromJson(Map<String, dynamic> json) {
    final Map<String, dynamic> rawMetadata =
        (json['metadata'] as Map<String, dynamic>?) ?? <String, dynamic>{};
    return ProviderConnectionState(
      connected: json['connected'] as bool? ?? false,
      providerId: json['provider_id'] as String? ?? '',
      metadata: rawMetadata
          .map((String key, dynamic value) => MapEntry(key, '$value')),
    );
  }
}

class ProviderSurface {
  const ProviderSurface({
    required this.id,
    required this.kind,
    required this.name,
    this.description,
    this.parentId,
    this.meta = const <String, String>{},
  });

  final String id;
  final String kind;
  final String name;
  final String? description;
  final String? parentId;
  final Map<String, String> meta;

  factory ProviderSurface.fromJson(Map<String, dynamic> json) {
    final Map<String, dynamic> rawMeta =
        (json['meta'] as Map<String, dynamic>?) ?? <String, dynamic>{};
    return ProviderSurface(
      id: json['id'] as String? ?? '',
      kind: json['kind'] as String? ?? '',
      name: json['name'] as String? ?? '',
      description: json['description'] as String?,
      parentId: json['parent_id'] as String?,
      meta: rawMeta.map((String key, dynamic value) => MapEntry(key, '$value')),
    );
  }

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'id': id,
      'kind': kind,
      'name': name,
      'description': description,
      'parent_id': parentId,
      'meta': meta,
    };
  }
}

class HighlightedHold {
  const HighlightedHold({
    required this.position,
    required this.x,
    required this.y,
    required this.role,
    required this.color,
  });

  final int position;
  final double x;
  final double y;
  final String role;
  final String color;

  factory HighlightedHold.fromJson(Map<String, dynamic> json) {
    return HighlightedHold(
      position: (json['position'] as num?)?.toInt() ?? 0,
      x: (json['x'] as num?)?.toDouble() ?? 0,
      y: (json['y'] as num?)?.toDouble() ?? 0,
      role: json['role'] as String? ?? '',
      color: json['color'] as String? ?? '',
    );
  }

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'position': position,
      'x': x,
      'y': y,
      'role': role,
      'color': color,
    };
  }
}

class ProviderClimbMedia {
  const ProviderClimbMedia({
    required this.url,
    required this.kind,
  });

  final String url;
  final String kind;

  factory ProviderClimbMedia.fromJson(Map<String, dynamic> json) {
    return ProviderClimbMedia(
      url: json['url'] as String? ?? '',
      kind: json['kind'] as String? ?? '',
    );
  }

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'url': url,
      'kind': kind,
    };
  }
}

class ProviderClimb {
  const ProviderClimb({
    required this.id,
    required this.externalId,
    required this.providerId,
    required this.surfaceId,
    required this.name,
    this.description,
    this.setterName,
    this.primaryGrade,
    this.secondaryGrade,
    this.createdAt,
    this.popularity,
    this.media = const <ProviderClimbMedia>[],
    this.highlightedHolds = const <HighlightedHold>[],
    this.meta = const <String, String>{},
  });

  final String id;
  final String externalId;
  final String providerId;
  final String surfaceId;
  final String name;
  final String? description;
  final String? setterName;
  final String? primaryGrade;
  final String? secondaryGrade;
  final String? createdAt;
  final int? popularity;
  final List<ProviderClimbMedia> media;
  final List<HighlightedHold> highlightedHolds;
  final Map<String, String> meta;

  factory ProviderClimb.fromJson(Map<String, dynamic> json) {
    final List<dynamic> rawMedia =
        (json['media'] as List<dynamic>?) ?? <dynamic>[];
    final List<dynamic> rawHolds =
        (json['highlighted_holds'] as List<dynamic>?) ?? <dynamic>[];
    final Map<String, dynamic> rawMeta =
        (json['meta'] as Map<String, dynamic>?) ?? <String, dynamic>{};
    return ProviderClimb(
      id: json['id'] as String? ?? '',
      externalId: json['external_id'] as String? ?? '',
      providerId: json['provider_id'] as String? ?? '',
      surfaceId: json['surface_id'] as String? ?? '',
      name: json['name'] as String? ?? '',
      description: json['description'] as String?,
      setterName: json['setter_name'] as String?,
      primaryGrade: json['primary_grade'] as String?,
      secondaryGrade: json['secondary_grade'] as String?,
      createdAt: json['created_at'] as String?,
      popularity: (json['popularity'] as num?)?.toInt(),
      media: rawMedia
          .whereType<Map<String, dynamic>>()
          .map(ProviderClimbMedia.fromJson)
          .toList(growable: false),
      highlightedHolds: rawHolds
          .whereType<Map<String, dynamic>>()
          .map(HighlightedHold.fromJson)
          .toList(growable: false),
      meta: rawMeta.map((String key, dynamic value) => MapEntry(key, '$value')),
    );
  }

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'id': id,
      'external_id': externalId,
      'provider_id': providerId,
      'surface_id': surfaceId,
      'name': name,
      'description': description,
      'setter_name': setterName,
      'primary_grade': primaryGrade,
      'secondary_grade': secondaryGrade,
      'created_at': createdAt,
      'popularity': popularity,
      'media': media
          .map((ProviderClimbMedia item) => item.toJson())
          .toList(growable: false),
      'highlighted_holds': highlightedHolds
          .map((HighlightedHold item) => item.toJson())
          .toList(growable: false),
      'meta': meta,
    };
  }
}
