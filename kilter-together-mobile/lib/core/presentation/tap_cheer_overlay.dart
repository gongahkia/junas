import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';

const List<String> _cheerPhrases = <String>[
  'allez!',
  'vamos!',
  'forza!',
  'hup!',
  'yalla!',
  'bora!',
  'go!',
  'push!',
  'nice!',
  'come on!',
];

const Duration _cheerLifetime = Duration(milliseconds: 1400);
const double _dragThresholdSquared = 144;

class TapCheerOverlay extends StatefulWidget {
  const TapCheerOverlay({
    required this.child,
    required this.enabled,
    super.key,
  });

  final Widget child;
  final bool enabled;

  @override
  State<TapCheerOverlay> createState() => _TapCheerOverlayState();
}

class _TapCheerOverlayState extends State<TapCheerOverlay> {
  final math.Random _random = math.Random();
  final Map<int, Offset> _activePointers = <int, Offset>{};
  final Set<int> _movedPointers = <int>{};
  final List<_CheerInstance> _cheers = <_CheerInstance>[];
  final List<Timer> _timers = <Timer>[];

  int _nextCheerId = 0;
  int _phraseIndex = 0;

  @override
  void didUpdateWidget(covariant TapCheerOverlay oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.enabled && !widget.enabled) {
      _clearCheerState();
    }
  }

  @override
  void dispose() {
    _clearCheerState();
    super.dispose();
  }

  void _clearCheerState() {
    for (final Timer timer in _timers) {
      timer.cancel();
    }
    _timers.clear();
    _activePointers.clear();
    _movedPointers.clear();
    if (_cheers.isNotEmpty && mounted) {
      setState(() {
        _cheers.clear();
      });
      return;
    }
    _cheers.clear();
  }

  void _handlePointerDown(PointerDownEvent event) {
    if (!widget.enabled || !_supportsTapCheer(event.kind)) {
      return;
    }
    _activePointers[event.pointer] = event.position;
  }

  void _handlePointerMove(PointerMoveEvent event) {
    final Offset? origin = _activePointers[event.pointer];
    if (origin == null) {
      return;
    }
    final Offset delta = event.position - origin;
    if (delta.distanceSquared > _dragThresholdSquared) {
      _movedPointers.add(event.pointer);
    }
  }

  void _handlePointerUp(PointerUpEvent event) {
    final Offset? origin = _activePointers.remove(event.pointer);
    final bool moved = _movedPointers.remove(event.pointer);
    if (origin == null || moved) {
      return;
    }
    _spawnCheer(event.position);
  }

  void _handlePointerCancel(PointerCancelEvent event) {
    _activePointers.remove(event.pointer);
    _movedPointers.remove(event.pointer);
  }

  void _spawnCheer(Offset position) {
    final int id = _nextCheerId++;
    final _CheerInstance cheer = _CheerInstance(
      id: id,
      position: position,
      text: _cheerPhrases[_phraseIndex % _cheerPhrases.length],
      drift: (_random.nextDouble() - 0.5) * 32,
      tiltRadians: (_random.nextDouble() - 0.5) * 0.18,
    );
    _phraseIndex += 1;

    setState(() {
      _cheers.add(cheer);
    });

    late final Timer timer;
    timer = Timer(_cheerLifetime, () {
      if (!mounted) {
        return;
      }
      setState(() {
        _cheers.removeWhere((_CheerInstance item) => item.id == id);
      });
      _timers.remove(timer);
    });
    _timers.add(timer);
  }

  @override
  Widget build(BuildContext context) {
    if (!widget.enabled) {
      return widget.child;
    }

    final TextStyle textStyle =
        Theme.of(context).textTheme.titleMedium!.copyWith(
      color: const Color(0xFF115E59),
      fontWeight: FontWeight.w800,
      letterSpacing: 0.4,
      shadows: const <Shadow>[
        Shadow(
          color: Color(0x55FFFFFF),
          blurRadius: 12,
        ),
      ],
    );

    return Listener(
      behavior: HitTestBehavior.translucent,
      onPointerDown: _handlePointerDown,
      onPointerMove: _handlePointerMove,
      onPointerUp: _handlePointerUp,
      onPointerCancel: _handlePointerCancel,
      child: Stack(
        fit: StackFit.expand,
        children: <Widget>[
          widget.child,
          IgnorePointer(
            child: Stack(
              clipBehavior: Clip.none,
              children: _cheers
                  .map(
                    (_CheerInstance cheer) => _TapCheerWord(
                      key: ValueKey<int>(cheer.id),
                      cheer: cheer,
                      textStyle: textStyle,
                    ),
                  )
                  .toList(growable: false),
            ),
          ),
        ],
      ),
    );
  }
}

class _TapCheerWord extends StatelessWidget {
  const _TapCheerWord({
    required this.cheer,
    required this.textStyle,
    super.key,
  });

  final _CheerInstance cheer;
  final TextStyle textStyle;

  @override
  Widget build(BuildContext context) {
    return TweenAnimationBuilder<double>(
      duration: _cheerLifetime,
      tween: Tween<double>(begin: 0, end: 1),
      builder: (BuildContext context, double value, Widget? child) {
        final double progress = Curves.easeOut.transform(value);
        final double fadeStart = 0.72;
        final double opacity = progress < fadeStart
            ? 1
            : (1 - (progress - fadeStart) / (1 - fadeStart)).clamp(0, 1);

        return Positioned(
          left: cheer.position.dx,
          top: cheer.position.dy,
          child: Transform.translate(
            offset:
                Offset(-18 + (cheer.drift * progress), -16 - (42 * progress)),
            child: Transform.rotate(
              angle: cheer.tiltRadians * progress,
              child: Opacity(
                opacity: opacity,
                child: DecoratedBox(
                  decoration: BoxDecoration(
                    color: const Color(0xF2F0FDFA),
                    borderRadius: BorderRadius.circular(999),
                    border: Border.all(color: const Color(0xFFD3F3EB)),
                  ),
                  child: Padding(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                    child: Text(cheer.text, style: textStyle),
                  ),
                ),
              ),
            ),
          ),
        );
      },
    );
  }
}

class _CheerInstance {
  const _CheerInstance({
    required this.id,
    required this.position,
    required this.text,
    required this.drift,
    required this.tiltRadians,
  });

  final int id;
  final Offset position;
  final String text;
  final double drift;
  final double tiltRadians;
}

bool _supportsTapCheer(PointerDeviceKind kind) {
  return kind == PointerDeviceKind.touch ||
      kind == PointerDeviceKind.stylus ||
      kind == PointerDeviceKind.invertedStylus ||
      kind == PointerDeviceKind.unknown;
}
