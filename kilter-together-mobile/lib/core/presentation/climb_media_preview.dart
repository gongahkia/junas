import 'dart:io';
import 'dart:math' as math;

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import '../models/provider_models.dart';

class ClimbMediaPreview extends StatefulWidget {
  const ClimbMediaPreview({
    super.key,
    required this.imageUrls,
    this.highlightedHolds = const <HighlightedHold>[],
    this.emptyMessage = 'Board preview unavailable',
    this.errorMessage = 'Unable to load board image',
    this.aspectRatio = 16 / 10,
  });

  final List<String> imageUrls;
  final List<HighlightedHold> highlightedHolds;
  final String emptyMessage;
  final String errorMessage;
  final double aspectRatio;

  @override
  State<ClimbMediaPreview> createState() => _ClimbMediaPreviewState();
}

class _ClimbMediaPreviewState extends State<ClimbMediaPreview> {
  Set<String> _failedImageUrls = <String>{};

  @override
  void didUpdateWidget(covariant ClimbMediaPreview oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (!listEquals(oldWidget.imageUrls, widget.imageUrls)) {
      _failedImageUrls = <String>{};
    }
  }

  @override
  Widget build(BuildContext context) {
    if (widget.imageUrls.isEmpty) {
      return _PreviewFallback(message: widget.emptyMessage);
    }

    final List<String> visibleImageUrls = widget.imageUrls
        .where((String url) => !_failedImageUrls.contains(url))
        .toList(growable: false);
    if (visibleImageUrls.isEmpty) {
      return _PreviewFallback(message: widget.errorMessage);
    }

    return ClipRRect(
      borderRadius: BorderRadius.zero,
      child: AspectRatio(
        aspectRatio: widget.aspectRatio,
        child: Stack(
          fit: StackFit.expand,
          children: <Widget>[
            Container(color: const Color(0xFFE2E8F0)),
            for (final String imageUrl in visibleImageUrls)
              _PreviewImage(
                imageUrl: imageUrl,
                onFailed: () => _markFailed(imageUrl),
              ),
            if (widget.highlightedHolds.isNotEmpty)
              CustomPaint(
                painter: _HoldOverlayPainter(widget.highlightedHolds),
              ),
          ],
        ),
      ),
    );
  }

  void _markFailed(String imageUrl) {
    if (_failedImageUrls.contains(imageUrl)) {
      return;
    }
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted || _failedImageUrls.contains(imageUrl)) {
        return;
      }
      setState(() {
        _failedImageUrls = <String>{..._failedImageUrls, imageUrl};
      });
    });
  }
}

class _PreviewImage extends StatelessWidget {
  const _PreviewImage({
    required this.imageUrl,
    required this.onFailed,
  });

  final String imageUrl;
  final VoidCallback onFailed;

  @override
  Widget build(BuildContext context) {
    if (!kIsWeb &&
        (imageUrl.startsWith('/') || imageUrl.startsWith('file://'))) {
      final File file = File(
        imageUrl.startsWith('file://')
            ? Uri.parse(imageUrl).toFilePath()
            : imageUrl,
      );
      return Image.file(
        file,
        key: ValueKey<String>(imageUrl),
        fit: BoxFit.cover,
        errorBuilder: (_, __, ___) {
          onFailed();
          return const SizedBox.shrink();
        },
      );
    }

    return Image.network(
      imageUrl,
      key: ValueKey<String>(imageUrl),
      fit: BoxFit.cover,
      errorBuilder: (_, __, ___) {
        onFailed();
        return const SizedBox.shrink();
      },
    );
  }
}

class _PreviewFallback extends StatelessWidget {
  const _PreviewFallback({
    required this.message,
  });

  final String message;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 220,
      decoration: BoxDecoration(
        color: const Color(0xFFE2E8F0),
        borderRadius: BorderRadius.zero,
      ),
      alignment: Alignment.center,
      child: Text(message),
    );
  }
}

class _HoldOverlayPainter extends CustomPainter {
  const _HoldOverlayPainter(this.holds);

  final List<HighlightedHold> holds;

  @override
  void paint(Canvas canvas, Size size) {
    for (final HighlightedHold hold in holds) {
      final double x = hold.x > 1 ? hold.x / 100 : hold.x;
      final double y = hold.y > 1 ? hold.y / 100 : hold.y;
      final Offset center = Offset(
        size.width * x.clamp(0.04, 0.96),
        size.height * y.clamp(0.04, 0.96),
      );
      final double radius = math.max(8, size.shortestSide * 0.03);
      final Color color = _parseHoldColor(hold.color) ??
          switch (hold.role) {
            'finish' => const Color(0xFFF97316),
            'start' => const Color(0xFF22C55E),
            _ => const Color(0xFF38BDF8),
          };

      final Paint fill = Paint()
        ..color = color.withValues(alpha: 0.24)
        ..style = PaintingStyle.fill;
      final Paint stroke = Paint()
        ..color = color
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2.1;
      canvas.drawCircle(center, radius, fill);
      canvas.drawCircle(center, radius, stroke);
    }
  }

  @override
  bool shouldRepaint(covariant _HoldOverlayPainter oldDelegate) {
    return oldDelegate.holds != holds;
  }

  Color? _parseHoldColor(String raw) {
    final String normalized = raw.trim().replaceFirst('#', '');
    if (normalized.isEmpty) {
      return null;
    }
    final String value = normalized.length == 6 ? 'FF$normalized' : normalized;
    final int? parsed = int.tryParse(value, radix: 16);
    if (parsed == null) {
      return null;
    }
    return Color(parsed);
  }
}
