import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';

import '../../../core/models/climb_log_models.dart';
import '../../../core/presentation/gradient_scaffold.dart';
import '../../../core/storage/climb_log_repository.dart';

final _climbLogEntriesProvider =
    FutureProvider.autoDispose<List<ClimbLogEntry>>((Ref ref) {
  return ref.read(climbLogRepositoryProvider).listAll();
});

class ClimbLogScreen extends ConsumerStatefulWidget {
  const ClimbLogScreen({super.key});

  @override
  ConsumerState<ClimbLogScreen> createState() => _ClimbLogScreenState();
}

class _ClimbLogScreenState extends ConsumerState<ClimbLogScreen> {
  @override
  Widget build(BuildContext context) {
    final AsyncValue<List<ClimbLogEntry>> entriesValue =
        ref.watch(_climbLogEntriesProvider);

    return GradientScaffold(
      title: 'Climb log',
      subtitle: 'Your personal climb history from all sessions.',
      actions: <Widget>[
        IconButton(
          onPressed: () => _showExportSheet(),
          icon: const Icon(Icons.ios_share),
        ),
        IconButton(
          onPressed: () => context.goNamed('settings'),
          icon: const Icon(Icons.close),
        ),
      ],
      child: entriesValue.when(
        data: (List<ClimbLogEntry> entries) {
          if (entries.isEmpty) {
            return const Card(
              child: Padding(
                padding: EdgeInsets.all(22),
                child: Text(
                  'No climb log entries yet. Entries are recorded as you interact with climbs during sessions.',
                ),
              ),
            );
          }
          return Column(
            children: entries
                .map((ClimbLogEntry entry) => _ClimbLogTile(entry: entry))
                .toList(growable: false),
          );
        },
        loading: () => const Card(
          child: Padding(
            padding: EdgeInsets.all(32),
            child: Center(child: CircularProgressIndicator()),
          ),
        ),
        error: (Object error, StackTrace stackTrace) => Card(
          child: Padding(
            padding: const EdgeInsets.all(22),
            child: Text('$error'),
          ),
        ),
      ),
    );
  }

  Future<void> _showExportSheet() async {
    final String? format = await showModalBottomSheet<String>(
      context: context,
      builder: (BuildContext dialogContext) {
        return SafeArea(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              ListTile(
                leading: const Icon(Icons.data_object),
                title: const Text('Export as JSON'),
                onTap: () => Navigator.of(dialogContext).pop('json'),
              ),
              ListTile(
                leading: const Icon(Icons.table_chart_outlined),
                title: const Text('Export as CSV'),
                onTap: () => Navigator.of(dialogContext).pop('csv'),
              ),
            ],
          ),
        );
      },
    );
    if (format == null || !mounted) {
      return;
    }
    try {
      final ClimbLogRepository repository =
          ref.read(climbLogRepositoryProvider);
      final String content;
      final String filename;
      if (format == 'csv') {
        content = await repository.exportCsv();
        filename = 'climb_log.csv';
      } else {
        content = await repository.exportJson();
        filename = 'climb_log.json';
      }
      final Directory tempDir = await getTemporaryDirectory();
      final File file = File('${tempDir.path}/$filename');
      await file.writeAsString(content);
      await Share.shareXFiles(<XFile>[XFile(file.path)]);
    } catch (error) {
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Export failed: $error')),
      );
    }
  }
}

class _ClimbLogTile extends StatelessWidget {
  const _ClimbLogTile({
    required this.entry,
  });

  final ClimbLogEntry entry;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Container(
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(22),
          border: Border.all(color: const Color(0xFFE2E8F0)),
        ),
        padding: const EdgeInsets.all(16),
        child: Row(
          children: <Widget>[
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Text(
                    entry.climbName ?? entry.climbId,
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  const SizedBox(height: 4),
                  Text(
                    '${entry.providerId} -- ${_formatTimestamp(entry.timestamp)}',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                  if (entry.note != null && entry.note!.isNotEmpty) ...<Widget>[
                    const SizedBox(height: 4),
                    Text(
                      entry.note!,
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                            fontStyle: FontStyle.italic,
                          ),
                    ),
                  ],
                ],
              ),
            ),
            const SizedBox(width: 12),
            _StatusChip(status: entry.status),
          ],
        ),
      ),
    );
  }

  String _formatTimestamp(String timestamp) {
    final DateTime? parsed = DateTime.tryParse(timestamp);
    if (parsed == null) {
      return timestamp;
    }
    final DateTime local = parsed.toLocal();
    return '${local.year}-${_pad(local.month)}-${_pad(local.day)} '
        '${_pad(local.hour)}:${_pad(local.minute)}';
  }

  String _pad(int value) => value.toString().padLeft(2, '0');
}

class _StatusChip extends StatelessWidget {
  const _StatusChip({
    required this.status,
  });

  final String status;

  @override
  Widget build(BuildContext context) {
    final Color chipColor;
    switch (status) {
      case 'completed':
        chipColor = const Color(0xFF059669);
        break;
      case 'sent':
        chipColor = const Color(0xFF0891B2);
        break;
      case 'attempted':
        chipColor = const Color(0xFFD97706);
        break;
      default:
        chipColor = const Color(0xFF6B7280);
    }
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: chipColor.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: chipColor.withValues(alpha: 0.3)),
      ),
      child: Text(
        status,
        style: Theme.of(context).textTheme.labelSmall?.copyWith(
              color: chipColor,
              fontWeight: FontWeight.w600,
            ),
      ),
    );
  }
}
