import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

import '../../../core/deep_links/invite_links.dart';
import '../../../core/models/app_prefs_models.dart';
import '../../../core/models/session_models.dart';
import '../../../core/network/api_client.dart';
import '../../../core/presentation/feedback_prompt_card.dart';
import '../../../core/presentation/flow_guide_sheet.dart';
import '../../../core/presentation/gradient_scaffold.dart';
import '../../../core/storage/app_prefs_controller.dart';
import '../../../core/storage/session_repository.dart';

const FlowGuideContent _guestGuide = FlowGuideContent(
  eyebrow: 'Guest guide',
  title: 'Join the shared room from this phone',
  summary:
      'Guest phones only need the invite and display name. The host phone owns provider authentication and shared room setup.',
  sections: <FlowGuideSection>[
    FlowGuideSection(
      title: 'Use the invite first',
      body:
          'Paste the full invite or scan the host QR code so the phone gets both the room slug and the correct self-hosted server address.',
    ),
    FlowGuideSection(
      title: 'Keep your display name stable',
      body:
          'The app remembers the last display name on this device so rejoining the same room later feels consistent for the rest of the group.',
    ),
    FlowGuideSection(
      title: 'Participate inside the room',
      body:
          'Once inside, set your own status, vote, add climbs to queue or finalists, and follow the host-managed surface and session controls.',
    ),
  ],
  completionLabel: 'Mark guest guide complete',
);

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
  final TextEditingController _serverController = TextEditingController();
  final TextEditingController _inviteController = TextEditingController();
  final TextEditingController _displayNameController =
      TextEditingController(text: 'Guest');

  bool _submitting = false;
  bool _scannerOpen = false;
  bool _showFailureFeedback = false;
  bool _autoGuideAttempted = false;
  String? _inlineError;

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
    ref.read(sessionRepositoryProvider).loadAppPrefs().then((AppPrefs prefs) {
      if (!mounted) {
        return;
      }
      if (prefs.savedDisplayName.trim().isNotEmpty) {
        setState(() {
          _displayNameController.text = prefs.savedDisplayName.trim();
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

  void _maybeAutoOpenGuide(AppPrefs prefs) {
    if (_autoGuideAttempted ||
        !prefs.settings.autoGuidesEnabled ||
        prefs.guidedTour.activeBranch != 'guest' ||
        prefs.guidedTour.guestCompleted) {
      return;
    }
    _autoGuideAttempted = true;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) {
        return;
      }
      unawaited(_openGuide());
    });
  }

  Future<void> _openGuide() async {
    final AppPrefs prefs =
        ref.read(appPrefsControllerProvider).valueOrNull ?? AppPrefs.defaults();
    final FlowGuideResult? result = await showFlowGuideSheet(
      context: context,
      content: _guestGuide,
      completed: prefs.guidedTour.guestCompleted,
    );
    if (result != FlowGuideResult.completed || !mounted) {
      return;
    }
    await ref.read(appPrefsControllerProvider.notifier).completeGuideBranch(
          'guest',
        );
  }

  Future<void> _dismissFailureFeedback() async {
    await ref
        .read(appPrefsControllerProvider.notifier)
        .markFeedbackPromptSeen('room-join-failure');
    if (!mounted) {
      return;
    }
    setState(() {
      _showFailureFeedback = false;
    });
  }

  Future<void> _submit() async {
    setState(() {
      _submitting = true;
      _inlineError = null;
      _showFailureFeedback = false;
    });

    try {
      final InviteLink? invite = InviteLink.parse(_inviteController.text);
      final Uri server =
          invite?.server ?? normalizeServerUri(_serverController.text);
      final String slug = invite?.slug ?? _inviteController.text.trim();
      if (slug.isEmpty) {
        throw const FormatException('Room slug is required.');
      }

      final result = await ref.read(apiClientProvider).joinRoom(
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
    } on ApiFailure catch (error) {
      final bool shouldShowFeedback = await ref
          .read(appPrefsControllerProvider.notifier)
          .shouldShowFeedbackPrompt('room-join-failure');
      if (!mounted) {
        return;
      }
      setState(() {
        _inlineError = error.message;
        _showFailureFeedback = shouldShowFeedback;
      });
      _showSnack('Unable to join room: ${error.message}');
    } catch (error) {
      if (!mounted) {
        return;
      }
      setState(() {
        _inlineError = '$error';
      });
      _showSnack('Unable to join room: $error');
    } finally {
      if (mounted) {
        setState(() {
          _submitting = false;
        });
      }
    }
  }

  void _showSnack(String message) {
    ScaffoldMessenger.of(context)
        .showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  Widget build(BuildContext context) {
    final AsyncValue<AppPrefs> prefsValue =
        ref.watch(appPrefsControllerProvider);
    final AppPrefs prefs = prefsValue.valueOrNull ?? AppPrefs.defaults();
    final String? joinReason = widget.initialReason;
    final String? joinReasonMessage = switch (joinReason) {
      'session_expired' =>
        'Your last room session on this device expired. Rejoin the room to continue.',
      'session_invalid' =>
        'This device does not have a valid room session for the room. Rejoin to continue.',
      'session_required' =>
        'Join the room on this device before opening the invite.',
      _ => null,
    };

    if (prefsValue.hasValue) {
      _maybeAutoOpenGuide(prefs);
    }

    return GradientScaffold(
      title: 'Join a room',
      subtitle:
          'Paste a custom mobile invite or enter the room slug directly with the self-hosted server URL.',
      actions: <Widget>[
        IconButton(
          onPressed: () => unawaited(_openGuide()),
          icon: const Icon(Icons.help_outline),
        ),
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
                  icon: Icon(
                      _scannerOpen ? Icons.qr_code_2 : Icons.qr_code_scanner),
                  label:
                      Text(_scannerOpen ? 'Hide QR scanner' : 'Scan host QR'),
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
              if (_showFailureFeedback) ...<Widget>[
                const SizedBox(height: 18),
                FeedbackPromptCard(
                  title: 'Was the join failure useful?',
                  description:
                      'A quick signal helps tighten invite parsing, rejoin recovery, and server messaging on mobile.',
                  onDismiss: () => unawaited(_dismissFailureFeedback()),
                  onSubmit: (String sentiment, String? message) async {
                    await ref.read(apiClientProvider).submitFeedback(
                      server: normalizeServerUri(_serverController.text.trim()),
                      promptFamily: 'room-join-failure',
                      sentiment: sentiment,
                      message: message,
                      route: '/join',
                      metadata: <String, dynamic>{
                        'reason': joinReason ?? '',
                      },
                    );
                    await _dismissFailureFeedback();
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
            if (invite == null ||
                invite.kind != InviteKind.join ||
                (invite.slug ?? '').isEmpty) {
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
