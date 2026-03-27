import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

class AppBottomBar extends StatelessWidget {
  const AppBottomBar({
    required this.currentIndex,
    required this.onTap,
    super.key,
    this.animationsEnabled = true,
  });

  final int currentIndex;
  final ValueChanged<int> onTap;
  final bool animationsEnabled;

  static const List<_BottomBarSpec> _items = <_BottomBarSpec>[
    _BottomBarSpec(
      branchIndex: 0,
      label: 'Session',
      icon: Icons.people_alt_outlined,
      accent: Color(0xFF255543),
    ),
    _BottomBarSpec(
      branchIndex: 1,
      label: 'Solo',
      icon: Icons.explore_outlined,
      accent: Color(0xFF7C6D31),
    ),
    _BottomBarSpec(
      branchIndex: 2,
      label: 'Log',
      icon: Icons.auto_graph_rounded,
      accent: Color(0xFFC7682F),
    ),
    _BottomBarSpec(
      branchIndex: 3,
      label: 'Settings',
      icon: Icons.tune_rounded,
      accent: Color(0xFF2D3631),
    ),
  ];

  @override
  Widget build(BuildContext context) {
    final KilterPalette palette = kilterPaletteOf(context);
    final int activeIndex = _items.indexWhere(
      (_BottomBarSpec item) => item.branchIndex == currentIndex,
    );
    final int clampedIndex = activeIndex >= 0 ? activeIndex : 0;
    final Color activeAccent = _items[clampedIndex].accent;
    final Duration motionDuration =
        animationsEnabled ? const Duration(milliseconds: 280) : Duration.zero;
    final Curve motionCurve =
        animationsEnabled ? Curves.easeOutCubic : Curves.linear;

    return SafeArea(
      top: false,
      minimum: const EdgeInsets.fromLTRB(16, 0, 16, 14),
      child: DecoratedBox(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            colors: <Color>[
              palette.panel.withValues(alpha: 0.94),
              palette.panelRaised.withValues(alpha: 0.98),
            ],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
          borderRadius: BorderRadius.circular(32),
          border: Border.all(color: palette.stroke.withValues(alpha: 0.95)),
          boxShadow: <BoxShadow>[
            BoxShadow(
              color: palette.ink.withValues(alpha: 0.14),
              blurRadius: 36,
              offset: const Offset(0, 18),
            ),
          ],
        ),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 10),
          child: SizedBox(
            height: 82,
            child: LayoutBuilder(
              builder: (BuildContext context, BoxConstraints constraints) {
                final double itemWidth = constraints.maxWidth / _items.length;

                return Stack(
                  children: <Widget>[
                    AnimatedPositioned(
                      duration: motionDuration,
                      curve: motionCurve,
                      left: itemWidth * clampedIndex,
                      top: 0,
                      bottom: 0,
                      width: itemWidth,
                      child: Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 4),
                        child: DecoratedBox(
                          decoration: BoxDecoration(
                            borderRadius: BorderRadius.circular(24),
                            gradient: LinearGradient(
                              colors: <Color>[
                                activeAccent.withValues(alpha: 0.2),
                                activeAccent.withValues(alpha: 0.08),
                              ],
                              begin: Alignment.topCenter,
                              end: Alignment.bottomCenter,
                            ),
                          ),
                        ),
                      ),
                    ),
                    Row(
                      children:
                          List<Widget>.generate(_items.length, (int index) {
                        final _BottomBarSpec item = _items[index];
                        return Expanded(
                          child: _BottomBarItem(
                            spec: item,
                            active: index == clampedIndex,
                            animationsEnabled: animationsEnabled,
                            onTap: () => onTap(item.branchIndex),
                          ),
                        );
                      }),
                    ),
                  ],
                );
              },
            ),
          ),
        ),
      ),
    );
  }
}

class _BottomBarItem extends StatelessWidget {
  const _BottomBarItem({
    required this.spec,
    required this.active,
    required this.onTap,
    required this.animationsEnabled,
  });

  final _BottomBarSpec spec;
  final bool active;
  final VoidCallback onTap;
  final bool animationsEnabled;

  @override
  Widget build(BuildContext context) {
    final KilterPalette palette = kilterPaletteOf(context);
    final Color foreground = active ? spec.accent : palette.subtleInk;
    final Duration motionDuration =
        animationsEnabled ? const Duration(milliseconds: 180) : Duration.zero;
    final Curve motionCurve =
        animationsEnabled ? Curves.easeOutCubic : Curves.linear;

    return InkWell(
      borderRadius: BorderRadius.circular(24),
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 4),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: <Widget>[
            AnimatedContainer(
              duration: motionDuration,
              curve: motionCurve,
              width: active ? 42 : 36,
              height: active ? 42 : 36,
              decoration: BoxDecoration(
                color: active
                    ? spec.accent
                    : palette.panel.withValues(alpha: 0.55),
                borderRadius: BorderRadius.circular(18),
                border: Border.all(
                  color: active
                      ? spec.accent.withValues(alpha: 0.35)
                      : palette.stroke.withValues(alpha: 0.6),
                ),
              ),
              child: Icon(
                spec.icon,
                size: active ? 22 : 19,
                color: active ? Colors.white : foreground,
              ),
            ),
            const SizedBox(height: 6),
            Text(
              spec.label,
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.labelSmall?.copyWith(
                    color: foreground,
                    fontWeight: active ? FontWeight.w700 : FontWeight.w600,
                  ),
            ),
          ],
        ),
      ),
    );
  }
}

class _BottomBarSpec {
  const _BottomBarSpec({
    required this.branchIndex,
    required this.label,
    required this.icon,
    required this.accent,
  });

  final int branchIndex;
  final String label;
  final IconData icon;
  final Color accent;
}
