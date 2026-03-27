import 'dart:async';
import 'dart:math' as math;
import 'package:flutter/material.dart';

class ClimbingLoader extends StatefulWidget {
  const ClimbingLoader({this.size = 120, super.key});
  final double size;
  @override
  State<ClimbingLoader> createState() => _ClimbingLoaderState();
}

class _ClimbingLoaderState extends State<ClimbingLoader> {
  static const List<String> _base = <String>[
    'assets/loading/1.png',
    'assets/loading/2.png',
    'assets/loading/3.png',
    'assets/loading/4.png',
  ];
  static const String _ending1 = 'assets/loading/5-1.png';
  static const String _ending2 = 'assets/loading/5-2.png';
  final math.Random _rng = math.Random();
  late List<String> _frames;
  int _index = 0;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _buildFrames();
    _timer = Timer.periodic(const Duration(milliseconds: 600), (_) {
      setState(() {
        _index++;
        if (_index >= _frames.length) {
          _index = 0;
          _buildFrames();
        }
      });
    });
  }

  void _buildFrames() {
    _frames = <String>[..._base, _rng.nextBool() ? _ending1 : _ending2];
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final double progress = (_index + 1) / _frames.length;
    return SizedBox(
      width: widget.size,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          SizedBox(
            width: widget.size,
            height: widget.size,
            child: Image.asset(_frames[_index], fit: BoxFit.contain),
          ),
          const SizedBox(height: 8),
          SizedBox(
            width: widget.size,
            height: 3,
            child: LinearProgressIndicator(
              value: progress,
              backgroundColor: const Color(0xFFE5E5E5),
              valueColor:
                  const AlwaysStoppedAnimation<Color>(Color(0xFF1A1A1A)),
              minHeight: 3,
            ),
          ),
        ],
      ),
    );
  }
}
