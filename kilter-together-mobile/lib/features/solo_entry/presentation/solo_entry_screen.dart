import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../core/presentation/gradient_scaffold.dart';

class SoloEntryScreen extends StatelessWidget {
  const SoloEntryScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return GradientScaffold(
      title: 'Solo Browse',
      subtitle: 'Resume your saved Kilter board state or open a live provider-backed solo catalog.',
      actions: <Widget>[
        IconButton(
          onPressed: () => context.goNamed('landing'),
          icon: const Icon(Icons.close),
        ),
      ],
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Card(
            child: Padding(
              padding: const EdgeInsets.all(22),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Text(
                    'Open Kilter',
                    style: Theme.of(context).textTheme.headlineMedium,
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'Browse the local board dataset with filters, shortlist state, and solo-plan creation.',
                  ),
                  const SizedBox(height: 18),
                  FilledButton.tonal(
                    onPressed: () => context.goNamed(
                      'solo-board',
                      pathParameters: <String, String>{'boardId': '1'},
                    ),
                    child: const Text('Choose Kilter board'),
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
                  Text(
                    'Open Provider Catalog',
                    style: Theme.of(context).textTheme.headlineMedium,
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'Authenticate on-device for provider-backed solo browse, shortlist creation, and shareable plans.',
                  ),
                  const SizedBox(height: 18),
                  FilledButton.tonal(
                    onPressed: () => context.goNamed(
                      'solo-provider',
                      pathParameters: <String, String>{'providerId': 'crux'},
                    ),
                    child: const Text('Open Crux'),
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
