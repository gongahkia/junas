import 'package:flutter/widgets.dart';
import 'package:go_router/go_router.dart';
import '../../features/about/presentation/about_screen.dart';
import '../../features/create_room/presentation/create_room_screen.dart';
import '../../features/join/presentation/join_screen.dart';
import '../../features/session/presentation/session_home_screen.dart';
import '../../features/plan/presentation/plan_screen.dart';
import '../../features/recap/presentation/recap_screen.dart';
import '../../features/room/presentation/room_screen.dart';
import '../../features/climb_log/presentation/climb_log_screen.dart';
import '../../features/settings/presentation/settings_screen.dart';
import '../../features/solo_entry/presentation/solo_entry_screen.dart';
import '../../features/solo_kilter/presentation/solo_board_screen.dart';
import '../../features/solo_provider/presentation/provider_solo_screen.dart';
import '../presentation/app_shell.dart';

GoRouter buildAppRouter() {
  return GoRouter(
    initialLocation: '/',
    routes: <RouteBase>[
      StatefulShellRoute.indexedStack(
        builder: (BuildContext context, GoRouterState state, StatefulNavigationShell navigationShell) {
          return AppShell(navigationShell: navigationShell);
        },
        branches: <StatefulShellBranch>[
          // branch 0: session
          StatefulShellBranch(routes: <RouteBase>[
            GoRoute(
              path: '/',
              name: 'session-home',
              builder: (BuildContext context, GoRouterState state) => const SessionHomeScreen(),
            ),
            GoRoute(
              path: '/create',
              name: 'create-room',
              builder: (BuildContext context, GoRouterState state) => const CreateRoomScreen(),
            ),
            GoRoute(
              path: '/join',
              name: 'join-room',
              builder: (BuildContext context, GoRouterState state) {
                return JoinRoomScreen(
                  initialSlug: state.uri.queryParameters['slug'],
                  initialReason: state.uri.queryParameters['reason'],
                );
              },
            ),
            GoRoute(
              path: '/room',
              name: 'room',
              builder: (BuildContext context, GoRouterState state) {
                return RoomScreen(
                  slug: state.uri.queryParameters['slug'] ?? '',
                  role: state.uri.queryParameters['role'] ?? 'host',
                  displayName: state.uri.queryParameters['display_name'],
                  hostPeerId: state.uri.queryParameters['host_peer_id'],
                  hostPeerName: state.uri.queryParameters['host_peer_name'],
                );
              },
            ),
            GoRoute(
              path: '/recap',
              name: 'recap',
              builder: (BuildContext context, GoRouterState state) {
                return RecapScreen(
                  shareId: state.uri.queryParameters['share_id'] ??
                      state.uri.queryParameters['shareId'] ?? '',
                );
              },
            ),
          ]),
          // branch 1: solo
          StatefulShellBranch(routes: <RouteBase>[
            GoRoute(
              path: '/solo',
              name: 'solo-entry',
              builder: (BuildContext context, GoRouterState state) => const SoloEntryScreen(),
            ),
            GoRoute(
              path: '/solo/boards/:boardId',
              name: 'solo-board',
              builder: (BuildContext context, GoRouterState state) {
                return SoloBoardScreen(
                  boardId: state.pathParameters['boardId'] ?? '',
                  initialAngle: int.tryParse(state.uri.queryParameters['angle'] ?? ''),
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
                  initialParentSurfaceId: state.uri.queryParameters['gym'],
                  initialChildSurfaceId: state.uri.queryParameters['wall'],
                  initialQuery: state.uri.queryParameters['q'],
                  initialSort: state.uri.queryParameters['sort'],
                  initialClimbId: state.uri.queryParameters['climb'],
                );
              },
            ),
            GoRoute(
              path: '/plan',
              name: 'plan',
              builder: (BuildContext context, GoRouterState state) {
                return PlanScreen(
                  shareId: state.uri.queryParameters['share_id'] ??
                      state.uri.queryParameters['shareId'] ?? '',
                );
              },
            ),
          ]),
          // branch 2: log
          StatefulShellBranch(routes: <RouteBase>[
            GoRoute(
              path: '/log',
              name: 'climb-log',
              builder: (BuildContext context, GoRouterState state) => const ClimbLogScreen(),
            ),
          ]),
          // branch 3: settings
          StatefulShellBranch(routes: <RouteBase>[
            GoRoute(
              path: '/settings',
              name: 'settings',
              builder: (BuildContext context, GoRouterState state) => const SettingsScreen(),
            ),
            GoRoute(
              path: '/about',
              name: 'about',
              builder: (BuildContext context, GoRouterState state) => const AboutScreen(),
            ),
          ]),
        ],
      ),
    ],
  );
}
