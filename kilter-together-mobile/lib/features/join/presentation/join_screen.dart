import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mobile_scanner/mobile_scanner.dart';
import 'package:go_router/go_router.dart';

import '../../../core/deep_links/invite_links.dart';
import '../../../core/models/session_models.dart';
import '../../../core/network/api_client.dart';
import '../../../core/presentation/gradient_scaffold.dart';
import '../../../core/storage/app_prefs_controller.dart';
import '../../../core/storage/session_repository.dart';

class JoinRoomScreen extends ConsumerStatefulWidget {
  const JoinRoomScreen({
    super.key,
    this.initialServer,
    this.initialSlug,
    this.initialReason,
  });

  final String? initialServer;
  final String? initialSlug;
  final String? initialReason;

  @override
  ConsumerState<JoinRoomScreen> createState() => _JoinRoomScreenState();
}

class _JoinRoomScreenState extends ConsumerState<JoinRoomScreen> {
  final ApiClient _api = ApiClient();
  final TextEditingController _serverController = TextEditingController();
  final TextEditingController _inviteController = TextEditingController();
  final TextEditingController _displayNameController = TextEditingController(text: 'Guest');
  bool _submitting = false;
  String? _inlineError;
  bool _scannerOpen = false;

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
    ref.read(appPrefsControllerProvider.notifier).refresh().then((_) {
      final AsyncValue<dynamic> prefsValue = ref.read(appPrefsControllerProvider);
      final dynamic prefs = prefsValue.valueOrNull;
      if (!mounted || prefs == null) {
        return;
      }
      if ((prefs.savedDisplayName as String?)?.trim().isNotEmpty == true) {
        setState(() {
          _displayNameController.text = prefs.savedDisplayName as String;
        });
      }
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
      _inlineError = null;
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
      await ref.read(appPrefsControllerProvider.notifier).rememberDisplayName(
            _displayNameController.text.trim(),
          );
      await ref.read(appPrefsControllerProvider.notifier).rememberRoomVisit(
            server: server,
            room: result.room,
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
      final String message = '$error';
      setState(() {
        _inlineError = message;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Unable to join room: $message')),
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
    final String? joinReason = widget.initialReason;
    final String? joinReasonMessage = switch (joinReason) {
      'session_expired' => 'Your last room session on this device expired. Rejoin the room to continue.',
      'session_invalid' => 'This device does not have a valid room session for the room. Rejoin to continue.',
      'session_required' => 'Join the room on this device before opening the invite.',
      _ => null,
    };

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
              const SizedBox(height: 12),
              if (joinReasonMessage != null)
                Container(
                  width: double.infinity,
                  decoration: BoxDecoration(
                    color: const Color(0xFFFEF3C7),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  padding: const EdgeInsets.all(14),
                  child: Text(joinReasonMessage),
                ),
              if (_inlineError != null) ...<Widget>[
                const SizedBox(height: 12),
                Container(
                  width: double.infinity,
                  decoration: BoxDecoration(
                    color: const Color(0xFFFEE2E2),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  padding: const EdgeInsets.all(14),
                  child: Text(_inlineError!),
                ),
              ],
              const SizedBox(height: 18),
              SizedBox(
                width: double.infinity,
                child: FilledButton(
                  onPressed: _submitting ? null : _submit,
                  child: Text(_submitting ? 'Joining room...' : 'Join room'),
                ),
              ),
              const SizedBox(height: 10),
              SizedBox(
                width: double.infinity,
                child: OutlinedButton.icon(
                  onPressed: () => setState(() => _scannerOpen = !_scannerOpen),
                  icon: Icon(_scannerOpen ? Icons.qr_code_2 : Icons.qr_code_scanner),
                  label: Text(_scannerOpen ? 'Hide QR scanner' : 'Scan host QR'),
                ),
              ),
              if (_scannerOpen) ...<Widget>[
                const SizedBox(height: 12),
                _InviteScanner(
                  onDetected: (InviteLink invite) {
                    setState(() {
                      _serverController.text = invite.server.toString();
                      if ((invite.slug ?? '').isNotEmpty) {
                        _inviteController.text = invite.slug!;
                      } else {
                        _inviteController.text = invite.toUri().toString();
                      }
                      _scannerOpen = false;
                    });
                  },
                  onError: (String message) {
                    setState(() {
                      _inlineError = message;
                    });
                  },
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _InviteScanner extends StatefulWidget {
  const _InviteScanner({
    required this.onDetected,
    required this.onError,
  });

  final ValueChanged<InviteLink> onDetected;
  final ValueChanged<String> onError;

  @override
  State<_InviteScanner> createState() => _InviteScannerState();
}

class _InviteScannerState extends State<_InviteScanner> {
  bool _handled = false;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 260,
      child: ClipRRect(
        borderRadius: BorderRadius.circular(24),
        child: MobileScanner(
          onDetect: (BarcodeCapture capture) {
            if (_handled) {
              return;
            }
            final List<Barcode> barcodes = capture.barcodes;
            if (barcodes.isEmpty) {
              return;
            }
            final String? rawValue = barcodes.first.rawValue;
            if (rawValue == null || rawValue.trim().isEmpty) {
              return;
            }
            final InviteLink? invite = InviteLink.parse(rawValue);
            if (invite == null || invite.kind != InviteKind.join || (invite.slug ?? '').isEmpty) {
              widget.onError('That QR code is not a supported room invite.');
              return;
            }
            _handled = true;
            widget.onDetected(invite);
          },
        ),
      ),
    );
  }
}
