import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/models/app_prefs_models.dart';
import '../../../core/models/provider_models.dart';
import '../../../core/models/session_models.dart';
import '../../../core/network/api_client.dart';
import '../../../core/presentation/feedback_prompt_card.dart';
import '../../../core/presentation/flow_guide_sheet.dart';
import '../../../core/presentation/gradient_scaffold.dart';
import '../../../core/storage/app_prefs_controller.dart';
import '../../../core/storage/session_repository.dart';

const FlowGuideContent _hostGuide = FlowGuideContent(
  eyebrow: 'Host guide',
  title: 'Open the room from this phone',
  summary:
      'Hosting means this device owns the provider connection, chooses the shared surface, and sends the invite to everyone else.',
  sections: <FlowGuideSection>[
    FlowGuideSection(
      title: 'Point at the right server',
      body:
          'Start with the self-hosted backend URL, then load providers from that server before picking which provider this room will use.',
    ),
    FlowGuideSection(
      title: 'Authenticate once',
      body:
          'Enter the provider credentials on the host phone only. Guests do not need those credentials in order to join, vote, or add climbs.',
    ),
    FlowGuideSection(
      title: 'Finish setup in the room',
      body:
          'After the room opens, set the shared surface, share the invite or QR code, and manage queue, finalists, and session controls from the room screen.',
    ),
  ],
  completionLabel: 'Mark host guide complete',
);

class CreateRoomScreen extends ConsumerStatefulWidget {
  const CreateRoomScreen({super.key});

  @override
  ConsumerState<CreateRoomScreen> createState() => _CreateRoomScreenState();
}

class _CreateRoomScreenState extends ConsumerState<CreateRoomScreen> {
  final TextEditingController _serverController = TextEditingController();
  final TextEditingController _roomNameController =
      TextEditingController(text: 'Evening Session');
  final TextEditingController _displayNameController =
      TextEditingController(text: 'Host');

  bool _loadingCapabilities = false;
  bool _submitting = false;
  bool _fistBumpsEnabled = true;
  bool _showFailureFeedback = false;
  bool _autoGuideAttempted = false;
  List<ProviderCapability> _capabilities = const <ProviderCapability>[];
  String? _selectedProviderId;
  String? _preferredProviderId;
  PendingRoomSeed? _pendingRoomSeed;
  String? _inlineError;
  final Map<String, TextEditingController> _secretControllers =
      <String, TextEditingController>{};

