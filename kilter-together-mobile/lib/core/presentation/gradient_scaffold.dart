import 'package:flutter/material.dart';

import '../theme/app_theme.dart';
import 'app_surfaces.dart';

class GradientScaffold extends StatelessWidget {
  const GradientScaffold({
    required this.title,
    required this.child,
    super.key,
    this.subtitle,
    this.actions = const <Widget>[],
    this.showBottomBar = true,
  });

  final String title;
  final String? subtitle;
  final Widget child;
  final List<Widget> actions;
  final bool showBottomBar;

  @override
  Widget build(BuildContext context) {
    final KilterPalette palette = kilterPaletteOf(context);
    final TextTheme textTheme = Theme.of(context).textTheme;

    return Scaffold(
      body: DecoratedBox(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: <Color>[
              palette.canvas,
              palette.mist,
              palette.panelRaised,
            ],
          ),
        ),
        child: Stack(
          children: <Widget>[
            Positioned(
              top: -80,
              left: -40,
              child: _GlowOrb(
                color: palette.primaryGlow.withValues(alpha: 0.38),
                size: 220,
              ),
            ),
            Positioned(
              top: 140,
              right: -70,
              child: _GlowOrb(
                color: palette.highlight.withValues(alpha: 0.2),
                size: 180,
              ),
            ),
            Positioned(
              bottom: -90,
              left: 40,
              child: _GlowOrb(
                color: palette.secondary.withValues(alpha: 0.12),
                size: 220,
              ),
            ),
            SafeArea(
              child: Align(
                alignment: Alignment.topCenter,
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 760),
                  child: ListView(
                    padding: EdgeInsets.fromLTRB(
                      20,
                      14,
                      20,
                      showBottomBar ? 124 : 32,
                    ),
                    children: <Widget>[
                      AppPanel(
                        accentColor: palette.highlight,
                        padding: const EdgeInsets.fromLTRB(24, 22, 24, 24),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: <Widget>[
                            Row(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: <Widget>[
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: <Widget>[
                                      AppBadge(
                                        label: 'Kilter Together',
                                        icon: Icons.terrain_rounded,
                                        color: palette.secondary,
                                      ),
                                      const SizedBox(height: 18),
                                      Text(title,
                                          style: textTheme.displayLarge),
                                      if (subtitle != null) ...<Widget>[
                                        const SizedBox(height: 12),
                                        Text(
                                          subtitle!,
                                          style: textTheme.bodyLarge?.copyWith(
                                            color: palette.subtleInk,
                                          ),
                                        ),
                                      ],
                                    ],
                                  ),
                                ),
                                if (actions.isNotEmpty) ...<Widget>[
                                  const SizedBox(width: 16),
                                  Wrap(
                                    spacing: 8,
                                    runSpacing: 8,
                                    alignment: WrapAlignment.end,
                                    children: actions
                                        .map(
                                          (Widget action) => DecoratedBox(
                                            decoration: BoxDecoration(
                                              color: palette.panelRaised
                                                  .withValues(alpha: 0.92),
                                              borderRadius:
                                                  BorderRadius.circular(18),
                                              border: Border.all(
                                                color: palette.stroke,
                                              ),
                                            ),
                                            child: action,
                                          ),
                                        )
                                        .toList(growable: false),
                                  ),
                                ],
                              ],
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 24),
                      child,
                    ],
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _GlowOrb extends StatelessWidget {
  const _GlowOrb({
    required this.color,
    required this.size,
  });

  final Color color;
  final double size;

  @override
  Widget build(BuildContext context) {
    return IgnorePointer(
      child: Container(
        width: size,
        height: size,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          gradient: RadialGradient(
            colors: <Color>[
              color,
              color.withValues(alpha: 0),
            ],
          ),
        ),
      ),
    );
  }
}
