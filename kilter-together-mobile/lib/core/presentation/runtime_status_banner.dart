import 'package:flutter/material.dart';

import '../models/runtime_models.dart';

class RuntimeStatusBanner extends StatelessWidget {
  const RuntimeStatusBanner({
    required this.status,
    super.key,
  });

  final RuntimeStatus status;

  @override
  Widget build(BuildContext context) {
    if (!status.storage.isWarning) {
      return const SizedBox.shrink();
    }

    final bool critical = status.storage.isCritical;
    final Color accent =
        critical ? const Color(0xFFB42318) : const Color(0xFFB54708);
    final Color background =
        critical ? const Color(0xFFFFF3F2) : const Color(0xFFFFFAEB);

    return Card(
      color: background,
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Icon(
              critical ? Icons.warning_amber_rounded : Icons.sd_storage_rounded,
              color: accent,
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Text(
                    critical
                        ? 'Hosted backend storage is critically low'
                        : 'Hosted backend storage is nearing full',
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          color: accent,
                          fontWeight: FontWeight.w700,
                        ),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    status.storage.message,
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                          color: const Color(0xFF344054),
                        ),
                  ),
                  const SizedBox(height: 10),
                  Text(
                    'Used ${status.storage.usagePercent.toStringAsFixed(1)}% • ${_formatBytes(status.storage.availableBytes)} free on ${status.storage.mountPath}',
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: const Color(0xFF667085),
                        ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

String _formatBytes(int bytes) {
  if (bytes < 1024) {
    return '$bytes B';
  }

  const List<String> units = <String>['KB', 'MB', 'GB', 'TB', 'PB'];
  double value = bytes.toDouble();
  int unitIndex = -1;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }

  return '${value.toStringAsFixed(1)} ${units[unitIndex]}';
}
