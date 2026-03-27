import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

class AppPanel extends StatelessWidget {
  const AppPanel({
    required this.child,
    super.key,
    this.padding = const EdgeInsets.all(22),
    this.accentColor,
    this.backgroundColor,
    this.onTap,
  });

  final Widget child;
  final EdgeInsetsGeometry padding;
  final Color? accentColor;
  final Color? backgroundColor;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final KilterPalette palette = kilterPaletteOf(context);
    final Color accent = accentColor ?? palette.primary;
    final Color base = backgroundColor ?? palette.panel;
    final BorderRadius borderRadius = BorderRadius.circular(30);
    final BoxDecoration decoration = BoxDecoration(
      gradient: LinearGradient(
        colors: <Color>[
          base,
          Color.lerp(base, accent, 0.07) ?? base,
        ],
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
      ),
      borderRadius: borderRadius,
      border: Border.all(
        color: Color.lerp(palette.stroke, accent, 0.28) ?? palette.stroke,
      ),
      boxShadow: <BoxShadow>[
        BoxShadow(
          color: palette.ink.withValues(alpha: 0.08),
          blurRadius: 30,
          offset: const Offset(0, 18),
        ),
      ],
    );

    if (onTap == null) {
      return DecoratedBox(
        decoration: decoration,
        child: _PanelContent(
          padding: padding,
          accent: accent,
          child: child,
        ),
      );
    }

    return Material(
      color: Colors.transparent,
      child: Ink(
        decoration: decoration,
        child: InkWell(
          borderRadius: borderRadius,
          onTap: onTap,
          child: _PanelContent(
            padding: padding,
            accent: accent,
            child: child,
          ),
        ),
      ),
    );
  }
}

class _PanelContent extends StatelessWidget {
  const _PanelContent({
    required this.padding,
    required this.accent,
    required this.child,
  });

  final EdgeInsetsGeometry padding;
  final Color accent;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Stack(
      children: <Widget>[
        Positioned(
          top: -24,
          right: -10,
          child: IgnorePointer(
            child: Container(
              width: 110,
              height: 110,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                gradient: RadialGradient(
                  colors: <Color>[
                    accent.withValues(alpha: 0.22),
                    accent.withValues(alpha: 0),
                  ],
                ),
              ),
            ),
          ),
        ),
        Padding(
          padding: padding,
          child: child,
        ),
      ],
    );
  }
}

class AppBadge extends StatelessWidget {
  const AppBadge({
    required this.label,
    super.key,
    this.icon,
    this.color,
  });

  final String label;
  final IconData? icon;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    final KilterPalette palette = kilterPaletteOf(context);
    final Color tone = color ?? palette.primary;
    final TextStyle style = Theme.of(context).textTheme.labelLarge?.copyWith(
              fontSize: 12,
              color: tone,
            ) ??
        TextStyle(
          fontSize: 12,
          fontWeight: FontWeight.w700,
          color: tone,
        );

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: tone.withValues(alpha: 0.11),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: tone.withValues(alpha: 0.18)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          if (icon != null) ...<Widget>[
            Icon(icon, size: 14, color: tone),
            const SizedBox(width: 6),
          ],
          Text(label, style: style),
        ],
      ),
    );
  }
}
