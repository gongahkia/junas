import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';

import '../../../core/models/climb_log_models.dart';
import '../../../core/presentation/climbing_loader.dart';
import '../../../core/presentation/app_surfaces.dart';
import '../../../core/presentation/gradient_scaffold.dart';
import '../../../core/storage/climb_log_repository.dart';
import '../../../core/theme/app_theme.dart';

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
    final KilterPalette palette = kilterPaletteOf(context);

    return GradientScaffold(
      title: 'Climb log',
      subtitle: 'Your personal climb history from all sessions.',
      actions: <Widget>[
        IconButton(
          onPressed: () => _showExportSheet(),
          icon: const Icon(Icons.ios_share),
        ),
        const SizedBox.shrink(),
      ],
      child: entriesValue.when(
        data: (List<ClimbLogEntry> entries) {
          if (entries.isEmpty) {
            return AppPanel(
              accentColor: palette.highlight,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  AppBadge(
                    label: 'No entries yet',
                    icon: Icons.landscape_outlined,
                    color: palette.highlight,
                  ),
                  const SizedBox(height: 16),
                  Text(
                    'Your first session notes will show up here.',
                    style: Theme.of(context).textTheme.headlineMedium,
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'Climb log entries are recorded as you interact with climbs during shared or solo sessions.',
                  ),
                ],
              ),
            );
          }
          final List<ClimbLogEntry> sortedEntries =
              List<ClimbLogEntry>.from(entries)
                ..sort(
                  (ClimbLogEntry left, ClimbLogEntry right) =>
                      right.timestamp.compareTo(left.timestamp),
                );

          return Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              _LogSummaryPanel(entries: sortedEntries),
              const SizedBox(height: 16),
              ...sortedEntries
                  .map((ClimbLogEntry entry) => _ClimbLogTile(entry: entry)),
            ],
          );
        },
        loading: () => AppPanel(
          accentColor: palette.secondary,
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: 28),
            child: Column(
              children: <Widget>[
                Center(child: ClimbingLoader()),
                const SizedBox(height: 16),
                Text(
                  'Loading your recent sessions.',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
              ],
            ),
          ),
        ),
        error: (Object error, StackTrace stackTrace) => AppPanel(
          accentColor: const Color(0xFF9B3445),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Text(
                'Climb log unavailable',
                style: Theme.of(context).textTheme.headlineMedium,
              ),
              const SizedBox(height: 8),
              Text('$error'),
            ],
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

class _LogSummaryPanel extends StatelessWidget {
  const _LogSummaryPanel({
    required this.entries,
  });

  final List<ClimbLogEntry> entries;

  @override
  Widget build(BuildContext context) {
    final KilterPalette palette = kilterPaletteOf(context);
    final int completedCount = entries
        .where((ClimbLogEntry entry) => entry.status == 'completed')
        .length;
    final int attemptedCount = entries
        .where((ClimbLogEntry entry) => entry.status == 'attempted')
        .length;

    return AppPanel(
      accentColor: palette.primary,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: <Widget>[
              AppBadge(
                label: '${entries.length} logged',
                icon: Icons.checklist_rounded,
                color: palette.primary,
              ),
              AppBadge(
                label: '$completedCount completed',
                icon: Icons.flag_rounded,
                color: palette.secondary,
              ),
              AppBadge(
                label: '$attemptedCount attempts',
                icon: Icons.bolt_rounded,
                color: palette.highlight,
              ),
            ],
          ),
          const SizedBox(height: 16),
          Text(
            'Recent activity',
            style: Theme.of(context).textTheme.headlineMedium,
          ),
          const SizedBox(height: 8),
          Text(
            'A local timeline of the climbs you touched most recently, ready to export when you need it.',
          ),
        ],
      ),
    );
  }
}

class _ClimbLogTile extends StatelessWidget {
  const _ClimbLogTile({
    required this.entry,
  });

  final ClimbLogEntry entry;

  @override
  Widget build(BuildContext context) {
    final Color accent = _statusColor(context, entry.status);

    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: AppPanel(
        accentColor: accent,
        padding: const EdgeInsets.all(18),
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
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    crossAxisAlignment: WrapCrossAlignment.center,
                    children: <Widget>[
                      AppBadge(
                        label: entry.providerId.toUpperCase(),
                        icon: Icons.terrain_rounded,
                        color: accent,
                      ),
                      Text(
                        _formatTimestamp(entry.timestamp),
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                    ],
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

  Color _statusColor(BuildContext context, String status) {
    final KilterPalette palette = kilterPaletteOf(context);
    switch (status) {
      case 'completed':
        return palette.primary;
      case 'sent':
        return palette.secondary;
      case 'attempted':
        return palette.highlight;
      default:
        return palette.subtleInk;
    }
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
    final KilterPalette palette = kilterPaletteOf(context);
    final Color chipColor;
    switch (status) {
      case 'completed':
        chipColor = palette.primary;
        break;
      case 'sent':
        chipColor = palette.secondary;
        break;
      case 'attempted':
        chipColor = palette.highlight;
        break;
      default:
        chipColor = palette.subtleInk;
    }
    return AppBadge(
      label: status,
      color: chipColor,
    );
  }
}
