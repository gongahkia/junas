import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import 'core/router/app_router.dart';
import 'core/theme/app_theme.dart';

class KilterTogetherApp extends StatefulWidget {
  const KilterTogetherApp({super.key});

  @override
  State<KilterTogetherApp> createState() => _KilterTogetherAppState();
}

class _KilterTogetherAppState extends State<KilterTogetherApp> {
  late final GoRouter _router = buildAppRouter();

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

