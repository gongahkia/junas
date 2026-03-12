import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../core/presentation/gradient_scaffold.dart';

class RecapScreen extends StatelessWidget {
  const RecapScreen({
    super.key,
    required this.server,
    required this.shareId,
  });

  final String server;
  final String shareId;

  @override
  Widget build(BuildContext context) {
    return GradientScaffold(
      title: 'Session Recap',
      subtitle: 'Server: $server',
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
            'Recap share $shareId will load here once the shared snapshot and feedback flow land in Batch 5.',
            style: Theme.of(context).textTheme.bodyLarge,
          ),
        ),
      ),
    );
  }
}
