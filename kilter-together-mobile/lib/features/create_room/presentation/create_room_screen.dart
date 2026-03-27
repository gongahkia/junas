import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:qr_flutter/qr_flutter.dart';

import '../../../core/deep_links/invite_links.dart';
import '../../../core/models/app_prefs_models.dart';
import '../../../core/p2p/host_room_controller.dart';
import '../../../core/presentation/app_surfaces.dart';
import '../../../core/presentation/gradient_scaffold.dart';
import '../../../core/storage/app_prefs_controller.dart';
import '../../../core/storage/session_repository.dart';
import '../../../core/theme/app_theme.dart';

class CreateRoomScreen extends ConsumerStatefulWidget {
  const CreateRoomScreen({super.key});

  @override
  ConsumerState<CreateRoomScreen> createState() => _CreateRoomScreenState();
}

class _CreateRoomScreenState extends ConsumerState<CreateRoomScreen> {
  final TextEditingController _roomNameController =
      TextEditingController(text: 'Evening Session');
  final TextEditingController _displayNameController =
      TextEditingController(text: 'Host');
  bool _fistBumpsEnabled = true;
  String _selectedProviderId = 'kilter';
  bool _creating = false;
  String? _inlineError;
  HostRoomArgs? _activeArgs;

  @override
  void initState() {
    super.initState();
    ref.read(sessionRepositoryProvider).loadAppPrefs().then((AppPrefs prefs) {
      if (!mounted) {
        return;
      }
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
    if (_roomNameController.text.trim().isEmpty) {
      return 'Enter a room name.';
    }
    if (_displayNameController.text.trim().isEmpty) {
      return 'Enter a display name.';
    }
    return null;
  }

  Future<void> _submit() async {
    final String? error = _validate();
    if (error != null) {
      setState(() {
        _inlineError = error;
      });
      return;
    }
    setState(() {
      _creating = true;
      _inlineError = null;
    });
    await ref.read(appPrefsControllerProvider.notifier).rememberDisplayName(
          _displayNameController.text.trim(),
        );
    await ref
        .read(appPrefsControllerProvider.notifier)
        .rememberLastProvider(_selectedProviderId);
    final HostRoomArgs args = HostRoomArgs(
      providerId: _selectedProviderId,
      roomName: _roomNameController.text.trim(),
      displayName: _displayNameController.text.trim(),
      fistBumpsEnabled: _fistBumpsEnabled,
    );
    setState(() {
      _activeArgs = args;
    });
  }

  @override
  Widget build(BuildContext context) {
    if (_activeArgs != null) {
      final HostRoomViewState hostState =
          ref.watch(hostRoomControllerProvider(_activeArgs!));
      if (hostState.hosting && hostState.room != null) {
        return _HostLobbyView(
          hostState: hostState,
          args: _activeArgs!,
          onEnterRoom: () {
            context.goNamed(
              'room',
              queryParameters: <String, String>{
                'slug': hostState.room!.slug,
                'role': 'host',
              },
            );
          },
        );
      }
      if (hostState.errorMessage != null) {
        return GradientScaffold(
          title: 'Create a room',
          subtitle:
              'Something blocked the host session before it finished booting.',
          child: AppPanel(
            accentColor: const Color(0xFF9B3445),
            child: Column(
              children: <Widget>[
                Text(hostState.errorMessage!),
                const SizedBox(height: 16),
                SizedBox(
                  width: double.infinity,
                  child: FilledButton(
                    onPressed: () {
                      setState(() {
                        _activeArgs = null;
                        _creating = false;
                      });
                    },
                    child: const Text('Back'),
                  ),
                ),
              ],
            ),
          ),
        );
      }
      return GradientScaffold(
        title: 'Create a room',
        subtitle:
            'Booting the host session and preparing the local room state.',
        child: const AppPanel(
          child: Padding(
            padding: EdgeInsets.symmetric(vertical: 22),
            child: Center(child: CircularProgressIndicator()),
          ),
        ),
      );
    }

    return GradientScaffold(
      title: 'Create a room',
      subtitle:
          'Host a P2P session and keep the control surface on one phone while everyone else connects in locally.',
      child: AppPanel(
        accentColor: _selectedProviderId == 'crux'
            ? const Color(0xFFC7682F)
            : const Color(0xFF23533F),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: <Widget>[
                AppBadge(
                  label: 'P2P host',
                  icon: Icons.router_outlined,
                  color: kilterPaletteOf(context).primary,
                ),
                AppBadge(
                  label: _selectedProviderId.toUpperCase(),
                  icon: Icons.terrain_rounded,
                  color: _selectedProviderId == 'crux'
                      ? kilterPaletteOf(context).highlight
                      : kilterPaletteOf(context).secondary,
                ),
              ],
            ),
            if (_inlineError != null) ...<Widget>[
              const SizedBox(height: 18),
              AppPanel(
                padding: const EdgeInsets.all(16),
                accentColor: const Color(0xFF9B3445),
                backgroundColor: const Color(0xFFFFF4F5),
                child: Text(_inlineError!),
              ),
            ],
            const SizedBox(height: 18),
            Text(
              'Room details',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _roomNameController,
              decoration: const InputDecoration(labelText: 'Room name'),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _displayNameController,
              decoration: const InputDecoration(labelText: 'Host display name'),
            ),
            const SizedBox(height: 18),
            Text(
              'Board provider',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 12),
            SegmentedButton<String>(
              multiSelectionEnabled: false,
              emptySelectionAllowed: false,
              showSelectedIcon: false,
              segments: const <ButtonSegment<String>>[
                ButtonSegment<String>(
                  value: 'kilter',
                  icon: Icon(Icons.grid_view_rounded),
                  label: Text('Kilter'),
                ),
                ButtonSegment<String>(
                  value: 'crux',
                  icon: Icon(Icons.layers_outlined),
                  label: Text('Crux'),
                ),
              ],
              selected: <String>{_selectedProviderId},
              onSelectionChanged: (Set<String> selection) {
                final String providerId = selection.first;
                setState(() {
                  _selectedProviderId = providerId;
                });
              },
            ),
            const SizedBox(height: 18),
            SwitchListTile.adaptive(
              contentPadding: EdgeInsets.zero,
              title: const Text('Enable fist bumps'),
              subtitle: const Text(
                'Keep vote-style reactions active when the room opens.',
              ),
              value: _fistBumpsEnabled,
              onChanged: (bool value) {
                setState(() {
                  _fistBumpsEnabled = value;
                });
              },
            ),
            const SizedBox(height: 18),
            SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                onPressed: _creating ? null : _submit,
                icon: Icon(
                  _creating
                      ? Icons.motion_photos_pause_rounded
                      : Icons.launch_rounded,
                ),
                label: Text(_creating ? 'Starting room' : 'Create room'),
              ),
            ),
          ],
        ),
      ),
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
    final KilterPalette palette = kilterPaletteOf(context);
    final String slug = hostState.room!.slug;
    final String inviteUri = InviteLink(
      kind: InviteKind.join,
      slug: slug,
    ).toUri().toString();
    final int peerCount = hostState.room!.participants.length;

    return GradientScaffold(
      title: 'Room created',
      subtitle:
          'Your invite is ready. Keep this phone nearby so guests can connect directly over the local P2P transport.',
      child: AppPanel(
        accentColor: palette.primary,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: <Widget>[
                AppBadge(
                  label: args.providerId.toUpperCase(),
                  icon: Icons.terrain_rounded,
                  color: palette.secondary,
                ),
                AppBadge(
                  label: 'Code $slug',
                  icon: Icons.password_rounded,
                  color: palette.highlight,
                ),
              ],
            ),
            const SizedBox(height: 18),
            Text(
              args.roomName,
              style: Theme.of(context).textTheme.headlineMedium,
            ),
            const SizedBox(height: 10),
            Text(
              '$peerCount participant${peerCount == 1 ? '' : 's'} connected. Share the QR code while guests are gathering at the board.',
            ),
            const SizedBox(height: 24),
            Center(
              child: DecoratedBox(
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(28),
                  border: Border.all(color: palette.stroke),
                ),
                child: Padding(
                  padding: const EdgeInsets.all(18),
                  child: QrImageView(
                    data: inviteUri,
                    size: 210,
                    eyeStyle: QrEyeStyle(
                      color: palette.ink,
                      eyeShape: QrEyeShape.square,
                    ),
                    dataModuleStyle: QrDataModuleStyle(
                      color: palette.ink,
                      dataModuleShape: QrDataModuleShape.square,
                    ),
                  ),
                ),
              ),
            ),
            const SizedBox(height: 24),
            SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                onPressed: onEnterRoom,
                icon: const Icon(Icons.arrow_forward_rounded),
                label: const Text('Enter room'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
