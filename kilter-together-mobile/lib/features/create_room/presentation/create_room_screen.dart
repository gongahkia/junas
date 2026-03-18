import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:qr_flutter/qr_flutter.dart';
import '../../../core/deep_links/invite_links.dart';
import '../../../core/models/app_prefs_models.dart';
import '../../../core/p2p/host_room_controller.dart';
import '../../../core/presentation/gradient_scaffold.dart';
import '../../../core/storage/app_prefs_controller.dart';
import '../../../core/storage/session_repository.dart';

class CreateRoomScreen extends ConsumerStatefulWidget {
  const CreateRoomScreen({super.key});
  @override
  ConsumerState<CreateRoomScreen> createState() => _CreateRoomScreenState();
}

class _CreateRoomScreenState extends ConsumerState<CreateRoomScreen> {
  final TextEditingController _roomNameController = TextEditingController(text: 'Evening Session');
  final TextEditingController _displayNameController = TextEditingController(text: 'Host');
  bool _fistBumpsEnabled = true;
  String _selectedProviderId = 'kilter';
  bool _creating = false;
  String? _inlineError;
  HostRoomArgs? _activeArgs;

  @override
  void initState() {
    super.initState();
    ref.read(sessionRepositoryProvider).loadAppPrefs().then((AppPrefs prefs) {
      if (!mounted) return;
      setState(() {
        if (prefs.savedDisplayName.trim().isNotEmpty) {
          _displayNameController.text = prefs.savedDisplayName.trim();
        }
        final String resolvedRoomName = ref
            .read(appPrefsControllerProvider.notifier)
            .resolveHostRoomNameTemplate(prefs.hostDefaults.roomNameTemplate);
        if (resolvedRoomName.isNotEmpty) {
          _roomNameController.text = resolvedRoomName;
        }
        _fistBumpsEnabled = prefs.hostDefaults.defaultFistBumpsEnabled;
        if (prefs.lastProviderId.isNotEmpty) {
          _selectedProviderId = prefs.lastProviderId;
        }
      });
    });
  }

  @override
  void dispose() {
    _roomNameController.dispose();
    _displayNameController.dispose();
    super.dispose();
  }

  String? _validate() {
    if (_roomNameController.text.trim().isEmpty) return 'Enter a room name.';
    if (_displayNameController.text.trim().isEmpty) return 'Enter a display name.';
    return null;
  }

  Future<void> _submit() async {
    final String? error = _validate();
    if (error != null) {
      setState(() => _inlineError = error);
      return;
    }
    setState(() { _creating = true; _inlineError = null; });
    await ref.read(appPrefsControllerProvider.notifier).rememberDisplayName(
      _displayNameController.text.trim(),
    );
    await ref.read(appPrefsControllerProvider.notifier).rememberLastProvider(_selectedProviderId);
    final HostRoomArgs args = HostRoomArgs(
      providerId: _selectedProviderId,
      roomName: _roomNameController.text.trim(),
      displayName: _displayNameController.text.trim(),
      fistBumpsEnabled: _fistBumpsEnabled,
    );
    setState(() { _activeArgs = args; });
  }

  @override
  Widget build(BuildContext context) {
    if (_activeArgs != null) {
      final HostRoomViewState hostState = ref.watch(hostRoomControllerProvider(_activeArgs!));
      if (hostState.hosting && hostState.room != null) {
        return _HostLobbyView(
          hostState: hostState,
          args: _activeArgs!,
          onEnterRoom: () {
            context.goNamed('room', queryParameters: <String, String>{
              'slug': hostState.room!.slug,
              'role': 'host',
            });
          },
        );
      }
      if (hostState.errorMessage != null) {
        return GradientScaffold(
          title: 'Create a room',
          child: Card(child: Padding(
            padding: const EdgeInsets.all(22),
            child: Column(children: <Widget>[
              Text(hostState.errorMessage!),
              const SizedBox(height: 16),
              FilledButton(onPressed: () => setState(() { _activeArgs = null; _creating = false; }),
                child: const Text('Back')),
            ]),
          )),
        );
      }
      return GradientScaffold(
        title: 'Create a room',
        child: const Card(child: Padding(
          padding: EdgeInsets.all(32),
          child: Center(child: CircularProgressIndicator()),
        )),
      );
    }
    return GradientScaffold(
      title: 'Create a room',
      subtitle: 'Host a P2P session. Nearby phones connect directly — no server needed.',
      child: Card(child: Padding(
        padding: const EdgeInsets.all(22),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: <Widget>[
          if (_inlineError != null) ...<Widget>[
            Container(
              width: double.infinity,
              decoration: BoxDecoration(
                color: const Color(0xFFF0F0F0),
                border: Border.all(color: const Color(0xFFD4D4D4)),
              ),
              padding: const EdgeInsets.all(16),
              child: Text(_inlineError!),
            ),
            const SizedBox(height: 18),
          ],
          TextField(
            controller: _roomNameController,
            decoration: const InputDecoration(labelText: 'Room name'),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _displayNameController,
            decoration: const InputDecoration(labelText: 'Host display name'),
          ),
          const SizedBox(height: 12),
          DropdownButtonFormField<String>(
            initialValue: _selectedProviderId,
            decoration: const InputDecoration(labelText: 'Provider'),
            items: const <DropdownMenuItem<String>>[
              DropdownMenuItem<String>(value: 'kilter', child: Text('Kilter')),
              DropdownMenuItem<String>(value: 'crux', child: Text('Crux')),
            ],
            onChanged: (String? v) { if (v != null) setState(() => _selectedProviderId = v); },
          ),
          const SizedBox(height: 12),
          SwitchListTile.adaptive(
            contentPadding: EdgeInsets.zero,
            title: const Text('Enable fist bumps'),
            value: _fistBumpsEnabled,
            onChanged: (bool v) => setState(() => _fistBumpsEnabled = v),
          ),
          const SizedBox(height: 18),
          SizedBox(width: double.infinity, child: FilledButton(
            onPressed: _creating ? null : _submit,
            child: Text(_creating ? 'Starting...' : 'Create room'),
          )),
        ]),
      )),
    );
  }
}

class _HostLobbyView extends StatelessWidget {
  const _HostLobbyView({
    required this.hostState,
    required this.args,
    required this.onEnterRoom,
  });
  final HostRoomViewState hostState;
  final HostRoomArgs args;
  final VoidCallback onEnterRoom;

  @override
  Widget build(BuildContext context) {
    final String slug = hostState.room!.slug;
    final String inviteUri = InviteLink(
      kind: InviteKind.join,
      slug: slug,
    ).toUri().toString();
    final int peerCount = hostState.room!.participants.length;
    return GradientScaffold(
      title: 'Room created',
      subtitle: 'Share the QR code or invite link. Guests connect directly via Bluetooth/WiFi.',
      child: Card(child: Padding(
        padding: const EdgeInsets.all(22),
        child: Column(children: <Widget>[
          Text(args.roomName, style: Theme.of(context).textTheme.headlineMedium),
          const SizedBox(height: 8),
          Text('Room code: $slug'),
          const SizedBox(height: 16),
          Center(child: QrImageView(data: inviteUri, size: 200)),
          const SizedBox(height: 16),
          Text('$peerCount participant${peerCount == 1 ? '' : 's'} connected'),
          const SizedBox(height: 24),
          SizedBox(width: double.infinity, child: FilledButton(
            onPressed: onEnterRoom,
            child: const Text('Enter room'),
          )),
        ]),
      )),
    );
  }
}
