import 'package:flutter_test/flutter_test.dart';
import 'package:kilter_together_mobile/core/deep_links/invite_links.dart';

void main() {
  test('parses join invites and normalizes the server URL', () {
    final InviteLink? invite = InviteLink.parse(
      'kiltertogether://join?server=demo.kilter.app/&slug=moonboard-night',
    );

    expect(invite, isNotNull);
    expect(invite!.kind, InviteKind.join);
    expect(invite.server.toString(), 'https://demo.kilter.app');
    expect(invite.slug, 'moonboard-night');
  });

  test('parses recap invites with share ids', () {
    final InviteLink? invite = InviteLink.parse(
      'kiltertogether://recap?server=https%3A%2F%2Flocalhost%3A8080&share_id=recap-123',
    );

    expect(invite, isNotNull);
    expect(invite!.kind, InviteKind.recap);
    expect(invite.server.toString(), 'https://localhost:8080');
    expect(invite.shareId, 'recap-123');
  });

  test('parses plan invites with camel-case share ids', () {
    final InviteLink? invite = InviteLink.parse(
      'kiltertogether://plan?server=https%3A%2F%2Fkilter.example&shareId=plan-42',
    );

    expect(invite, isNotNull);
    expect(invite!.kind, InviteKind.plan);
    expect(invite.shareId, 'plan-42');
  });

  test('rejects invalid invite schemes', () {
    expect(
      InviteLink.parse('https://kiltertogether.example/join?slug=nope'),
      isNull,
    );
  });
}
