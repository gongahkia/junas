import 'dart:async';

import 'package:app_links/app_links.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import 'core/deep_links/invite_links.dart';
import 'core/router/app_router.dart';
import 'core/theme/app_theme.dart';

class KilterTogetherApp extends StatefulWidget {
  const KilterTogetherApp({super.key});

  @override
  State<KilterTogetherApp> createState() => _KilterTogetherAppState();
}

class _KilterTogetherAppState extends State<KilterTogetherApp> {
  late final GoRouter _router = buildAppRouter();
  final AppLinks _appLinks = AppLinks();
  StreamSubscription<Uri>? _linkSubscription;

  @override
  void initState() {
    super.initState();
    unawaited(_bindDeepLinks());
  }

  @override
  void dispose() {
    final StreamSubscription<Uri>? subscription = _linkSubscription;
    _linkSubscription = null;
    if (subscription != null) {
      unawaited(subscription.cancel());
    }
    super.dispose();
  }

  Future<void> _bindDeepLinks() async {
    final Uri? initialLink = await _appLinks.getInitialLink();
    if (initialLink != null) {
      _openInvite(initialLink.toString());
    }

    _linkSubscription = _appLinks.uriLinkStream.listen((Uri uri) {
      _openInvite(uri.toString());
    });
  }

  void _openInvite(String raw) {
    final InviteLink? invite = InviteLink.parse(raw);
    if (invite == null || !mounted) {
      return;
    }

    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) {
        return;
      }

      switch (invite.kind) {
        case InviteKind.join:
          _router.goNamed(
            'join-room',
            queryParameters: invite.toRouteQueryParameters(),
          );
          return;
        case InviteKind.recap:
          _router.goNamed(
            'recap',
            queryParameters: invite.toRouteQueryParameters(),
          );
          return;
        case InviteKind.plan:
          _router.goNamed(
            'plan',
            queryParameters: invite.toRouteQueryParameters(),
          );
          return;
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      title: 'Kilter Together',
      theme: buildAppTheme(),
      routerConfig: _router,
      debugShowCheckedModeBanner: false,
    );
  }
}
