import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/link.dart';

import '../../../core/presentation/app_surfaces.dart';
import '../../../core/presentation/gradient_scaffold.dart';
import '../../../core/theme/app_theme.dart';

class AboutScreen extends StatelessWidget {
  const AboutScreen({super.key});

  static final Uri _gabrielUri = Uri.parse('https://gabrielongzm.com');
  static final Uri _projectUri = Uri.parse(
    'https://github.com/gongahkia/kilter-together',
  );

  @override
  Widget build(BuildContext context) {
    final KilterPalette palette = kilterPaletteOf(context);
    final TextStyle headingStyle = Theme.of(context).textTheme.displayLarge ??
        const TextStyle(fontSize: 32, fontWeight: FontWeight.w700);
    final TextStyle bodyStyle = Theme.of(context).textTheme.bodyLarge?.copyWith(
              color: palette.ink,
            ) ??
        TextStyle(
          fontSize: 16,
          height: 1.5,
          color: palette.ink,
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
      child: AppPanel(
        accentColor: palette.highlight,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: <Widget>[
                AppBadge(
                  label: 'Project note',
                  icon: Icons.auto_stories_outlined,
                  color: palette.highlight,
                ),
                AppBadge(
                  label: 'Open source',
                  icon: Icons.code_rounded,
                  color: palette.secondary,
                ),
              ],
            ),
            const SizedBox(height: 20),
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
                        ' because board sessions usually leave one person scrolling while everyone else waits. I wanted the group to make decisions together instead.',
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
            Text('See you at the gym.', style: bodyStyle),
          ],
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
    final KilterPalette palette = kilterPaletteOf(context);
    return Link(
      uri: uri,
      target: LinkTarget.blank,
      builder: (BuildContext context, FollowLink? followLink) {
        return InkWell(
          borderRadius: BorderRadius.circular(16),
          onTap: followLink,
          child: Text(
            label,
            style: style.copyWith(
              color: palette.highlight,
              decoration: TextDecoration.underline,
              decorationColor: palette.highlight,
            ),
          ),
        );
      },
    );
  }
}
