import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/models/provider_models.dart';
import '../../../core/models/session_models.dart';
import '../../../core/network/api_client.dart';
import '../../../core/presentation/gradient_scaffold.dart';
import '../../../core/storage/session_repository.dart';

class CreateRoomScreen extends ConsumerStatefulWidget {
  const CreateRoomScreen({super.key});

  @override
  ConsumerState<CreateRoomScreen> createState() => _CreateRoomScreenState();
}

class _CreateRoomScreenState extends ConsumerState<CreateRoomScreen> {
  final ApiClient _api = ApiClient();
  final TextEditingController _serverController = TextEditingController();
  final TextEditingController _roomNameController = TextEditingController(text: 'Evening Session');
  final TextEditingController _displayNameController = TextEditingController(text: 'Host');

  bool _loadingCapabilities = false;
  bool _submitting = false;
  bool _fistBumpsEnabled = true;
  List<ProviderCapability> _capabilities = const <ProviderCapability>[];
  String? _selectedProviderId;
  final Map<String, TextEditingController> _secretControllers = <String, TextEditingController>{};

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

  Future<void> _loadCapabilities() async {
    setState(() {
      _loadingCapabilities = true;
    });

    try {
      final Uri server = normalizeServerUri(_serverController.text);
      final List<ProviderCapability> capabilities = await _api.getProviderCapabilities(server);
      final List<ProviderCapability> roomCapabilities =
          capabilities.where((ProviderCapability capability) => capability.roomSupported).toList(growable: false);
      for (final TextEditingController controller in _secretControllers.values) {
        controller.dispose();
      }
      _secretControllers.clear();
      for (final ProviderCapability capability in roomCapabilities) {
        for (final ProviderAuthField field in capability.authFields) {
          _secretControllers.putIfAbsent(field.key, () => TextEditingController());
        }
      }

      setState(() {
        _capabilities = roomCapabilities;
        _selectedProviderId = roomCapabilities.isEmpty ? null : roomCapabilities.first.id;
      });
    } catch (error) {
      _showSnack('Unable to load provider capabilities: $error');
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
    });

    try {
      final Uri server = normalizeServerUri(_serverController.text);
      final Map<String, String> secret = <String, String>{
        for (final ProviderAuthField field in capability.authFields)
          field.key: _secretControllers[field.key]?.text.trim() ?? '',
      };
      final result = await _api.createRoom(
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
      _showSnack('Unable to create room: $error');
    } finally {
      if (mounted) {
        setState(() {
          _submitting = false;
        });
      }
    }
  }

  void _showSnack(String message) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  Widget build(BuildContext context) {
    final ProviderCapability? capability = _selectedCapability;

    return GradientScaffold(
      title: 'Create a room',
      subtitle: 'Authenticate the provider on this phone, then open the shared session with a bearer-backed room token.',
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
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
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
                  child: Text(_loadingCapabilities ? 'Loading providers...' : 'Load providers'),
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
                decoration: const InputDecoration(labelText: 'Host display name'),
              ),
              const SizedBox(height: 12),
              DropdownButtonFormField<String>(
                value: _selectedProviderId,
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
            ],
          ),
        ),
      ),
    );
  }
}

