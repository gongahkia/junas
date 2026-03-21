import 'package:flutter/material.dart';
import '../../../core/models/room_models.dart';

class QueueCard extends StatelessWidget {
  const QueueCard({
    super.key,
    required this.room,
    required this.queueStatuses,
    required this.onMoveUp,
    required this.onMoveDown,
    required this.onDelete,
    required this.onPromoteCurrent,
    required this.onPromoteNext,
    required this.onStatusChanged,
    this.onAutoRefill,
  });
  final RoomSnapshot room;
  final List<String> queueStatuses;
  final ValueChanged<int> onMoveUp;
  final ValueChanged<int> onMoveDown;
  final ValueChanged<int> onDelete;
  final ValueChanged<String> onPromoteCurrent;
  final ValueChanged<String> onPromoteNext;
  final void Function(int entryId, String? value) onStatusChanged;
  final VoidCallback? onAutoRefill;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(22),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text('Queue', style: Theme.of(context).textTheme.headlineMedium),
            const SizedBox(height: 12),
            if (onAutoRefill != null) ...<Widget>[
              Container(
                width: double.infinity,
                decoration: BoxDecoration(color: const Color(0xFFF0F0F0), borderRadius: BorderRadius.zero, border: Border.all(color: const Color(0xFFD4D4D4))),
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    const Text('Queue empty \u2014 add top-voted climbs?'),
                    const SizedBox(height: 10),
                    FilledButton.tonal(onPressed: onAutoRefill, child: const Text('Add top-voted to queue')),
                  ],
                ),
              ),
              const SizedBox(height: 12),
            ],
            if (room.queue.isEmpty)
              const Text('No climbs are queued yet.')
            else
              ...room.queue.map((QueueEntry entry) => Padding(
                padding: const EdgeInsets.only(bottom: 14),
                child: Container(
                  decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.zero, border: Border.all(color: const Color(0xFFE2E8F0))),
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      Text(entry.climb.name, style: Theme.of(context).textTheme.titleLarge),
                      const SizedBox(height: 6),
                      Text('${entry.status} · added by ${entry.addedBy}'),
                      const SizedBox(height: 12),
                      Wrap(spacing: 10, runSpacing: 10, children: <Widget>[
                        if (room.permissions.manageQueue) SizedBox(
                          width: 180,
                          child: DropdownButtonFormField<String>(
                            initialValue: entry.status,
                            decoration: const InputDecoration(labelText: 'Status'),
                            items: queueStatuses.map((String value) => DropdownMenuItem<String>(value: value, child: Text(value))).toList(growable: false),
                            onChanged: (String? value) => onStatusChanged(entry.id, value),
                          ),
                        ),
                        if (room.permissions.manageQueue) OutlinedButton(onPressed: () => onMoveUp(entry.id), child: const Text('Up')),
                        if (room.permissions.manageQueue) OutlinedButton(onPressed: () => onMoveDown(entry.id), child: const Text('Down')),
                        if (room.permissions.manageSession) FilledButton.tonal(onPressed: () => onPromoteCurrent(entry.climb.id), child: const Text('Current')),
                        if (room.permissions.manageSession) FilledButton.tonal(onPressed: () => onPromoteNext(entry.climb.id), child: const Text('Next')),
                        if (room.permissions.manageQueue) OutlinedButton(onPressed: () => onDelete(entry.id), child: const Text('Delete')),
                      ]),
                    ],
                  ),
                ),
              )),
          ],
        ),
      ),
    );
  }
}

class FinalistsCard extends StatelessWidget {
  const FinalistsCard({
    super.key,
    required this.room,
    required this.onMoveUp,
    required this.onMoveDown,
    required this.onDelete,
    required this.onPickRandomFinalists,
    required this.onPickRandomTopVoted,
    required this.onPromoteCurrent,
    required this.onPromoteNext,
  });
  final RoomSnapshot room;
  final ValueChanged<int> onMoveUp;
  final ValueChanged<int> onMoveDown;
  final ValueChanged<int> onDelete;
  final VoidCallback onPickRandomFinalists;
  final VoidCallback onPickRandomTopVoted;
  final ValueChanged<String> onPromoteCurrent;
  final ValueChanged<String> onPromoteNext;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(22),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Row(children: <Widget>[
              Expanded(child: Text('Finalists', style: Theme.of(context).textTheme.headlineMedium)),
              if (room.permissions.manageFinalists) PopupMenuButton<String>(
                onSelected: (String value) { if (value == 'finalists') { onPickRandomFinalists(); } else { onPickRandomTopVoted(); } },
                itemBuilder: (BuildContext context) => const <PopupMenuEntry<String>>[
                  PopupMenuItem<String>(value: 'finalists', child: Text('Pick random finalist')),
                  PopupMenuItem<String>(value: 'top_voted', child: Text('Pick from top fist bumps')),
                ],
              ),
            ]),
            const SizedBox(height: 12),
            if (room.finalists.isEmpty)
              const Text('No finalists selected yet.')
            else
              ...room.finalists.map((FinalistEntry entry) => Padding(
                padding: const EdgeInsets.only(bottom: 14),
                child: Container(
                  decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.zero, border: Border.all(color: const Color(0xFFE2E8F0))),
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      Text(entry.climb.name, style: Theme.of(context).textTheme.titleLarge),
                      const SizedBox(height: 6),
                      Text('Added by ${entry.addedBy}'),
                      const SizedBox(height: 12),
                      Wrap(spacing: 10, runSpacing: 10, children: <Widget>[
                        if (room.permissions.manageFinalists) OutlinedButton(onPressed: () => onMoveUp(entry.id), child: const Text('Up')),
                        if (room.permissions.manageFinalists) OutlinedButton(onPressed: () => onMoveDown(entry.id), child: const Text('Down')),
                        if (room.permissions.manageSession) FilledButton.tonal(onPressed: () => onPromoteCurrent(entry.climb.id), child: const Text('Current')),
                        if (room.permissions.manageSession) FilledButton.tonal(onPressed: () => onPromoteNext(entry.climb.id), child: const Text('Next')),
                        if (room.permissions.manageFinalists) OutlinedButton(onPressed: () => onDelete(entry.id), child: const Text('Delete')),
                      ]),
                    ],
                  ),
                ),
              )),
          ],
        ),
      ),
    );
  }
}

