import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/models/session_models.dart';
import '../../../core/presentation/gradient_scaffold.dart';
import '../../../core/storage/session_repository.dart';

class LandingScreen extends ConsumerWidget {
  const LandingScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final TextTheme textTheme = Theme.of(context).textTheme;

    return GradientScaffold(
      title: 'Kilter Together',
      subtitle: 'Host, join, and run collaborative board sessions from a native mobile client.',
      child: Column(
        children: <Widget>[
          _ActionCard(
            title: 'Create a room',
            description: 'Authenticate the provider account, open a room, and share the invite from this phone.',
            accent: const Color(0xFF0F766E),
            buttonLabel: 'Host session',
            onPressed: () => context.goNamed('create-room'),
          ),
          const SizedBox(height: 14),
          _ActionCard(
            title: 'Join a room',
            description: 'Paste or scan a mobile invite that already includes the self-hosted server address.',
            accent: const Color(0xFF4D7C0F),
            buttonLabel: 'Join invite',
            onPressed: () => context.goNamed('join-room'),
          ),
          const SizedBox(height: 20),
          Align(
            alignment: Alignment.centerLeft,
            child: Text(
              'Recent servers',
              style: textTheme.titleLarge,
            ),
          ),
          const SizedBox(height: 12),
          FutureBuilder<List<Uri>>(
            future: ref.read(sessionRepositoryProvider).loadRecentServers(),
            builder: (BuildContext context, AsyncSnapshot<List<Uri>> snapshot) {
              final List<Uri> servers = snapshot.data ?? <Uri>[];
              if (servers.isEmpty) {
                return Card(
                  child: Padding(
                    padding: const EdgeInsets.all(20),
                    child: Text(
                      'No self-hosted servers remembered yet. Your first create or join flow will add one here.',
                      style: textTheme.bodyLarge,
                    ),
                  ),
                );
              }

              return Column(
                children: servers
                    .map(
                      (Uri server) => Card(
                        child: ListTile(
                          title: Text(describeServer(server)),
                          subtitle: Text(server.toString()),
                          trailing: const Icon(Icons.chevron_right),
                          onTap: () => context.goNamed(
                            'join-room',
                            queryParameters: <String, String>{
                              'server': server.toString(),
                            },
                          ),
                        ),
                      ),
                    )
                    .toList(growable: false),
              );
            },
          ),
        ],
      ),
    );
  }
}

class _ActionCard extends StatelessWidget {
  const _ActionCard({
    required this.title,
    required this.description,
    required this.accent,
    required this.buttonLabel,
    required this.onPressed,
  });

  final String title;
  final String description;
  final Color accent;
  final String buttonLabel;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Container(
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(28),
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: <Color>[
              accent.withOpacity(0.14),
              Colors.white,
            ],
          ),
        ),
        padding: const EdgeInsets.all(22),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              title,
              style: Theme.of(context).textTheme.headlineMedium,
            ),
            const SizedBox(height: 10),
            Text(description),
            const SizedBox(height: 18),
            FilledButton.tonal(
              onPressed: onPressed,
              child: Text(buttonLabel),
            ),
          ],
        ),
      ),
    );
  }
}
