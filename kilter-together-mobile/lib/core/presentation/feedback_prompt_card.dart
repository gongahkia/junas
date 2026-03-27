import 'package:flutter/material.dart';

import '../theme/app_theme.dart';
import 'app_surfaces.dart';

class FeedbackPromptCard extends StatefulWidget {
  const FeedbackPromptCard({
    required this.title,
    required this.description,
    required this.onDismiss,
    required this.onSubmit,
    super.key,
  });

  final String title;
  final String description;
  final VoidCallback onDismiss;
  final Future<void> Function(String sentiment, String? message) onSubmit;

  @override
  State<FeedbackPromptCard> createState() => _FeedbackPromptCardState();
}

class _FeedbackPromptCardState extends State<FeedbackPromptCard> {
  final TextEditingController _messageController = TextEditingController();
  bool _submitting = false;

  @override
  void dispose() {
    _messageController.dispose();
    super.dispose();
  }

  Future<void> _submit(String sentiment) async {
    setState(() {
      _submitting = true;
    });
    try {
      final String message = _messageController.text.trim();
      await widget.onSubmit(
        sentiment,
        message.isEmpty ? null : message,
      );
      _messageController.clear();
    } finally {
      if (mounted) {
        setState(() {
          _submitting = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final KilterPalette palette = kilterPaletteOf(context);

    return AppPanel(
      accentColor: palette.highlight,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          AppBadge(
            label: 'Feedback prompt',
            icon: Icons.forum_outlined,
            color: palette.highlight,
          ),
          const SizedBox(height: 16),
          Text(
            widget.title,
            style: Theme.of(context).textTheme.headlineMedium,
          ),
          const SizedBox(height: 8),
          Text(widget.description),
          const SizedBox(height: 16),
          TextField(
            controller: _messageController,
            minLines: 1,
            maxLines: 3,
            decoration: const InputDecoration(
              labelText: 'Optional note',
              hintText: 'Anything confusing, blocked, or surprisingly good?',
            ),
          ),
          const SizedBox(height: 16),
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: <Widget>[
              TextButton(
                onPressed: _submitting ? null : widget.onDismiss,
                child: const Text('Later'),
              ),
              FilledButton.tonal(
                onPressed: _submitting ? null : () => _submit('positive'),
                child: Text(_submitting ? 'Sending...' : 'Helpful'),
              ),
              FilledButton.tonal(
                onPressed: _submitting ? null : () => _submit('negative'),
                child: Text(_submitting ? 'Sending...' : 'Needs work'),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
