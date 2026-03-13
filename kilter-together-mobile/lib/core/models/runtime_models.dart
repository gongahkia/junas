class RuntimeStorageStatus {
  const RuntimeStorageStatus({
    required this.severity,
    required this.message,
    required this.mountPath,
    required this.usedBytes,
    required this.availableBytes,
    required this.totalBytes,
    required this.usagePercent,
    required this.warningPercent,
    required this.criticalPercent,
  });

  final String severity;
  final String message;
  final String mountPath;
  final int usedBytes;
  final int availableBytes;
  final int totalBytes;
  final double usagePercent;
  final int warningPercent;
  final int criticalPercent;

  bool get isWarning => severity == 'warning' || severity == 'critical';
  bool get isCritical => severity == 'critical';

  factory RuntimeStorageStatus.fromJson(Map<String, dynamic> json) {
    return RuntimeStorageStatus(
      severity: json['severity'] as String? ?? 'unknown',
      message: json['message'] as String? ?? '',
      mountPath: json['mount_path'] as String? ?? '',
      usedBytes: (json['used_bytes'] as num?)?.toInt() ?? 0,
      availableBytes: (json['available_bytes'] as num?)?.toInt() ?? 0,
      totalBytes: (json['total_bytes'] as num?)?.toInt() ?? 0,
      usagePercent: (json['usage_percent'] as num?)?.toDouble() ?? 0,
      warningPercent: (json['warning_percent'] as num?)?.toInt() ?? 80,
      criticalPercent: (json['critical_percent'] as num?)?.toInt() ?? 90,
    );
  }
}

class RuntimeStatus {
  const RuntimeStatus({
    required this.status,
    required this.runtimeReady,
    required this.storage,
    this.runtimeMessage,
    this.generatedAt,
  });

  final String status;
  final bool runtimeReady;
  final String? runtimeMessage;
  final RuntimeStorageStatus storage;
  final DateTime? generatedAt;

  factory RuntimeStatus.fromJson(Map<String, dynamic> json) {
    return RuntimeStatus(
      status: json['status'] as String? ?? 'unknown',
      runtimeReady: json['runtime_ready'] as bool? ?? false,
      runtimeMessage: json['runtime_message'] as String?,
      storage: RuntimeStorageStatus.fromJson(
        (json['storage'] as Map<String, dynamic>?) ?? <String, dynamic>{},
      ),
      generatedAt: DateTime.tryParse(json['generated_at'] as String? ?? ''),
    );
  }
}
