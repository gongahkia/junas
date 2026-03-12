import 'package:flutter/widgets.dart';
import 'package:go_router/go_router.dart';

import '../../features/create_room/presentation/create_room_screen.dart';
import '../../features/join/presentation/join_screen.dart';
import '../../features/landing/presentation/landing_screen.dart';
import '../../features/room/presentation/room_screen.dart';

GoRouter buildAppRouter() {
  return GoRouter(
    initialLocation: '/',
    routes: <RouteBase>[
      GoRoute(
        path: '/',
        name: 'landing',
        builder: (BuildContext context, GoRouterState state) {
          return const LandingScreen();
        },
      ),
      GoRoute(
        path: '/create',
        name: 'create-room',
        builder: (BuildContext context, GoRouterState state) {
          return const CreateRoomScreen();
        },
      ),
      GoRoute(
        path: '/join',
        name: 'join-room',
        builder: (BuildContext context, GoRouterState state) {
          return JoinRoomScreen(
            initialServer: state.uri.queryParameters['server'],
            initialSlug: state.uri.queryParameters['slug'],
          );
        },
      ),
      GoRoute(
        path: '/room',
        name: 'room',
        builder: (BuildContext context, GoRouterState state) {
          final String? server = state.uri.queryParameters['server'];
          final String? slug = state.uri.queryParameters['slug'];
          return RoomScreen(
            server: server ?? '',
            slug: slug ?? '',
          );
        },
      ),
    ],
  );
}

