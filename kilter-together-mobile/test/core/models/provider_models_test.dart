import 'package:flutter_test/flutter_test.dart';
import 'package:kilter_together_mobile/core/models/provider_models.dart';

void main() {
  group('ProviderClimb', () {
    test('fromJson parses all fields', () {
      final ProviderClimb climb =
          ProviderClimb.fromJson(const <String, dynamic>{
        'id': 'c1',
        'external_id': 'ext-1',
        'provider_id': 'kilter',
        'surface_id': 'board-1',
        'name': 'Test Route',
        'description': 'A fun problem',
        'setter_name': 'John',
        'primary_grade': 'V5',
        'secondary_grade': '6C',
        'created_at': '2025-01-01',
        'popularity': 42,
        'media': <Map<String, dynamic>>[
          <String, dynamic>{
            'url': 'https://example.com/img.png',
            'kind': 'image'
          },
        ],
        'highlighted_holds': <Map<String, dynamic>>[
          <String, dynamic>{
            'position': 1,
            'x': 0.5,
            'y': 0.8,
            'role': 'start',
            'color': 'green'
          },
        ],
        'meta': <String, dynamic>{'angle': '40'},
      });
      expect(climb.id, 'c1');
      expect(climb.externalId, 'ext-1');
      expect(climb.name, 'Test Route');
      expect(climb.description, 'A fun problem');
      expect(climb.setterName, 'John');
      expect(climb.primaryGrade, 'V5');
      expect(climb.secondaryGrade, '6C');
      expect(climb.popularity, 42);
      expect(climb.media.length, 1);
      expect(climb.media[0].url, 'https://example.com/img.png');
      expect(climb.highlightedHolds.length, 1);
      expect(climb.highlightedHolds[0].role, 'start');
      expect(climb.meta['angle'], '40');
    });

    test('toJson roundtrip preserves data', () {
      const ProviderClimb original = ProviderClimb(
        id: 'c1',
        externalId: 'ext-1',
        providerId: 'kilter',
        surfaceId: 'board-1',
        name: 'Test',
        primaryGrade: 'V3',
        media: <ProviderClimbMedia>[
          ProviderClimbMedia(url: 'http://example.com', kind: 'video'),
        ],
        highlightedHolds: <HighlightedHold>[
          HighlightedHold(
              position: 0, x: 0.1, y: 0.2, role: 'finish', color: 'red'),
        ],
      );
      final ProviderClimb restored = ProviderClimb.fromJson(original.toJson());
      expect(restored.id, original.id);
      expect(restored.name, original.name);
      expect(restored.primaryGrade, original.primaryGrade);
      expect(restored.media.length, 1);
      expect(restored.media[0].kind, 'video');
      expect(restored.highlightedHolds.length, 1);
      expect(restored.highlightedHolds[0].color, 'red');
    });

    test('fromJson handles empty json', () {
      final ProviderClimb climb =
          ProviderClimb.fromJson(const <String, dynamic>{});
      expect(climb.id, '');
      expect(climb.name, '');
      expect(climb.media.isEmpty, true);
      expect(climb.highlightedHolds.isEmpty, true);
      expect(climb.popularity, isNull);
    });
  });

  group('ProviderSurface', () {
    test('fromJson/toJson roundtrip', () {
      const ProviderSurface surface = ProviderSurface(
        id: 's1',
        kind: 'board',
        name: 'Original 40',
        description: 'The OG board',
        parentId: 'gym-1',
        meta: <String, String>{'angle': '40'},
      );
      final ProviderSurface restored =
          ProviderSurface.fromJson(surface.toJson());
      expect(restored.id, 's1');
      expect(restored.kind, 'board');
      expect(restored.name, 'Original 40');
      expect(restored.description, 'The OG board');
      expect(restored.parentId, 'gym-1');
      expect(restored.meta['angle'], '40');
    });

    test('fromJson defaults', () {
      final ProviderSurface surface =
          ProviderSurface.fromJson(const <String, dynamic>{});
      expect(surface.id, '');
      expect(surface.kind, '');
      expect(surface.name, '');
      expect(surface.description, isNull);
      expect(surface.parentId, isNull);
    });
  });

  group('ProviderConnectionState', () {
    test('fromJson parses correctly', () {
      final ProviderConnectionState conn =
          ProviderConnectionState.fromJson(const <String, dynamic>{
        'connected': true,
        'provider_id': 'kilter',
        'metadata': <String, dynamic>{'version': '2.0'},
      });
      expect(conn.connected, true);
      expect(conn.providerId, 'kilter');
      expect(conn.metadata['version'], '2.0');
    });

    test('defaults for empty json', () {
      final ProviderConnectionState conn =
          ProviderConnectionState.fromJson(const <String, dynamic>{});
      expect(conn.connected, false);
      expect(conn.providerId, '');
      expect(conn.metadata.isEmpty, true);
    });
  });

  group('ProviderCapability.fromJson', () {
    test('parses with auth fields', () {
      final ProviderCapability cap =
          ProviderCapability.fromJson(<String, dynamic>{
        'id': 'kilter',
        'label': 'Kilter Board',
        'room_supported': true,
        'solo_supported': true,
        'surface_hierarchy': 'board',
        'auth_fields': <Map<String, dynamic>>[
          <String, dynamic>{
            'key': 'username',
            'label': 'Username',
            'type': 'text',
            'placeholder': 'Enter username',
          },
        ],
        'features': <String>['solo', 'room'],
      });
      expect(cap.id, 'kilter');
      expect(cap.label, 'Kilter Board');
      expect(cap.roomSupported, true);
      expect(cap.soloSupported, true);
      expect(cap.authFields.length, 1);
      expect(cap.authFields[0].key, 'username');
      expect(cap.authFields[0].placeholder, 'Enter username');
      expect(cap.supportsFeature('solo'), true);
      expect(cap.supportsFeature('plans'), false);
    });

    test('defaults for empty json', () {
      final ProviderCapability cap =
          ProviderCapability.fromJson(const <String, dynamic>{});
      expect(cap.id, '');
      expect(cap.roomSupported, false);
      expect(cap.authFields.isEmpty, true);
    });
  });

  group('ProviderAuthField', () {
    test('toJson roundtrip', () {
      const ProviderAuthField field = ProviderAuthField(
        key: 'token',
        label: 'API Token',
        type: 'password',
        placeholder: 'Enter token',
        autocomplete: 'off',
      );
      final ProviderAuthField restored =
          ProviderAuthField.fromJson(field.toJson());
      expect(restored.key, 'token');
      expect(restored.label, 'API Token');
      expect(restored.type, 'password');
      expect(restored.placeholder, 'Enter token');
      expect(restored.autocomplete, 'off');
    });
  });

  group('HighlightedHold', () {
    test('toJson roundtrip', () {
      const HighlightedHold hold = HighlightedHold(
        position: 3,
        x: 0.45,
        y: 0.67,
        role: 'start',
        color: 'green',
      );
      final HighlightedHold restored = HighlightedHold.fromJson(hold.toJson());
      expect(restored.position, 3);
      expect(restored.x, closeTo(0.45, 0.001));
      expect(restored.y, closeTo(0.67, 0.001));
      expect(restored.role, 'start');
      expect(restored.color, 'green');
    });
  });

  group('ProviderClimbMedia', () {
    test('toJson roundtrip', () {
      const ProviderClimbMedia media =
          ProviderClimbMedia(url: 'http://example.com/vid.mp4', kind: 'video');
      final ProviderClimbMedia restored =
          ProviderClimbMedia.fromJson(media.toJson());
      expect(restored.url, 'http://example.com/vid.mp4');
      expect(restored.kind, 'video');
    });
  });
}
