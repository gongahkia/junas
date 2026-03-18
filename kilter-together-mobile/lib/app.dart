import 'dart:async';

import 'package:app_links/app_links.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'core/deep_links/invite_links.dart';
import 'core/presentation/tap_cheer_overlay.dart';
import 'core/router/app_router.dart';
import 'core/storage/offline_kilter_catalog_controller.dart';
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
    WidgetsBinding.instance.addObserver(_lifecycleObserver);
    unawaited(_bindDeepLinks());
    unawaited(ref
        .read(offlineKilterCatalogControllerProvider.notifier)
        .autoSyncIfNeeded());
  }

  late final WidgetsBindingObserver _lifecycleObserver =
      _CatalogLifecycleObserver(
    onResumed: () => ref
        .read(offlineKilterCatalogControllerProvider.notifier)
        .autoSyncIfNeeded(),
  );

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(_lifecycleObserver);
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
    final RoomJoinTarget? joinTarget = invite == null
        ? parseRoomJoinTarget(raw)
        : invite.kind == InviteKind.join &&
                (invite.slug ?? '').trim().isNotEmpty
            ? RoomJoinTarget(
                slug: invite.slug!.trim(),
                server: invite.server,
              )
            : null;
    if (!mounted) {
      return;
    }

    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) {
        return;
      }

      if (joinTarget != null && joinTarget.server != null) {
        _router.goNamed(
          'join-room',
          queryParameters: <String, String>{
            'server': joinTarget.server.toString(),
            'slug': joinTarget.slug,
          },
        );
        return;
      }

      if (invite == null) {
        return;
      }

      switch (invite.kind) {
        case InviteKind.join:
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
    final bool clickCheersEnabled = false;

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

class _CatalogLifecycleObserver extends WidgetsBindingObserver {
  _CatalogLifecycleObserver({
    required this.onResumed,
  });

  final Future<void> Function() onResumed;

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      unawaited(onResumed());
    }
  }
}
