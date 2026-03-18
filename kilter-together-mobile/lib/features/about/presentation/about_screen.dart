import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/link.dart';

import '../../../core/presentation/gradient_scaffold.dart';

class AboutScreen extends StatelessWidget {
  const AboutScreen({super.key});

  static final Uri _gabrielUri = Uri.parse('https://gabrielongzm.com');
  static final Uri _projectUri = Uri.parse(
    'https://github.com/gongahkia/kilter-together',
  );

  @override
  Widget build(BuildContext context) {
    final TextStyle headingStyle = Theme.of(context).textTheme.displayLarge ??
        const TextStyle(fontSize: 32, fontWeight: FontWeight.w700);
    final TextStyle bodyStyle = Theme.of(context).textTheme.bodyLarge?.copyWith(
              height: 1.5,
              color: const Color(0xFF203632),
            ) ??
        const TextStyle(
          fontSize: 16,
          height: 1.5,
          color: Color(0xFF203632),
        );

    return GradientScaffold(
      title: 'About Kilter Together',
      subtitle:
          'Why this project exists, and what it is trying to make easier for group board sessions.',
      actions: <Widget>[
        IconButton(
          onPressed: () => context.goNamed('session-home'),
          icon: const Icon(Icons.close),
        ),
      ],
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(22),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Text.rich(
                TextSpan(
                  style: headingStyle,
                  children: <InlineSpan>[
                    const TextSpan(text: 'Hi, I\'m '),
                    WidgetSpan(
                      alignment: PlaceholderAlignment.baseline,
                      baseline: TextBaseline.alphabetic,
                      child: _ExternalLinkText(
                        label: 'Gabriel',
                        uri: _gabrielUri,
                        style: headingStyle,
                      ),
                    ),
                    const TextSpan(text: '.'),
                  ],
                ),
              ),
              const SizedBox(height: 16),
              Text.rich(
                TextSpan(
                  style: bodyStyle,
                  children: <InlineSpan>[
                    const TextSpan(text: 'I built '),
                    WidgetSpan(
                      alignment: PlaceholderAlignment.baseline,
                      baseline: TextBaseline.alphabetic,
                      child: _ExternalLinkText(
                        label: 'Kilter Together',
                        uri: _projectUri,
                        style: bodyStyle.copyWith(fontWeight: FontWeight.w700),
                      ),
                    ),
                    const TextSpan(
                      text:
                          ' because I wanted board sessions to feel more collaborative than one person scrolling through climbs while everyone else waits to ask for a turn.',
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 14),
              Text.rich(
                TextSpan(
                  style: bodyStyle,
                  children: <InlineSpan>[
                    const TextSpan(text: 'The goal of '),
                    WidgetSpan(
                      alignment: PlaceholderAlignment.baseline,
                      baseline: TextBaseline.alphabetic,
                      child: _ExternalLinkText(
                        label: 'Kilter Together',
                        uri: _projectUri,
                        style: bodyStyle.copyWith(fontWeight: FontWeight.w700),
                      ),
                    ),
                    const TextSpan(
                      text:
                          ' is simple: one host connects the provider account, opens a room, and the whole group can vote, queue climbs, and session together from their own phones.',
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 14),
              Text(
                'I like software that gets out of the way. This app is meant to make shared decisions around a board feel lighter, clearer, and less awkward.',
                style: bodyStyle,
              ),
              const SizedBox(height: 16),
              Text(
                'See you at the gym.',
                style: bodyStyle,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ExternalLinkText extends StatelessWidget {
  const _ExternalLinkText({
    required this.label,
    required this.uri,
    required this.style,
  });

  final String label;
  final Uri uri;
  final TextStyle style;

  @override
  Widget build(BuildContext context) {
    return Link(
      uri: uri,
      target: LinkTarget.blank,
      builder: (BuildContext context, FollowLink? followLink) {
        return InkWell(
          borderRadius: BorderRadius.zero,
          onTap: followLink,
          child: Text(
            label,
            style: style.copyWith(
              color: const Color(0xFF1A1A1A),
              decoration: TextDecoration.underline,
              decorationColor: const Color(0xFF1A1A1A),
            ),
          ),
        );
      },
    );
  }
}
