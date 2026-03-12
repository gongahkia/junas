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
}

class ProviderCapability {
  const ProviderCapability({
    required this.id,
    required this.label,
    required this.roomSupported,
    required this.soloSupported,
    required this.surfaceHierarchy,
    required this.authFields,
  });

  final String id;
  final String label;
  final bool roomSupported;
  final bool soloSupported;
  final String surfaceHierarchy;
  final List<ProviderAuthField> authFields;

  factory ProviderCapability.fromJson(Map<String, dynamic> json) {
    final List<dynamic> rawFields = (json['auth_fields'] as List<dynamic>?) ?? <dynamic>[];
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
    );
  }
}

