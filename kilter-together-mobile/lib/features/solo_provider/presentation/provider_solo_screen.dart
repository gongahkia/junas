import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../core/presentation/gradient_scaffold.dart';

class ProviderSoloScreen extends StatelessWidget {
  const ProviderSoloScreen({
    super.key,
    required this.providerId,
  });

  final String providerId;

  @override
  Widget build(BuildContext context) {
    return GradientScaffold(
      title: '${providerId.toUpperCase()} Solo',
      subtitle: 'This route will host provider auth, surface selection, paginated climb catalog, and shared plan creation.',
      actions: <Widget>[
        IconButton(
          onPressed: () => context.goNamed('solo-entry'),
          icon: const Icon(Icons.arrow_back),
        ),
      ],
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(22),
          child: Text(
            'Batch 4 fills this screen with provider-backed solo browse, remembered secrets, shortlist assembly, and plan continuity.',
            style: Theme.of(context).textTheme.bodyLarge,
          ),
        ),
      ),
    );
  }
}
