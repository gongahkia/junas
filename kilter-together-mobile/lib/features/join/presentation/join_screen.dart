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

InviteLink? _tryParseInvite(String raw) {
  try {
    return InviteLink.parse(raw);
  } on FormatException {
    return null;
  }
}

RoomJoinTarget? _tryParseJoinTarget(
  String raw, {
  Uri? fallbackServer,
}) {
  try {
    return parseRoomJoinTarget(raw, fallbackServer: fallbackServer);
  } on FormatException {
    return null;
  }
}

String _describeInviteKind(InviteKind kind) {
  return switch (kind) {
    InviteKind.join => 'room invite',
    InviteKind.recap => 'recap',
    InviteKind.plan => 'plan',
  };
}

String _scannerErrorMessage(MobileScannerException error) {
  return switch (error.errorCode) {
    MobileScannerErrorCode.permissionDenied =>
      'Camera access was denied. Paste the invite instead, or enable camera access and try again.',
    MobileScannerErrorCode.unsupported =>
      'This device cannot open the camera for QR scanning. Paste the invite or enter the server and room slug manually.',
    _ =>
      'The camera could not start for QR scanning. Paste the invite or enter the room slug manually.',
  };
}

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

  String? _validateJoinSubmission() {
    final String displayName = _displayNameController.text.trim();
    if (displayName.isEmpty) {
      return 'Enter a display name before joining the room.';
    }

    final String rawInvite = _inviteController.text.trim();
    if (rawInvite.isEmpty) {
      return 'Paste the room invite or enter the room slug.';
    }

    final InviteLink? invite = _tryParseInvite(rawInvite);
    if (invite != null) {
      if (invite.kind != InviteKind.join) {
        return 'That link opens a ${_describeInviteKind(invite.kind)}, not a room invite. Ask the host for the room invite instead.';
      }
      if ((invite.slug ?? '').trim().isEmpty) {
        return 'That room invite is missing the room slug. Ask the host to resend it, or enter the slug and server manually.';
      }
      return null;
    }

    final RoomJoinTarget? absoluteJoinTarget = _tryParseJoinTarget(rawInvite);
    if (absoluteJoinTarget != null) {
      if (absoluteJoinTarget.server != null) {
        return null;
      }
    }

    final String rawServer = _serverController.text.trim();
    if (rawServer.isEmpty) {
      return 'Enter the self-hosted server URL or paste a full room invite.';
    }

    final Uri fallbackServer;
    try {
      fallbackServer = normalizeServerUri(rawServer);
    } on FormatException {
      return 'Enter a valid self-hosted server URL or paste a full room invite.';
    }

    final RoomJoinTarget? joinTarget = _tryParseJoinTarget(
      rawInvite,
      fallbackServer: fallbackServer,
    );
    if (joinTarget != null && joinTarget.server != null) {
      return null;
    }

    if (rawInvite.contains('://') || rawInvite.startsWith('kiltertogether:')) {
      return 'That invite is malformed or unsupported. Paste a room invite, a web join link, or enter the room slug and server manually.';
    }

    return 'Paste a room invite, a web join link, or enter the room slug and server manually.';
  }

  ({Uri server, String slug}) _resolveJoinTarget() {
    final String rawInvite = _inviteController.text.trim();
    final RoomJoinTarget? inviteTarget = _tryParseJoinTarget(rawInvite);
    if (inviteTarget != null && inviteTarget.server != null) {
      return (
        server: inviteTarget.server!,
        slug: inviteTarget.slug,
      );
    }
    final Uri fallbackServer = normalizeServerUri(_serverController.text);
    final RoomJoinTarget? joinTarget = _tryParseJoinTarget(
      rawInvite,
      fallbackServer: fallbackServer,
    );
    if (joinTarget != null && joinTarget.server != null) {
      return (
        server: joinTarget.server!,
        slug: joinTarget.slug,
      );
    }
    return (
      server: fallbackServer,
      slug: rawInvite,
    );
  }

  String _formatJoinFailure(ApiFailure error) {
    return switch (error.code) {
      'display_name_taken' =>
        'That display name is already taken in this room. Choose another name and try again.',
      'room_closed' =>
        'This room is already closed. Ask the host for a new invite if the session is still happening.',
      'room_not_found' =>
        'That room could not be found on this server. Check the invite or room slug and try again.',
      'session_expired' =>
        'The saved room session on this device expired. Rejoin from the invite to continue.',
      'session_invalid' =>
        'This device does not have a valid room session for that room. Rejoin from the invite to continue.',
      'session_required' =>
        'Join the room on this device before opening it here.',
      'rate_limited' =>
        'Too many join attempts were sent. Wait a moment and try again.',
      _ => error.message,
    };
  }

  Future<void> _submit() async {
    final String? validationError = _validateJoinSubmission();
    if (validationError != null) {
      setState(() {
        _inlineError = validationError;
        _showFailureFeedback = false;
      });
      _showSnack(validationError);
      return;
    }

    setState(() {
      _submitting = true;
      _inlineError = null;
      _showFailureFeedback = false;
    });

    try {
      final ({Uri server, String slug}) joinTarget = _resolveJoinTarget();
      final Uri server = joinTarget.server;
      final String slug = joinTarget.slug;
      _serverController.text = server.toString();
      _inviteController.text = slug;

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
      final String message = _formatJoinFailure(error);
      if (!mounted) {
        return;
      }
      setState(() {
        _inlineError = message;
        _showFailureFeedback = shouldShowFeedback;
      });
      _showSnack('Unable to join room: $message');
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
          'Paste a mobile invite, a web join link, or the room slug directly with the self-hosted server URL.',
      actions: <Widget>[
        IconButton(
          onPressed: () => unawaited(_openGuide()),
          icon: const Icon(Icons.help_outline),
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
                  hintText:
                      'kiltertogether://join?... / https://.../join/... / room-slug',
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
                  onDetected: (RoomJoinTarget joinTarget) {
                    setState(() {
                      if (joinTarget.server != null) {
                        _serverController.text = joinTarget.server.toString();
                      }
                      _inviteController.text = joinTarget.slug;
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

  final ValueChanged<RoomJoinTarget> onDetected;
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
          errorBuilder: (BuildContext context, MobileScannerException error,
              Widget? child) {
            return Container(
              color: const Color(0xFF111827),
              padding: const EdgeInsets.all(20),
              child: Center(
                child: Text(
                  _scannerErrorMessage(error),
                  style: const TextStyle(color: Colors.white),
                  textAlign: TextAlign.center,
                ),
              ),
            );
          },
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
            final InviteLink? invite = _tryParseInvite(rawValue);
            if (invite != null && invite.kind != InviteKind.join) {
              widget.onError(
                'That QR code opens a ${_describeInviteKind(invite.kind)}, not a room invite.',
              );
              return;
            }

            final RoomJoinTarget? joinTarget = _tryParseJoinTarget(rawValue);
            if (joinTarget == null) {
              widget.onError(
                'That QR code is not a supported room invite.',
              );
              return;
            }
            if (joinTarget.server == null) {
              widget.onError(
                'That QR code does not include the server address. Paste a full invite or enter the server manually.',
              );
              return;
            }
            _handled = true;
            widget.onDetected(joinTarget);
          },
        ),
      ),
    );
  }
}
