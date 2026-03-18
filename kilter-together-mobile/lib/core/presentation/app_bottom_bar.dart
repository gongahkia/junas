import 'package:flutter/material.dart';

class AppBottomBar extends StatelessWidget {
  const AppBottomBar({
    required this.currentIndex,
    required this.onTap,
    super.key,
  });

  final int currentIndex;
  final ValueChanged<int> onTap;

  static const List<_BottomBarSpec> _items = <_BottomBarSpec>[
    _BottomBarSpec(
      branchIndex: 0,
      label: 'Session',
      icon: Icons.people_outline_rounded,
      accent: Color(0xFF1A1A1A),
    ),
    _BottomBarSpec(
      branchIndex: 1,
      label: 'Solo',
      icon: Icons.grid_view_rounded,
      accent: Color(0xFF1A1A1A),
    ),
    _BottomBarSpec(
      branchIndex: 2,
      label: 'Log',
      icon: Icons.history_rounded,
      accent: Color(0xFF1A1A1A),
    ),
    _BottomBarSpec(
      branchIndex: 3,
      label: 'Settings',
      icon: Icons.tune_rounded,
      accent: Color(0xFF1A1A1A),
    ),
  ];

  @override
  Widget build(BuildContext context) {
    final int activeIndex = _items.indexWhere(
      (_BottomBarSpec item) => item.branchIndex == currentIndex,
    );
    final int clampedIndex = activeIndex >= 0 ? activeIndex : 0;
    final Color activeAccent = _items[clampedIndex].accent;

    return SafeArea(
      top: false,
      minimum: const EdgeInsets.fromLTRB(16, 0, 16, 14),
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: const Color(0xFFFFFFFF),
          borderRadius: BorderRadius.zero,
          border: Border.all(color: const Color(0xFFD4D4D4)),
          boxShadow: const <BoxShadow>[
            BoxShadow(
              color: Color(0x191A1A1A),
              blurRadius: 28,
              offset: Offset(0, 14),
            ),
          ],
        ),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
          child: SizedBox(
            height: 84,
            child: LayoutBuilder(
              builder: (BuildContext context, BoxConstraints constraints) {
                final double itemWidth = constraints.maxWidth / _items.length;

                return Stack(
                  children: <Widget>[
                    AnimatedPositioned(
                      duration: const Duration(milliseconds: 280),
                      curve: Curves.easeInOutCubic,
                      left: itemWidth * clampedIndex,
                      top: 0,
                      bottom: 0,
                      width: itemWidth,
                      child: Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 3),
                        child: AnimatedContainer(
                          duration: const Duration(milliseconds: 220),
                          curve: Curves.easeOutCubic,
                          decoration: BoxDecoration(
                            borderRadius: BorderRadius.zero,
                            gradient: LinearGradient(
                              colors: <Color>[
                                activeAccent.withValues(alpha: 0.22),
                                Colors.white,
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
  });

  final _BottomBarSpec spec;
  final bool active;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final Color accent = spec.accent;
    final Color foreground = active ? accent : const Color(0xFF737373);

    return InkWell(
      borderRadius: BorderRadius.zero,
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 6),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            AnimatedContainer(
              duration: const Duration(milliseconds: 180),
              curve: Curves.easeOutCubic,
              width: active ? 38 : 32,
              height: active ? 38 : 32,
              decoration: BoxDecoration(
                color: active
                    ? accent.withValues(alpha: 0.96)
                    : Colors.transparent,
                borderRadius: BorderRadius.zero,
                border: Border.all(
                  color: active
                      ? accent.withValues(alpha: 0.28)
                      : const Color(0x00000000),
                ),
              ),
              child: Icon(
                spec.icon,
                size: active ? 20 : 18,
                color: active ? Colors.white : foreground,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              spec.label,
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.labelSmall?.copyWith(
                    fontWeight: active ? FontWeight.w700 : FontWeight.w500,
                    color: foreground,
                    letterSpacing: 0.1,
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
