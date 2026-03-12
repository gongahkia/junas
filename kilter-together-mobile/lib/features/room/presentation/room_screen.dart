import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:wakelock_plus/wakelock_plus.dart';

import '../../../core/models/room_models.dart';
import '../../../core/models/session_models.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/sse_client.dart';
import '../../../core/presentation/gradient_scaffold.dart';
import '../../../core/storage/session_repository.dart';

class RoomScreen extends ConsumerStatefulWidget {
  const RoomScreen({
    super.key,
    required this.server,
    required this.slug,
  });

  final String server;
  final String slug;

  @override
  ConsumerState<RoomScreen> createState() => _RoomScreenState();
}

class _RoomScreenState extends ConsumerState<RoomScreen> {
  final ApiClient _api = ApiClient();
  final SseClient _sseClient = SseClient();

  RoomSnapshot? _room;
  RoomSession? _session;
  String? _error;
  StreamSubscription<SseMessage>? _subscription;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    WakelockPlus.enable();
    unawaited(_bootstrap());
  }

  @override
  void dispose() {
    _subscription?.cancel();
    WakelockPlus.disable();
    super.dispose();
  }

  Future<void> _bootstrap() async {
    try {
      final Uri server = normalizeServerUri(widget.server);
      final RoomSession? session = await ref.read(sessionRepositoryProvider).readSession(
            server: server,
            slug: widget.slug,
          );
      if (session == null) {
        setState(() {
          _error = 'No saved room session is available on this device. Rejoin the room.';
          _loading = false;
        });
        return;
      }

      final RoomSnapshot room = await _api.getRoom(
        server: server,
        slug: widget.slug,
        sessionToken: session.token,
      );

      if (!mounted) {
        return;
      }
      setState(() {
        _session = session;
        _room = room;
        _error = null;
        _loading = false;
      });

      await _subscription?.cancel();
      _subscription = _sseClient
          .connect(
            uri: _api.getRoomEventsUri(server: server, slug: widget.slug),
            sessionToken: session.token,
          )
          .listen((SseMessage _) {
        unawaited(_refresh(silent: true));
      });
    } catch (error) {
      if (!mounted) {
        return;
      }
      setState(() {
        _error = '$error';
        _loading = false;
      });
    }
  }

  Future<void> _refresh({bool silent = false}) async {
    final RoomSession? session = _session;
    if (session == null) {
      return;
    }

    if (!silent && mounted) {
      setState(() {
        _loading = true;
      });
    }

    try {
      final Uri server = normalizeServerUri(widget.server);
      final RoomSnapshot room = await _api.getRoom(
        server: server,
        slug: widget.slug,
        sessionToken: session.token,
      );
      if (!mounted) {
        return;
      }
      setState(() {
        _room = room;
        _error = null;
        _loading = false;
      });
    } catch (error) {
      if (!mounted) {
        return;
      }
      setState(() {
        _error = '$error';
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final RoomSnapshot? room = _room;
    final RoomSnapshot? activeRoom = room;
    final TextTheme textTheme = Theme.of(context).textTheme;

    return GradientScaffold(
      title: room?.roomName ?? 'Room ${widget.slug}',
      subtitle: widget.server,
      actions: <Widget>[
        IconButton(
          onPressed: _loading ? null : () => unawaited(_refresh()),
          icon: const Icon(Icons.refresh),
        ),
      ],
      child: _loading
          ? const Center(child: Padding(padding: EdgeInsets.all(40), child: CircularProgressIndicator()))
          : _error != null
              ? Card(
                  child: Padding(
                    padding: const EdgeInsets.all(22),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Text('Room unavailable', style: textTheme.headlineMedium),
                        const SizedBox(height: 10),
                        Text(_error!),
                        const SizedBox(height: 18),
                        FilledButton.tonal(
                          onPressed: () => context.goNamed(
                            'join-room',
                            queryParameters: <String, String>{
                              'server': widget.server,
                              'slug': widget.slug,
                            },
                          ),
                          child: const Text('Rejoin room'),
                        ),
                      ],
                    ),
                  ),
                )
              : Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Card(
                      child: Padding(
                        padding: const EdgeInsets.all(22),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: <Widget>[
                            Text(
                              '${room?.providerId.toUpperCase() ?? ''} · ${room?.status.toUpperCase() ?? ''}',
                              style: textTheme.titleLarge,
                            ),
                            const SizedBox(height: 10),
                            Text('Viewer: ${room?.displayName ?? 'Unknown'}'),
                            if (activeRoom?.surface != null) ...<Widget>[
                              const SizedBox(height: 6),
                              Text('Surface: ${activeRoom!.surface!.name}'),
                            ],
                            if (activeRoom?.currentClimb != null) ...<Widget>[
                              const SizedBox(height: 14),
                              Text(
                                'Current climb',
                                style: textTheme.titleLarge,
                              ),
                              const SizedBox(height: 6),
                              Text(activeRoom!.currentClimb!.name),
                              if (activeRoom.currentClimb!.primaryGrade != null)
                                Text(activeRoom.currentClimb!.primaryGrade!),
                            ],
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(height: 14),
                    Card(
                      child: Padding(
                        padding: const EdgeInsets.all(22),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: <Widget>[
                            Text('Participants', style: textTheme.titleLarge),
                            const SizedBox(height: 10),
                            ...?activeRoom?.participants.map(
                              (Participant participant) => ListTile(
                                dense: true,
                                contentPadding: EdgeInsets.zero,
                                title: Text(participant.displayName),
                                subtitle: Text('${participant.role} · ${participant.status}'),
                                trailing: Icon(
                                  participant.isOnline ? Icons.circle : Icons.circle_outlined,
                                  size: 14,
                                  color: participant.isOnline ? const Color(0xFF0F766E) : const Color(0xFF94A3B8),
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(height: 14),
                    Card(
                      child: Padding(
                        padding: const EdgeInsets.all(22),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: <Widget>[
                            Text('Queue', style: textTheme.titleLarge),
                            const SizedBox(height: 10),
                            if (activeRoom?.queue.isEmpty ?? true)
                              const Text('No climbs are queued yet.')
                            else
                              ...activeRoom!.queue.map(
                                (QueueEntry entry) => ListTile(
                                  dense: true,
                                  contentPadding: EdgeInsets.zero,
                                  title: Text(entry.climb.name),
                                  subtitle: Text('${entry.status} · added by ${entry.addedBy}'),
                                  trailing: Text('#${entry.position}'),
                                ),
                              ),
                          ],
                        ),
                      ),
                    ),
                  ],
                ),
    );
  }
}