class ParticipantsCard extends StatelessWidget {
  const ParticipantsCard({
    super.key,
    required this.room,
    required this.onRoleChanged,
    required this.onRemove,
  });
  final RoomSnapshot room;
  final void Function(int participantId, String? role) onRoleChanged;
  final ValueChanged<int> onRemove;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(22),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text('Participants', style: Theme.of(context).textTheme.headlineMedium),
            const SizedBox(height: 12),
            ...room.participants.map((Participant participant) => Padding(
              padding: const EdgeInsets.only(bottom: 14),
              child: Container(
                decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.zero, border: Border.all(color: const Color(0xFFE2E8F0))),
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Row(children: <Widget>[
                      Expanded(child: Text(participant.displayName, style: Theme.of(context).textTheme.titleLarge)),
                      Icon(participant.isOnline ? Icons.circle : Icons.circle_outlined, size: 14, color: participant.isOnline ? const Color(0xFF1A1A1A) : const Color(0xFF94A3B8)),
                    ]),
                    const SizedBox(height: 6),
                    Text('${participant.role} · ${participant.status}'),
                    if (room.permissions.assignCoHosts && participant.role != 'host') ...<Widget>[
                      const SizedBox(height: 12),
                      DropdownButtonFormField<String>(
                        initialValue: participant.role == 'co_host' ? 'co_host' : 'participant',
                        decoration: const InputDecoration(labelText: 'Role'),
                        items: const <DropdownMenuItem<String>>[
                          DropdownMenuItem<String>(value: 'participant', child: Text('participant')),
                          DropdownMenuItem<String>(value: 'co_host', child: Text('co_host')),
                        ],
                        onChanged: (String? value) => onRoleChanged(participant.id, value),
                      ),
                    ],
                    if (room.permissions.manageParticipants && participant.displayName != room.displayName && participant.role != 'host') ...<Widget>[
                      const SizedBox(height: 12),
                      OutlinedButton(onPressed: () => onRemove(participant.id), child: const Text('Remove participant')),
                    ],
                  ],
                ),
              ),
            )),
          ],
        ),
      ),
    );
  }
}

class ManageRoomCard extends StatelessWidget {
  const ManageRoomCard({
    super.key,
    required this.room,
    required this.roomNameController,
    required this.assistantModes,
    required this.busy,
    required this.onSaveName,
    required this.onAssistantModeChanged,
    required this.onFistBumpsChanged,
    required this.onClearVotes,
    required this.onCloseRoom,
  });
  final RoomSnapshot room;
  final TextEditingController roomNameController;
  final List<String> assistantModes;
  final bool busy;
  final VoidCallback? onSaveName;
  final ValueChanged<String?>? onAssistantModeChanged;
  final ValueChanged<bool>? onFistBumpsChanged;
  final VoidCallback? onClearVotes;
  final VoidCallback? onCloseRoom;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(22),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text('Room controls', style: Theme.of(context).textTheme.headlineMedium),
            const SizedBox(height: 12),
            TextField(controller: roomNameController, decoration: const InputDecoration(labelText: 'Room name')),
            const SizedBox(height: 10),
            if (onSaveName != null) FilledButton.tonal(onPressed: busy ? null : onSaveName, child: const Text('Save room name')),
            const SizedBox(height: 12),
            DropdownButtonFormField<String>(
              initialValue: room.assistant.mode,
              decoration: const InputDecoration(labelText: 'Assistant mode'),
              items: assistantModes.map((String value) => DropdownMenuItem<String>(value: value, child: Text(value))).toList(growable: false),
              onChanged: onAssistantModeChanged,
            ),
            const SizedBox(height: 10),
            SwitchListTile.adaptive(contentPadding: EdgeInsets.zero, value: room.fistBumpsEnabled, onChanged: onFistBumpsChanged, title: const Text('Enable fist bumps')),
            const SizedBox(height: 12),
            Wrap(spacing: 10, runSpacing: 10, children: <Widget>[
              if (onClearVotes != null) OutlinedButton(onPressed: busy ? null : onClearVotes, child: const Text('Clear fist bumps')),
              if (onCloseRoom != null) FilledButton(onPressed: busy ? null : onCloseRoom, child: const Text('Close room')),
            ]),
          ],
        ),
      ),
    );
  }
}
