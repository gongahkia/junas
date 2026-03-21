import 'package:flutter/material.dart';
import '../../../core/models/provider_models.dart';
import '../../../core/models/room_models.dart';
import '../../../core/presentation/climb_media_preview.dart';
import '../../../core/presentation/climbing_loader.dart';
import '../application/room_controller.dart';

bool hasClimbMeta(ProviderClimb climb) {
  return (climb.meta['color'] ?? '').isNotEmpty ||
      (climb.meta['hold_type'] ?? '').isNotEmpty ||
      (climb.meta['foot_rule'] ?? '').isNotEmpty;
}

Color parseClimbColor(String raw) {
  return switch (raw.toLowerCase().trim()) {
    'green' => const Color(0xFF16A34A),
    'blue' => const Color(0xFF2563EB),
    'red' => const Color(0xFFDC2626),
    'yellow' => const Color(0xFFEAB308),
    'orange' => const Color(0xFFEA580C),
    'purple' => const Color(0xFF9333EA),
    'pink' => const Color(0xFFEC4899),
    'white' => const Color(0xFFE2E8F0),
    'black' => const Color(0xFF1E293B),
    _ => const Color(0xFF6B7280),
  };
}

class RoomColorDot extends StatelessWidget {
  const RoomColorDot({super.key, required this.color});
  final Color color;
  @override
  Widget build(BuildContext context) {
    return Container(
      width: 10, height: 10,
      decoration: BoxDecoration(shape: BoxShape.circle, color: color),
    );
  }
}

class RoomChip extends StatelessWidget {
  const RoomChip({super.key, required this.label});
  final String label;
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: const Color(0xFFE7F8F4),
        borderRadius: BorderRadius.zero,
      ),
      child: Text(label, style: const TextStyle(fontWeight: FontWeight.w700, letterSpacing: 0.2)),
    );
  }
}

class CatalogCard extends StatelessWidget {
  const CatalogCard({
    super.key,
    required this.roomState,
    required this.queryController,
    required this.gradeMinController,
    required this.gradeMaxController,
    required this.sortOptions,
    required this.onSearch,
    required this.onSortChanged,
    required this.onSelectClimb,
    required this.onLoadMore,
    required this.onToggleVote,
    required this.onAddQueue,
    required this.onAddFinalist,
    required this.onPromoteCurrent,
    required this.onPromoteNext,
  });
  final RoomViewState roomState;
  final TextEditingController queryController;
  final TextEditingController gradeMinController;
  final TextEditingController gradeMaxController;
  final List<String> sortOptions;
  final VoidCallback onSearch;
  final ValueChanged<String?> onSortChanged;
  final ValueChanged<String> onSelectClimb;
  final VoidCallback? onLoadMore;
  final ValueChanged<String> onToggleVote;
  final ValueChanged<String> onAddQueue;
  final ValueChanged<String> onAddFinalist;
  final ValueChanged<String> onPromoteCurrent;
  final ValueChanged<String> onPromoteNext;

