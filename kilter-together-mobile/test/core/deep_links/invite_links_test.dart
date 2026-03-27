import 'package:flutter_test/flutter_test.dart';
import 'package:kilter_together_mobile/core/deep_links/invite_links.dart';

void main() {
  group('InviteLink.parse', () {
    test('parses join link', () {
      final InviteLink? link =
          InviteLink.parse('kiltertogether://join?slug=abc123');
      expect(link, isNotNull);
      expect(link!.kind, InviteKind.join);
      expect(link.slug, 'abc123');
    });

    test('parses recap link with share_id', () {
      final InviteLink? link =
          InviteLink.parse('kiltertogether://recap?share_id=xyz');
      expect(link, isNotNull);
      expect(link!.kind, InviteKind.recap);
      expect(link.shareId, 'xyz');
    });

    test('parses recap link with shareId (camelCase)', () {
      final InviteLink? link =
          InviteLink.parse('kiltertogether://recap?shareId=abc');
      expect(link, isNotNull);
      expect(link!.shareId, 'abc');
    });

    test('parses plan link', () {
      final InviteLink? link =
          InviteLink.parse('kiltertogether://plan?share_id=plan123');
      expect(link, isNotNull);
      expect(link!.kind, InviteKind.plan);
      expect(link.shareId, 'plan123');
    });

    test('returns null for empty string', () {
      expect(InviteLink.parse(''), isNull);
    });

    test('returns null for whitespace', () {
      expect(InviteLink.parse('   '), isNull);
    });

    test('returns null for wrong scheme', () {
      expect(InviteLink.parse('https://join?slug=abc'), isNull);
    });

    test('returns null for unknown host', () {
      expect(InviteLink.parse('kiltertogether://unknown?slug=abc'), isNull);
    });

    test('trims whitespace before parsing', () {
      final InviteLink? link =
          InviteLink.parse('  kiltertogether://join?slug=trimmed  ');
      expect(link, isNotNull);
      expect(link!.slug, 'trimmed');
    });

    test('join link without slug parameter', () {
      final InviteLink? link = InviteLink.parse('kiltertogether://join');
      expect(link, isNotNull);
      expect(link!.kind, InviteKind.join);
      expect(link.slug, isNull);
    });

    test('returns null for completely invalid URI', () {
      expect(InviteLink.parse('not a uri at all :::'), isNull);
    });
  });

  group('InviteLink.toUri', () {
    test('join link roundtrip', () {
      const InviteLink link =
          InviteLink(kind: InviteKind.join, slug: 'test123');
      final String raw = link.toUri().toString();
      final InviteLink? parsed = InviteLink.parse(raw);
      expect(parsed, isNotNull);
      expect(parsed!.kind, InviteKind.join);
      expect(parsed.slug, 'test123');
    });

    test('recap link roundtrip', () {
      const InviteLink link =
          InviteLink(kind: InviteKind.recap, shareId: 'share-abc');
      final String raw = link.toUri().toString();
      final InviteLink? parsed = InviteLink.parse(raw);
      expect(parsed, isNotNull);
      expect(parsed!.kind, InviteKind.recap);
      expect(parsed.shareId, 'share-abc');
    });

    test('plan link roundtrip', () {
      const InviteLink link =
          InviteLink(kind: InviteKind.plan, shareId: 'plan-xyz');
      final String raw = link.toUri().toString();
      final InviteLink? parsed = InviteLink.parse(raw);
      expect(parsed, isNotNull);
      expect(parsed!.kind, InviteKind.plan);
      expect(parsed.shareId, 'plan-xyz');
    });

    test('toUri omits empty slug', () {
      const InviteLink link = InviteLink(kind: InviteKind.join);
      final Uri uri = link.toUri();
      expect(uri.queryParameters.containsKey('slug'), false);
    });

    test('toUri omits empty shareId', () {
      const InviteLink link = InviteLink(kind: InviteKind.recap, shareId: '');
      final Uri uri = link.toUri();
      expect(uri.queryParameters.containsKey('share_id'), false);
    });
  });

  group('InviteLink.toRouteQueryParameters', () {
    test('includes slug for join link', () {
      const InviteLink link = InviteLink(kind: InviteKind.join, slug: 'abc');
      final Map<String, String> params = link.toRouteQueryParameters();
      expect(params['slug'], 'abc');
      expect(params.containsKey('share_id'), false);
    });

    test('includes share_id for recap link', () {
      const InviteLink link =
          InviteLink(kind: InviteKind.recap, shareId: 'xyz');
      final Map<String, String> params = link.toRouteQueryParameters();
      expect(params['share_id'], 'xyz');
      expect(params.containsKey('slug'), false);
    });

    test('empty map when no params set', () {
      const InviteLink link = InviteLink(kind: InviteKind.join);
      expect(link.toRouteQueryParameters(), isEmpty);
    });
  });
}
