import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../core/presentation/gradient_scaffold.dart';

class SoloBoardScreen extends StatelessWidget {
  const SoloBoardScreen({
    super.key,
    required this.boardId,
  });

  final String boardId;

  @override
  Widget build(BuildContext context) {
    return GradientScaffold(
      title: 'Kilter Board $boardId',
      subtitle: 'This route will host the dedicated board browse, climb detail, overlays, saved filters, and share-plan flow.',
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
            'Batch 3 fills this screen with board selection, paginated catalog state, hold overlays, shortlist actions, and plan sharing.',
            style: Theme.of(context).textTheme.bodyLarge,
          ),
        ),
      ),
    );
  }
}