  @override
  void initState() {
    super.initState();
    ref.read(sessionRepositoryProvider).loadActiveServer().then((Uri? server) {
      if (!mounted || server == null) {
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
      final String resolvedRoomName = prefs.pendingRoomSeed?.title
                  ?.trim()
                  .isNotEmpty ==
              true
          ? prefs.pendingRoomSeed!.title!.trim()
          : ref
              .read(appPrefsControllerProvider.notifier)
              .resolveHostRoomNameTemplate(prefs.hostDefaults.roomNameTemplate);
      setState(() {
        if (prefs.savedDisplayName.trim().isNotEmpty) {
          _displayNameController.text = prefs.savedDisplayName.trim();
        }
        if (resolvedRoomName.isNotEmpty) {
          _roomNameController.text = resolvedRoomName;
        }
        _fistBumpsEnabled = prefs.hostDefaults.defaultFistBumpsEnabled;
        _preferredProviderId =
            prefs.pendingRoomSeed?.providerId ?? prefs.lastProviderId;
        _pendingRoomSeed = prefs.pendingRoomSeed;
      });
    });
  }

  @override
  void dispose() {
    _serverController.dispose();
    _roomNameController.dispose();
    _displayNameController.dispose();
    for (final TextEditingController controller in _secretControllers.values) {
      controller.dispose();
    }
    super.dispose();
  }

  ProviderCapability? get _selectedCapability {
    for (final ProviderCapability capability in _capabilities) {
      if (capability.id == _selectedProviderId) {
        return capability;
      }
    }
    return _capabilities.isEmpty ? null : _capabilities.first;
  }

  void _maybeAutoOpenGuide(AppPrefs prefs) {
    if (_autoGuideAttempted ||
        !prefs.settings.autoGuidesEnabled ||
        prefs.guidedTour.activeBranch != 'host' ||
        prefs.guidedTour.hostCompleted) {
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
      content: _hostGuide,
      completed: prefs.guidedTour.hostCompleted,
    );
    if (result != FlowGuideResult.completed || !mounted) {
      return;
    }
    await ref.read(appPrefsControllerProvider.notifier).completeGuideBranch(
          'host',
        );
  }

  Future<void> _dismissFailureFeedback() async {
    await ref
        .read(appPrefsControllerProvider.notifier)
        .markFeedbackPromptSeen('room-create-failure');
    if (!mounted) {
      return;
    }
    setState(() {
      _showFailureFeedback = false;
    });
  }

  Future<void> _loadCapabilities() async {
    setState(() {
      _loadingCapabilities = true;
      _inlineError = null;
    });

    try {
      final Uri server = normalizeServerUri(_serverController.text);
      final List<ProviderCapability> capabilities =
          await ref.read(apiClientProvider).getProviderCapabilities(server);
      final List<ProviderCapability> roomCapabilities = capabilities
          .where((ProviderCapability capability) => capability.roomSupported)
          .toList(growable: false);
      for (final TextEditingController controller
          in _secretControllers.values) {
        controller.dispose();
      }
      _secretControllers.clear();
      for (final ProviderCapability capability in roomCapabilities) {
        for (final ProviderAuthField field in capability.authFields) {
          _secretControllers.putIfAbsent(
            field.key,
            () => TextEditingController(),
          );
        }
      }

      setState(() {
        _capabilities = roomCapabilities;
        final String? preferredProviderId = _preferredProviderId;
        _selectedProviderId = roomCapabilities.any(
                (ProviderCapability item) => item.id == preferredProviderId)
            ? preferredProviderId
            : roomCapabilities.isEmpty
                ? null
                : roomCapabilities.first.id;
      });
    } catch (error) {
      _showSnack('Unable to load provider capabilities: $error');
      setState(() {
        _inlineError = '$error';
      });
    } finally {
      if (mounted) {
        setState(() {
          _loadingCapabilities = false;
        });
      }
    }
  }

  Future<void> _submit() async {
    final ProviderCapability? capability = _selectedCapability;
    if (capability == null) {
      _showSnack('Load providers before creating a room.');
      return;
    }

    setState(() {
      _submitting = true;
      _inlineError = null;
      _showFailureFeedback = false;
    });

    try {
      final Uri server = normalizeServerUri(_serverController.text);
      final Map<String, String> secret = <String, String>{
        for (final ProviderAuthField field in capability.authFields)
          field.key: _secretControllers[field.key]?.text.trim() ?? '',
      };
      final result = await ref.read(apiClientProvider).createRoom(
            server: server,
            providerId: capability.id,
            roomName: _roomNameController.text.trim(),
            displayName: _displayNameController.text.trim(),
            secret: secret,
            fistBumpsEnabled: _fistBumpsEnabled,
          );

      await ref.read(sessionRepositoryProvider).saveSession(
            server: server,
            slug: result.room.slug,
            session: result.session,
          );
      await ref.read(appPrefsControllerProvider.notifier).rememberDisplayName(
            _displayNameController.text.trim(),
          );
      await ref
          .read(appPrefsControllerProvider.notifier)
          .rememberLastProvider(capability.id);

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
          .shouldShowFeedbackPrompt('room-create-failure');
      _showSnack('Unable to create room: ${error.message}');
      if (!mounted) {
        return;
      }
      setState(() {
        _inlineError = error.message;
        _showFailureFeedback = shouldShowFeedback;
      });
    } catch (error) {
      _showSnack('Unable to create room: $error');
      if (!mounted) {
        return;
      }
      setState(() {
        _inlineError = '$error';
      });
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
    final ProviderCapability? capability = _selectedCapability;
    final AsyncValue<AppPrefs> prefsValue =
        ref.watch(appPrefsControllerProvider);
    final AppPrefs prefs = prefsValue.valueOrNull ?? AppPrefs.defaults();

    if (prefsValue.hasValue) {
      _maybeAutoOpenGuide(prefs);
    }

    return GradientScaffold(
      title: 'Create a room',
      subtitle:
          'Authenticate the provider on this phone, then open the shared session with a bearer-backed room token.',
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
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              if (_pendingRoomSeed != null) ...<Widget>[
                Container(
                  width: double.infinity,
                  decoration: BoxDecoration(
                    color: const Color(0xFFECFDF5),
                    borderRadius: BorderRadius.circular(24),
                    border: Border.all(color: const Color(0xFFA7F3D0)),
                  ),
                  padding: const EdgeInsets.all(18),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      Text(
                        'Saved plan seed is ready',
                        style: Theme.of(context).textTheme.titleLarge,
                      ),
                      const SizedBox(height: 8),
                      Text(
                        '${_pendingRoomSeed!.surface.name} · ${_pendingRoomSeed!.climbs.length} queued climb${_pendingRoomSeed!.climbs.length == 1 ? '' : 's'}',
                      ),
                      const SizedBox(height: 12),
                      Row(
                        children: <Widget>[
                          Expanded(
                            child: Text(
                              'Open a matching ${_pendingRoomSeed!.providerId} room, then import the seed from inside the room once the surface is set.',
                            ),
                          ),
                          const SizedBox(width: 12),
                          TextButton(
                            onPressed: () async {
                              await ref
                                  .read(appPrefsControllerProvider.notifier)
                                  .clearPendingRoomSeed();
                              if (!mounted) {
                                return;
                              }
                              setState(() {
                                _pendingRoomSeed = null;
                              });
                            },
                            child: const Text('Clear'),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 18),
              ],
              if (_inlineError != null) ...<Widget>[
                Container(
                  width: double.infinity,
                  decoration: BoxDecoration(
                    color: const Color(0xFFFEE2E2),
                    borderRadius: BorderRadius.circular(24),
                    border: Border.all(color: const Color(0xFFFCA5A5)),
                  ),
                  padding: const EdgeInsets.all(16),
                  child: Text(_inlineError!),
                ),
                const SizedBox(height: 18),
              ],
              TextField(
                controller: _serverController,
                decoration: const InputDecoration(
                  labelText: 'Self-hosted server URL',
                  hintText: 'https://boards.example.com',
                ),
                keyboardType: TextInputType.url,
              ),
              const SizedBox(height: 12),
              Align(
                alignment: Alignment.centerLeft,
                child: FilledButton.tonal(
                  onPressed: _loadingCapabilities ? null : _loadCapabilities,
                  child: Text(_loadingCapabilities
                      ? 'Loading providers...'
                      : 'Load providers'),
                ),
              ),
              const SizedBox(height: 18),
              TextField(
                controller: _roomNameController,
                decoration: const InputDecoration(labelText: 'Room name'),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _displayNameController,
                decoration:
                    const InputDecoration(labelText: 'Host display name'),
              ),
              const SizedBox(height: 12),
              DropdownButtonFormField<String>(
                initialValue: _selectedProviderId,
                decoration: const InputDecoration(labelText: 'Provider'),
                items: _capabilities
                    .map(
                      (ProviderCapability item) => DropdownMenuItem<String>(
                        value: item.id,
                        child: Text(item.label),
                      ),
                    )
                    .toList(growable: false),
                onChanged: (String? value) {
                  setState(() {
                    _selectedProviderId = value;
                  });
                },
              ),
              const SizedBox(height: 12),
              if (capability != null)
                ...capability.authFields.map(
                  (ProviderAuthField field) => Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: TextField(
                      controller: _secretControllers[field.key],
                      obscureText: field.type == 'password',
                      decoration: InputDecoration(
                        labelText: field.label,
                        hintText: field.placeholder,
                      ),
                    ),
                  ),
                ),
              SwitchListTile.adaptive(
                contentPadding: EdgeInsets.zero,
                title: const Text('Enable fist bumps'),
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
                child: FilledButton(
                  onPressed: _submitting ? null : _submit,
                  child: Text(_submitting ? 'Creating room...' : 'Open room'),
                ),
              ),
              if (_showFailureFeedback) ...<Widget>[
                const SizedBox(height: 18),
                FeedbackPromptCard(
                  title: 'Was the room creation failure useful?',
                  description:
                      'A quick signal helps tighten provider auth and room setup messaging on mobile.',
                  onDismiss: () => unawaited(_dismissFailureFeedback()),
                  onSubmit: (String sentiment, String? message) async {
                    await ref.read(apiClientProvider).submitFeedback(
                      server: normalizeServerUri(_serverController.text.trim()),
                      promptFamily: 'room-create-failure',
                      sentiment: sentiment,
                      message: message,
                      route: '/create',
                      metadata: <String, dynamic>{
                        'provider_id': capability?.id ?? '',
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
