import 'dart:async';

import 'package:app_links/app_links.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'core/deep_links/invite_links.dart';
import 'core/presentation/tap_cheer_overlay.dart';
import 'core/router/app_router.dart';
import 'core/storage/app_prefs_controller.dart';
import 'core/theme/app_theme.dart';

class KilterTogetherApp extends ConsumerStatefulWidget {
  const KilterTogetherApp({super.key});

  @override
  ConsumerState<KilterTogetherApp> createState() => _KilterTogetherAppState();
}

class _KilterTogetherAppState extends ConsumerState<KilterTogetherApp> {
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
    final bool clickCheersEnabled = ref
            .watch(appPrefsControllerProvider)
            .valueOrNull
            ?.settings
            .clickCheersEnabled ??
        true;

    return MaterialApp.router(
      title: 'Kilter Together',
      theme: buildAppTheme(),
      routerConfig: _router,
      builder: (BuildContext context, Widget? child) {
        return TapCheerOverlay(
          enabled: clickCheersEnabled,
          child: child ?? const SizedBox.shrink(),
        );
      },
      debugShowCheckedModeBanner: false,
    );
  }
}
