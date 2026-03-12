import 'package:flutter/widgets.dart';
import 'package:go_router/go_router.dart';

import '../../features/create_room/presentation/create_room_screen.dart';
import '../../features/join/presentation/join_screen.dart';
import '../../features/landing/presentation/landing_screen.dart';
import '../../features/plan/presentation/plan_screen.dart';
import '../../features/recap/presentation/recap_screen.dart';
import '../../features/room/presentation/room_screen.dart';
import '../../features/settings/presentation/settings_screen.dart';
import '../../features/solo_entry/presentation/solo_entry_screen.dart';
import '../../features/solo_kilter/presentation/solo_board_screen.dart';
import '../../features/solo_provider/presentation/provider_solo_screen.dart';

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
            initialReason: state.uri.queryParameters['reason'],
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
      GoRoute(
        path: '/solo',
        name: 'solo-entry',
        builder: (BuildContext context, GoRouterState state) {
          return const SoloEntryScreen();
        },
      ),
      GoRoute(
        path: '/solo/boards/:boardId',
        name: 'solo-board',
        builder: (BuildContext context, GoRouterState state) {
          return SoloBoardScreen(
            boardId: state.pathParameters['boardId'] ?? '',
            initialServer: state.uri.queryParameters['server'],
            initialAngle:
                int.tryParse(state.uri.queryParameters['angle'] ?? ''),
            initialSort: state.uri.queryParameters['sort'],
            initialQuery: state.uri.queryParameters['q'],
            initialSetter: state.uri.queryParameters['setter'],
            initialGrade: state.uri.queryParameters['grade'],
            initialClimbUuid: state.uri.queryParameters['climb'],
          );
        },
      ),
      GoRoute(
        path: '/solo/providers/:providerId',
        name: 'solo-provider',
        builder: (BuildContext context, GoRouterState state) {
          return ProviderSoloScreen(
            providerId: state.pathParameters['providerId'] ?? '',
            initialServer: state.uri.queryParameters['server'],
          );
        },
      ),
      GoRoute(
        path: '/recap',
        name: 'recap',
        builder: (BuildContext context, GoRouterState state) {
          return RecapScreen(
            server: state.uri.queryParameters['server'] ?? '',
            shareId: state.uri.queryParameters['share_id'] ??
                state.uri.queryParameters['shareId'] ??
                '',
          );
        },
      ),
      GoRoute(
        path: '/plan',
        name: 'plan',
        builder: (BuildContext context, GoRouterState state) {
          return PlanScreen(
            server: state.uri.queryParameters['server'] ?? '',
            shareId: state.uri.queryParameters['share_id'] ??
                state.uri.queryParameters['shareId'] ??
                '',
          );
        },
      ),
      GoRoute(
        path: '/settings',
        name: 'settings',
        builder: (BuildContext context, GoRouterState state) {
          return const SettingsScreen();
        },
      ),
    ],
  );
}