  @override
  Widget build(BuildContext context) {
    final RoomSnapshot room = roomState.room!;
    final RoomCatalogClimbsResponse? catalog = roomState.catalog;
    final RoomCatalogClimbResponse? selectedClimb = roomState.selectedCatalogClimb;
    final List<String> selectedClimbImageUrls = selectedClimb == null
        ? const <String>[]
        : selectedClimb.climb.media
            .where((ProviderClimbMedia item) => item.kind == 'image')
            .map((ProviderClimbMedia item) => item.url)
            .toList(growable: false);
    final QueueEntry? selectedQueueEntry = selectedClimb == null
        ? null
        : room.queue.where((QueueEntry entry) => entry.climb.id == selectedClimb.climb.id).firstOrNull;
    final bool selectedIsQueued = selectedQueueEntry != null;
    final bool selectedIsFinalist = selectedClimb != null &&
        room.finalists.any((FinalistEntry entry) => entry.climb.id == selectedClimb.climb.id);
    final String emptyCatalogMessage;
    if (room.status == 'closed') {
      emptyCatalogMessage = 'This room is closed. Start a new room if you want to browse climbs again.';
    } else if (!room.connection.connected) {
      emptyCatalogMessage = 'Waiting for the host to reconnect the provider before climbs can load.';
    } else if (room.surface == null) {
      emptyCatalogMessage = 'Waiting for the host to choose the shared surface for this room.';
    } else {
      emptyCatalogMessage = 'No climbs are loaded for this room surface yet.';
    }
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(22),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text('Catalog', style: Theme.of(context).textTheme.headlineMedium),
            const SizedBox(height: 12),
            TextField(
              controller: queryController,
              decoration: InputDecoration(
                labelText: 'Search climbs',
                suffixIcon: IconButton(onPressed: onSearch, icon: const Icon(Icons.search)),
              ),
              onSubmitted: (_) => onSearch(),
            ),
            const SizedBox(height: 12),
            DropdownButtonFormField<String>(
              initialValue: roomState.catalogSort,
              decoration: const InputDecoration(labelText: 'Sort'),
              items: sortOptions.map((String value) => DropdownMenuItem<String>(value: value, child: Text(value))).toList(growable: false),
              onChanged: onSortChanged,
            ),
            const SizedBox(height: 12),
            Row(
              children: <Widget>[
                Expanded(child: TextField(controller: gradeMinController, decoration: const InputDecoration(labelText: 'Grade min', hintText: 'e.g. V3'), textInputAction: TextInputAction.next)),
                const SizedBox(width: 12),
                Expanded(child: TextField(controller: gradeMaxController, decoration: const InputDecoration(labelText: 'Grade max', hintText: 'e.g. V8'), textInputAction: TextInputAction.search, onSubmitted: (_) => onSearch())),
              ],
            ),
            if (selectedClimb != null) ...<Widget>[
              const SizedBox(height: 16),
              Container(
                decoration: BoxDecoration(color: const Color(0xFFE9F4FF), borderRadius: BorderRadius.zero),
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Text(selectedClimb.climb.name, style: Theme.of(context).textTheme.titleLarge),
                    const SizedBox(height: 8),
                    Wrap(spacing: 10, runSpacing: 10, children: <Widget>[
                      if (selectedIsQueued) const RoomChip(label: 'Queued'),
                      if (selectedQueueEntry?.status == 'current') const RoomChip(label: 'Current'),
                      if (selectedQueueEntry?.status == 'next') const RoomChip(label: 'Next'),
                      if (selectedIsFinalist) const RoomChip(label: 'Finalist'),
                    ]),
                    const SizedBox(height: 6),
                    Text(selectedClimb.climb.setterName ?? 'Unknown setter'),
                    if (selectedClimb.climb.primaryGrade != null) ...<Widget>[const SizedBox(height: 6), Text(selectedClimb.climb.primaryGrade!)],
                    if ((selectedClimb.climb.description ?? '').isNotEmpty) ...<Widget>[const SizedBox(height: 10), Text(selectedClimb.climb.description!)],
                    const SizedBox(height: 12),
                    ClimbMediaPreview(
                      imageUrls: selectedClimbImageUrls,
                      highlightedHolds: selectedClimb.climb.highlightedHolds,
                      emptyMessage: 'No climb images are available yet',
                      errorMessage: 'Unable to load climb image layers',
                    ),
                    const SizedBox(height: 12),
                    Wrap(spacing: 10, runSpacing: 10, children: <Widget>[
                      FilledButton.tonal(onPressed: () => onToggleVote(selectedClimb.climb.id), child: Text(selectedClimb.myVote ? 'Remove fist bump' : 'Fist bump')),
                      if (room.permissions.manageQueue) FilledButton.tonal(onPressed: selectedIsQueued || room.status == 'closed' ? null : () => onAddQueue(selectedClimb.climb.id), child: Text(selectedIsQueued ? 'Already queued' : 'Add to queue')),
                      if (room.permissions.manageFinalists) FilledButton.tonal(onPressed: selectedIsFinalist || room.status == 'closed' ? null : () => onAddFinalist(selectedClimb.climb.id), child: Text(selectedIsFinalist ? 'Already finalist' : 'Add finalist')),
                      if (room.permissions.manageSession) FilledButton.tonal(onPressed: room.status == 'closed' ? null : () => onPromoteCurrent(selectedClimb.climb.id), child: const Text('Promote to current')),
                      if (room.permissions.manageSession) FilledButton.tonal(onPressed: room.status == 'closed' ? null : () => onPromoteNext(selectedClimb.climb.id), child: const Text('Promote to next')),
                    ]),
                  ],
                ),
              ),
            ],
            const SizedBox(height: 16),
            if (roomState.catalogLoading)
              Padding(padding: const EdgeInsets.symmetric(vertical: 18), child: Center(child: ClimbingLoader()))
            else if (catalog == null || catalog.climbs.isEmpty)
              Text(emptyCatalogMessage)
            else
              ...catalog.climbs.map((ProviderClimb climb) => Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: InkWell(
                  borderRadius: BorderRadius.zero,
                  onTap: () => onSelectClimb(climb.id),
                  child: Ink(
                    decoration: BoxDecoration(borderRadius: BorderRadius.zero, border: Border.all(color: const Color(0xFFE2E8F0)), color: Colors.white),
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Text(climb.name, style: Theme.of(context).textTheme.titleMedium),
                        const SizedBox(height: 4),
                        Text([if ((climb.setterName ?? '').isNotEmpty) climb.setterName!, if ((climb.primaryGrade ?? '').isNotEmpty) climb.primaryGrade!].join(' · '), style: Theme.of(context).textTheme.bodySmall),
                        if (hasClimbMeta(climb)) ...<Widget>[
                          const SizedBox(height: 8),
                          Wrap(spacing: 8, runSpacing: 6, children: <Widget>[
                            if ((climb.meta['color'] ?? '').isNotEmpty) RoomColorDot(color: parseClimbColor(climb.meta['color']!)),
                            if ((climb.meta['hold_type'] ?? '').isNotEmpty) RoomChip(label: climb.meta['hold_type']!),
                            if ((climb.meta['foot_rule'] ?? '').isNotEmpty) RoomChip(label: climb.meta['foot_rule']!),
                          ]),
                        ],
                        const SizedBox(height: 4),
                        Align(alignment: Alignment.centerRight, child: Text('${catalog.voteCounts[climb.id] ?? 0} bump${(catalog.voteCounts[climb.id] ?? 0) == 1 ? '' : 's'}')),
                      ],
                    ),
                  ),
                ),
              )),
            if (onLoadMore != null) ...<Widget>[
              const SizedBox(height: 12),
              Align(alignment: Alignment.centerLeft, child: FilledButton.tonal(onPressed: onLoadMore, child: const Text('Load more climbs'))),
            ],
          ],
        ),
      ),
    );
  }
}
