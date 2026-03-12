import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../core/presentation/gradient_scaffold.dart';

class SettingsScreen extends StatelessWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return GradientScaffold(
      title: 'Settings',
      subtitle: 'Local-only preferences for display defaults, guides, recent rooms, saved credentials, and solo behavior.',
      actions: <Widget>[
        IconButton(
          onPressed: () => context.goNamed('landing'),
          icon: const Icon(Icons.close),
        ),
      ],
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(22),
          child: Text(
            'Batch 5 turns this into the full parity settings screen backed by the new mobile prefs schema.',
            style: Theme.of(context).textTheme.bodyLarge,
          ),
        ),
      ),
    );
  }
}
