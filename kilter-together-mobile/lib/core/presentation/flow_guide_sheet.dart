import 'package:flutter/material.dart';

enum FlowGuideResult {
  dismissed,
  completed,
}

class FlowGuideContent {
  const FlowGuideContent({
    required this.eyebrow,
    required this.title,
    required this.summary,
    required this.sections,
    this.completionLabel = 'Mark guide complete',
  });

  final String eyebrow;
  final String title;
  final String summary;
  final List<FlowGuideSection> sections;
  final String completionLabel;
}

class FlowGuideSection {
  const FlowGuideSection({
    required this.title,
    required this.body,
  });

  final String title;
  final String body;
}

Future<FlowGuideResult?> showFlowGuideSheet({
  required BuildContext context,
  required FlowGuideContent content,
  required bool completed,
}) {
  return showModalBottomSheet<FlowGuideResult>(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    backgroundColor: Colors.transparent,
    builder: (BuildContext context) {
      return _FlowGuideSheet(
        content: content,
        completed: completed,
      );
    },
  );
}

class _FlowGuideSheet extends StatelessWidget {
  const _FlowGuideSheet({
    required this.content,
    required this.completed,
  });

  final FlowGuideContent content;
  final bool completed;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      top: false,
      child: Container(
        decoration: const BoxDecoration(
          color: Color(0xFFF5F5F5),
          borderRadius: BorderRadius.zero,
        ),
        child: SingleChildScrollView(
          padding: EdgeInsets.fromLTRB(
            24,
            16,
            24,
            24 + MediaQuery.of(context).viewInsets.bottom,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                decoration: BoxDecoration(
                  color: const Color(0xFFDDF7F0),
                  borderRadius: BorderRadius.zero,
                ),
                child: Text(
                  content.eyebrow,
                  style: Theme.of(context).textTheme.labelLarge?.copyWith(
                        color: const Color(0xFF1A1A1A),
                        letterSpacing: 0.4,
                      ),
                ),
              ),
              const SizedBox(height: 18),
              Text(
                content.title,
                style: Theme.of(context).textTheme.displayLarge,
              ),
              const SizedBox(height: 10),
              Text(
                content.summary,
                style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                      color: const Color(0xFF525252),
                    ),
              ),
              const SizedBox(height: 20),
              ...content.sections.map(
                (FlowGuideSection section) => Padding(
                  padding: const EdgeInsets.only(bottom: 14),
                  child: Container(
                    width: double.infinity,
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.zero,
                      border: Border.all(color: const Color(0xFFD7ECE6)),
                    ),
                    padding: const EdgeInsets.all(18),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Text(
                          section.title,
                          style: Theme.of(context).textTheme.titleLarge,
                        ),
                        const SizedBox(height: 8),
                        Text(section.body),
                      ],
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 10),
              Row(
                children: <Widget>[
                  Expanded(
                    child: OutlinedButton(
                      onPressed: () => Navigator.of(context)
                          .pop(FlowGuideResult.dismissed),
                      child: Text(completed ? 'Done' : 'Not now'),
                    ),
                  ),
                  if (!completed) ...<Widget>[
                    const SizedBox(width: 12),
                    Expanded(
                      child: FilledButton(
                        onPressed: () => Navigator.of(context)
                            .pop(FlowGuideResult.completed),
                        child: Text(content.completionLabel),
                      ),
                    ),
                  ],
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}
