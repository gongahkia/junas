import 'package:flutter_test/flutter_test.dart';
import 'package:kilter_together_mobile/core/models/session_models.dart';

void main() {
  group('normalizeServerUri', () {
    test('adds https scheme when missing', () {
      final Uri uri = normalizeServerUri('example.com');
      expect(uri.scheme, 'https');
      expect(uri.host, 'example.com');
    });

    test('preserves existing https scheme', () {
      final Uri uri = normalizeServerUri('https://example.com');
      expect(uri.scheme, 'https');
      expect(uri.host, 'example.com');
    });

    test('preserves existing http scheme', () {
      final Uri uri = normalizeServerUri('http://localhost:8080');
      expect(uri.scheme, 'http');
      expect(uri.host, 'localhost');
      expect(uri.port, 8080);
    });

    test('strips trailing slash', () {
      final Uri uri = normalizeServerUri('https://example.com/');
      expect(uri.path, '');
    });

    test('strips multiple trailing slashes', () {
      final Uri uri = normalizeServerUri('https://example.com/api///');
      expect(uri.path, '/api');
    });

    test('preserves non-trailing path', () {
      final Uri uri = normalizeServerUri('https://example.com/api/v1');
      expect(uri.path, '/api/v1');
    });

    test('trims whitespace', () {
      final Uri uri = normalizeServerUri('  example.com  ');
      expect(uri.host, 'example.com');
    });

    test('throws on empty input', () {
      expect(() => normalizeServerUri(''), throwsFormatException);
    });

    test('throws on whitespace-only input', () {
      expect(() => normalizeServerUri('   '), throwsFormatException);
    });
  });

  group('describeServer', () {
    test('returns host without port', () {
      final Uri uri = Uri.parse('https://example.com');
      expect(describeServer(uri), 'example.com');
    });

    test('returns host:port when port is explicit', () {
      final Uri uri = Uri.parse('http://localhost:8080');
      expect(describeServer(uri), 'localhost:8080');
    });
  });
}
