import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/deep_links/invite_links.dart';
import '../../../core/models/session_models.dart';
import '../../../core/network/api_client.dart';
import '../../../core/presentation/gradient_scaffold.dart';
import '../../../core/storage/session_repository.dart';

class JoinRoomScreen extends ConsumerStatefulWidget {
  const JoinRoomScreen({
    super.key,
    this.initialServer,
    this.initialSlug,
  });

  final String? initialServer;
  final String? initialSlug;

  @override
  ConsumerState<JoinRoomScreen> createState() => _JoinRoomScreenState();
}

class _JoinRoomScreenState extends ConsumerState<JoinRoomScreen> {
  final ApiClient _api = ApiClient();
  final TextEditingController _serverController = TextEditingController();
  final TextEditingController _inviteController = TextEditingController();
  final TextEditingController _displayNameController = TextEditingController(text: 'Guest');
  bool _submitting = false;

  @override
  void initState() {
    super.initState();
    _serverController.text = widget.initialServer ?? '';
    _inviteController.text = widget.initialSlug ?? '';
    ref.read(sessionRepositoryProvider).loadActiveServer().then((Uri? server) {
      if (!mounted || _serverController.text.isNotEmpty || server == null) {
        return;
      }
      setState(() {
        _serverController.text = server.toString();
      });
    });
  }

  @override
  void dispose() {
    _serverController.dispose();
    _inviteController.dispose();
    _displayNameController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    setState(() {
      _submitting = true;
    });

    try {
      final InviteLink? invite = InviteLink.parse(_inviteController.text);
      final Uri server = invite?.server ?? normalizeServerUri(_serverController.text);
      final String slug = invite?.slug ?? _inviteController.text.trim();
      if (slug.isEmpty) {
        throw const FormatException('Room slug is required.');
      }

      final result = await _api.joinRoom(
        server: server,
        slug: slug,
        displayName: _displayNameController.text.trim(),
      );
      await ref.read(sessionRepositoryProvider).saveSession(
            server: server,
            slug: result.room.slug,
            session: result.session,
          );

      if (!mounted) {
        return;
      }
      context.goNamed(
        'room',
        queryParameters: <String, String>{
          'server': server.toString(),
          'slug': result.room.slug,
        },
      );
    } catch (error) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Unable to join room: $error')),
      );
    } finally {
      if (mounted) {
        setState(() {
          _submitting = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return GradientScaffold(
      title: 'Join a room',
      subtitle: 'Paste a custom mobile invite or enter the room slug directly with the self-hosted server URL.',
      actions: <Widget>[
        IconButton(
          onPressed: () => context.goNamed('landing'),
          icon: const Icon(Icons.close),
        ),
      ],
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(22),
          child: Column(
            children: <Widget>[
              TextField(
                controller: _serverController,
                decoration: const InputDecoration(
                  labelText: 'Self-hosted server URL',
                  hintText: 'https://boards.example.com',
                ),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _inviteController,
                decoration: const InputDecoration(
                  labelText: 'Invite or room slug',
                  hintText: 'kiltertogether://join?... or room-slug',
                ),
                minLines: 1,
                maxLines: 2,
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _displayNameController,
                decoration: const InputDecoration(labelText: 'Display name'),
              ),
              const SizedBox(height: 18),
              SizedBox(
                width: double.infinity,
                child: FilledButton(
                  onPressed: _submitting ? null : _submit,
                  child: Text(_submitting ? 'Joining room...' : 'Join room'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

