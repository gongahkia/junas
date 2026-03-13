import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:kilter_together_mobile/core/deep_links/invite_links.dart';
import 'package:kilter_together_mobile/core/models/app_prefs_models.dart';
import 'package:kilter_together_mobile/core/models/product_models.dart';
import 'package:kilter_together_mobile/core/models/provider_models.dart';
import 'package:kilter_together_mobile/core/models/room_models.dart';
import 'package:kilter_together_mobile/core/models/session_models.dart';
import 'package:kilter_together_mobile/core/network/api_client.dart';
import 'package:kilter_together_mobile/core/network/sse_client.dart';
import 'package:kilter_together_mobile/core/router/app_router.dart';
import 'package:kilter_together_mobile/core/storage/app_preferences.dart';
import 'package:kilter_together_mobile/core/storage/secure_store.dart';
import 'package:kilter_together_mobile/core/storage/session_repository.dart';
import 'package:kilter_together_mobile/features/create_room/presentation/create_room_screen.dart';
import 'package:kilter_together_mobile/features/join/presentation/join_screen.dart';
import 'package:kilter_together_mobile/features/landing/presentation/landing_screen.dart';
import 'package:kilter_together_mobile/features/recap/presentation/recap_screen.dart';
import 'package:kilter_together_mobile/features/room/presentation/room_screen.dart';
import 'package:wakelock_plus_platform_interface/wakelock_plus_platform_interface.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  final WakelockPlusPlatformInterface originalWakelockPlatform =
      WakelockPlusPlatformInterface.instance;

  setUpAll(() {
    WakelockPlusPlatformInterface.instance = _FakeWakelockPlatform();
  });

  tearDownAll(() {
    WakelockPlusPlatformInterface.instance = originalWakelockPlatform;
  });

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

  testWidgets('landing auto-opens guide when unfinished',
      (WidgetTester tester) async {
    await _pumpScreen(
      tester,
      child: const LandingScreen(),
      appPreferences: FakeAppPreferences(
        prefs: _buildPrefs(),
      ),
      apiClient: FakeApiClient(),
    );

    await tester.pumpAndSettle();

    expect(find.text('How the app is split up'), findsOneWidget);
  });

  testWidgets(
      'landing does not auto-open guide when disabled, but manual help still works',
      (WidgetTester tester) async {
    await _pumpScreen(
      tester,
      child: const LandingScreen(),
      appPreferences: FakeAppPreferences(
        prefs: _buildPrefs(
          settings: _buildSettings(autoGuidesEnabled: false),
        ),
      ),
      apiClient: FakeApiClient(),
    );

    await tester.pumpAndSettle();

    expect(find.text('How the app is split up'), findsNothing);

    await tester.tap(find.byIcon(Icons.help_outline));
    await tester.pumpAndSettle();

    expect(find.text('How the app is split up'), findsOneWidget);
  });

  testWidgets('landing manual help works even after completion',
      (WidgetTester tester) async {
    await _pumpScreen(
      tester,
      child: const LandingScreen(),
      appPreferences: FakeAppPreferences(
        prefs: _buildPrefs(
          guidedTour: _buildGuidedTour(landingCompleted: true),
        ),
      ),
      apiClient: FakeApiClient(),
    );

    await tester.pumpAndSettle();

    expect(find.text('How the app is split up'), findsNothing);

    await tester.tap(find.byIcon(Icons.help_outline));
    await tester.pumpAndSettle();

    expect(find.text('How the app is split up'), findsOneWidget);
    expect(find.text('Done'), findsOneWidget);
  });

  testWidgets('completing the host guide prevents a future auto-open',
      (WidgetTester tester) async {
    final FakeAppPreferences appPreferences = FakeAppPreferences(
      activeServer: _server,
      prefs: _buildPrefs(
        guidedTour: _buildGuidedTour(activeBranch: 'host'),
      ),
    );

    await _pumpScreen(
      tester,
      child: const CreateRoomScreen(),
      appPreferences: appPreferences,
      apiClient: FakeApiClient(),
    );

    await tester.pumpAndSettle();
    expect(find.text('Open the room from this phone'), findsOneWidget);

    await tester.ensureVisible(find.text('Mark host guide complete'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Mark host guide complete'));
    await tester.pumpAndSettle();
    expect(find.text('Open the room from this phone'), findsNothing);

    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pumpAndSettle();

    await _pumpScreen(
      tester,
      child: const CreateRoomScreen(),
      appPreferences: appPreferences,
      apiClient: FakeApiClient(),
    );

    await tester.pumpAndSettle();
    expect(find.text('Open the room from this phone'), findsNothing);
  });

  testWidgets('create-room failure shows the mobile feedback prompt',
      (WidgetTester tester) async {
    final FakeApiClient apiClient = FakeApiClient()
      ..capabilities = <ProviderCapability>[
        const ProviderCapability(
          id: 'kilter',
          label: 'Kilter',
          roomSupported: true,
          soloSupported: true,
          surfaceHierarchy: 'board',
          authFields: <ProviderAuthField>[],
        ),
      ]
      ..createFailure = const ApiFailure(message: 'Bad provider credentials.');

    await _pumpScreen(
      tester,
      child: const CreateRoomScreen(),
      appPreferences: FakeAppPreferences(
        activeServer: _server,
        prefs: _buildPrefs(),
      ),
      apiClient: apiClient,
    );

    await tester.pumpAndSettle();
    await tester.tap(find.text('Load providers'));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.text('Open room'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Open room'));
    await tester.pumpAndSettle();

    expect(find.text('Was the room creation failure useful?'), findsOneWidget);
  });

  testWidgets('join failure shows the mobile feedback prompt',
      (WidgetTester tester) async {
    final FakeApiClient apiClient = FakeApiClient()
      ..joinFailure = const ApiFailure(message: 'Room invite is invalid.');

    await _pumpScreen(
      tester,
      child: const JoinRoomScreen(
        initialServer: 'https://boards.example.com',
        initialSlug: 'moonboard-night',
      ),
      appPreferences: FakeAppPreferences(
        prefs: _buildPrefs(),
      ),
      apiClient: apiClient,
    );

    await tester.pumpAndSettle();
    await tester.tap(find.text('Join room'));
    await tester.pumpAndSettle();

    expect(find.text('Was the join failure useful?'), findsOneWidget);
  });

  testWidgets('recent rooms preview is capped and view-all can remove entries',
      (WidgetTester tester) async {
    await _pumpScreen(
      tester,
      child: const LandingScreen(),
      appPreferences: FakeAppPreferences(
        prefs: _buildPrefs(
          settings: _buildSettings(autoGuidesEnabled: false),
          recentRooms: <RecentRoom>[
            _recentRoom(1),
            _recentRoom(2),
            _recentRoom(3),
            _recentRoom(4),
          ],
        ),
      ),
      apiClient: FakeApiClient(),
    );

    await tester.pumpAndSettle();
    expect(find.byIcon(Icons.push_pin_outlined), findsNWidgets(3));
    expect(find.text('View all (4)'), findsOneWidget);

    await tester.ensureVisible(find.text('View all (4)'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('View all (4)'));
    await tester.pumpAndSettle();

    expect(find.text('Room 1'), findsOneWidget);
    expect(find.text('Room 4'), findsWidgets);
    expect(find.byIcon(Icons.delete_outline), findsNWidgets(4));

    final Finder room1Delete = find.descendant(
      of: find.ancestor(
        of: find.text('Room 1'),
        matching: find.byType(ListTile),
      ),
      matching: find.byIcon(Icons.delete_outline),
    );

    expect(room1Delete, findsOneWidget);
    await tester.ensureVisible(room1Delete);
    await tester.pumpAndSettle();
    await tester.tap(room1Delete);
    await tester.pumpAndSettle();

    expect(find.byIcon(Icons.delete_outline), findsNWidgets(3));
    expect(find.text('View all (4)'), findsNothing);
  });

  testWidgets('recent rooms can be pinned from the landing preview',
      (WidgetTester tester) async {
    await _pumpScreen(
      tester,
      child: const LandingScreen(),
      appPreferences: FakeAppPreferences(
        prefs: _buildPrefs(
          settings: _buildSettings(autoGuidesEnabled: false),
          recentRooms: <RecentRoom>[_recentRoom(1)],
        ),
      ),
      apiClient: FakeApiClient(),
    );

    await tester.pumpAndSettle();

    await tester.ensureVisible(find.byIcon(Icons.push_pin_outlined));
    await tester.pumpAndSettle();

    expect(find.byIcon(Icons.push_pin_outlined), findsOneWidget);

    await tester.tap(find.byIcon(Icons.push_pin_outlined));
    await tester.pumpAndSettle();

    expect(find.byIcon(Icons.push_pin), findsOneWidget);
  });

  testWidgets('about route is reachable through the router',
      (WidgetTester tester) async {
    final GoRouter router = buildAppRouter();

    await _pumpRouterApp(
      tester,
      router: router,
      appPreferences: FakeAppPreferences(
        prefs: _buildPrefs(
          settings: _buildSettings(autoGuidesEnabled: false),
        ),
      ),
      apiClient: FakeApiClient(),
    );

    router.go('/about');
    await tester.pumpAndSettle();

    expect(find.text('About Kilter Together'), findsOneWidget);
  });

  testWidgets('recap feedback prompt still appears on the final slide',
      (WidgetTester tester) async {
    final FakeApiClient apiClient = FakeApiClient()
      ..recap = RoomRecap(
        shareId: 'recap-1',
        roomSlug: 'room-1',
        roomName: 'Moonboard Session',
        providerId: 'kilter',
        surfaceName: 'Main Board',
        closedAt: DateTime.utc(2025, 1, 1),
        slides: const <RecapSlide>[
          RecapSlide(
            id: 'slide-1',
            eyebrow: 'Summary',
            title: 'Strong session',
            description: 'Everyone got on the board.',
          ),
        ],
      );

    await _pumpScreen(
      tester,
      child: const RecapScreen(
        server: 'https://boards.example.com',
        shareId: 'recap-1',
      ),
      appPreferences: FakeAppPreferences(
        prefs: _buildPrefs(),
      ),
      apiClient: apiClient,
    );

    await tester.pumpAndSettle();

    expect(find.text('How did this recap feel?'), findsOneWidget);
  });

  testWidgets('closing a room surfaces the host feedback prompt',
      (WidgetTester tester) async {
    final FakeAppPreferences appPreferences = FakeAppPreferences(
      activeServer: _server,
      prefs: _buildPrefs(
        settings: _buildSettings(autoGuidesEnabled: false),
      ),
    );
    final FakeSecureStore secureStore = FakeSecureStore();
    final SessionRepository sessionRepository = SessionRepository(
      appPreferences: appPreferences,
      secureStore: secureStore,
    );
    final FakeApiClient apiClient = FakeApiClient()
      ..room = _room(
        status: 'open',
        permissions: const RoomPermissions(
          manageSession: true,
          manageSurface: true,
          manageQueue: true,
          manageFinalists: true,
          editRoomSettings: true,
          manageParticipants: true,
          assignCoHosts: true,
          closeRoom: true,
        ),
      );

    await sessionRepository.saveSession(
      server: _server,
      slug: 'room-1',
      session: _session,
    );

    await _pumpScreen(
      tester,
      child: const RoomScreen(
        server: 'https://boards.example.com',
        slug: 'room-1',
      ),
      appPreferences: appPreferences,
      secureStore: secureStore,
      apiClient: apiClient,
      sseClient: FakeSseClient(),
    );

    await tester.pumpAndSettle();
    await tester.ensureVisible(find.text('Close room'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Close room'));
    await tester.pumpAndSettle();

    expect(apiClient.closeRoomCalled, isTrue);
    expect(find.text('How did closing the room feel?'), findsOneWidget);
  });
}

Future<void> _pumpScreen(
  WidgetTester tester, {
  required Widget child,
  FakeAppPreferences? appPreferences,
  FakeSecureStore? secureStore,
  FakeApiClient? apiClient,
  SseClient? sseClient,
}) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: <Override>[
        appPreferencesProvider.overrideWithValue(
          appPreferences ?? FakeAppPreferences(prefs: _buildPrefs()),
        ),
        secureStoreProvider.overrideWithValue(
          secureStore ?? FakeSecureStore(),
        ),
        apiClientProvider.overrideWithValue(apiClient ?? FakeApiClient()),
        sseClientProvider.overrideWithValue(sseClient ?? FakeSseClient()),
      ],
      child: MaterialApp(
        home: child,
      ),
    ),
  );
  await tester.pump();
}

Future<void> _pumpRouterApp(
  WidgetTester tester, {
  required GoRouter router,
  FakeAppPreferences? appPreferences,
  FakeSecureStore? secureStore,
  FakeApiClient? apiClient,
}) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: <Override>[
        appPreferencesProvider.overrideWithValue(
          appPreferences ?? FakeAppPreferences(prefs: _buildPrefs()),
        ),
        secureStoreProvider.overrideWithValue(
          secureStore ?? FakeSecureStore(),
        ),
        apiClientProvider.overrideWithValue(apiClient ?? FakeApiClient()),
        sseClientProvider.overrideWithValue(FakeSseClient()),
      ],
      child: MaterialApp.router(routerConfig: router),
    ),
  );
  await tester.pump();
}

AppPrefs _buildPrefs({
  AppSettings? settings,
  GuidedTourProgress? guidedTour,
  List<RecentRoom>? recentRooms,
  Map<String, String>? feedbackPrompts,
}) {
  final AppPrefs defaults = AppPrefs.defaults();
  return AppPrefs(
    savedDisplayName: defaults.savedDisplayName,
    lastProviderId: defaults.lastProviderId,
    lastKilterBoardId: defaults.lastKilterBoardId,
    lastKilterAngle: defaults.lastKilterAngle,
    lastCruxGymSlug: defaults.lastCruxGymSlug,
    lastCruxWallId: defaults.lastCruxWallId,
    hostDefaults: defaults.hostDefaults,
    savedCredentials: defaults.savedCredentials,
    recentRooms: recentRooms ?? defaults.recentRooms,
    savedSoloFilters: defaults.savedSoloFilters,
    soloFavorites: defaults.soloFavorites,
    soloShortlist: defaults.soloShortlist,
    pendingRoomSeed: defaults.pendingRoomSeed,
    soloResume: defaults.soloResume,
    intro: defaults.intro,
    onboarding: defaults.onboarding,
    guidedTour: guidedTour ?? defaults.guidedTour,
    feedbackPrompts: feedbackPrompts ?? defaults.feedbackPrompts,
    settings: settings ?? defaults.settings,
  );
}

AppSettings _buildSettings({
  bool? autoGuidesEnabled,
  bool? recentRoomsEnabled,
}) {
  final AppSettings defaults = AppPrefs.defaults().settings;
  return AppSettings(
    clickCheersEnabled: defaults.clickCheersEnabled,
    playfulMotionEnabled: defaults.playfulMotionEnabled,
    autoGuidesEnabled: autoGuidesEnabled ?? defaults.autoGuidesEnabled,
    recentRoomsEnabled: recentRoomsEnabled ?? defaults.recentRoomsEnabled,
    soloDefaultSort: defaults.soloDefaultSort,
  );
}

GuidedTourProgress _buildGuidedTour({
  bool landingCompleted = false,
  bool hostCompleted = false,
  bool guestCompleted = false,
  bool soloCompleted = false,
  String? activeBranch,
}) {
  return GuidedTourProgress(
    version: 2,
    landingCompleted: landingCompleted,
    hostCompleted: hostCompleted,
    guestCompleted: guestCompleted,
    soloCompleted: soloCompleted,
    activeBranch: activeBranch,
  );
}

RecentRoom _recentRoom(int index, {bool pinned = false}) {
  return RecentRoom(
    server: _server.toString(),
    slug: 'room-$index',
    providerId: 'kilter',
    lastVisitedAt: DateTime.utc(2025, 1, index).toIso8601String(),
    roomName: 'Room $index',
    surfaceName: 'Board $index',
    pinned: pinned,
  );
}

RoomSnapshot _room({
  required String status,
  required RoomPermissions permissions,
}) {
  return RoomSnapshot(
    slug: 'room-1',
    roomName: 'Moonboard Night',
    status: status,
    providerId: 'kilter',
    version: status == 'closed' ? 2 : 1,
    surface: const ProviderSurface(
      id: 'board-1',
      kind: 'board',
      name: 'Main Board',
    ),
    connection: const ProviderConnectionState(
      connected: false,
      providerId: 'kilter',
    ),
    participants: const <Participant>[
      Participant(
        id: 1,
        displayName: 'Host',
        role: 'host',
        status: 'ready',
        isOnline: true,
      ),
    ],
    finalists: const <FinalistEntry>[],
    queue: const <QueueEntry>[],
    voteCounts: const <String, int>{},
    myVotes: const <String>[],
    fistBumpsEnabled: true,
    canManage: true,
    permissions: permissions,
    displayName: 'Host',
    assistant: const AssistantState(mode: 'manual'),
  );
}

final Uri _server = Uri(
  scheme: 'https',
  host: 'boards.example.com',
);

final RoomSession _session = RoomSession(
  token: 'session-token',
  role: 'host',
  expiresAt: DateTime.utc(2030, 1, 1),
);

class FakeAppPreferences extends AppPreferences {
  FakeAppPreferences({
    required AppPrefs prefs,
    this.activeServer,
    List<Uri>? recentServers,
  })  : _prefs = prefs,
        _recentServers = recentServers ?? <Uri>[];

  AppPrefs _prefs;
  Uri? activeServer;
  final List<Uri> _recentServers;

  @override
  Future<AppPrefs> loadAppPrefs() async => _prefs;

  @override
  Future<void> saveAppPrefs(AppPrefs appPrefs) async {
    _prefs = appPrefs;
  }

  @override
  Future<AppPrefs> updateAppPrefs(
      AppPrefs Function(AppPrefs current) updater) async {
    _prefs = updater(_prefs);
    return _prefs;
  }

  @override
  Future<Uri?> loadActiveServer() async => activeServer;

  @override
  Future<void> saveActiveServer(Uri server) async {
    activeServer = server;
  }

  @override
  Future<List<Uri>> loadRecentServers() async => List<Uri>.from(_recentServers);

  @override
  Future<void> rememberServer(Uri server) async {
    activeServer = server;
    _recentServers
      ..removeWhere((Uri item) => item == server)
      ..insert(0, server);
  }
}

class FakeSecureStore extends SecureStore {
  FakeSecureStore();

  final Map<String, String> _values = <String, String>{};

  @override
  Future<void> write(String key, String value) async {
    _values[key] = value;
  }

  @override
  Future<String?> read(String key) async => _values[key];

  @override
  Future<void> delete(String key) async {
    _values.remove(key);
  }
}

class FakeApiClient extends ApiClient {
  FakeApiClient();

  List<ProviderCapability> capabilities = const <ProviderCapability>[];
  List<SessionSummary> recentSessions = const <SessionSummary>[];
  ApiFailure? createFailure;
  ApiFailure? joinFailure;
  RoomRecap? recap;
  RoomSnapshot? room;
  bool closeRoomCalled = false;

  @override
  Future<List<ProviderCapability>> getProviderCapabilities(Uri server) async {
    return capabilities;
  }

  @override
  Future<List<SessionSummary>> getRecentSessions({
    required Uri server,
    int limit = 6,
  }) async {
    return recentSessions;
  }

  @override
  Future<RoomSessionEnvelope> createRoom({
    required Uri server,
    required String providerId,
    required String roomName,
    required String displayName,
    required Map<String, String> secret,
    required bool fistBumpsEnabled,
  }) async {
    if (createFailure != null) {
      throw createFailure!;
    }
    return RoomSessionEnvelope(
      room: room ??
          _room(
            status: 'open',
            permissions: const RoomPermissions(
              manageSession: true,
              manageSurface: true,
              manageQueue: true,
              manageFinalists: true,
              editRoomSettings: true,
              manageParticipants: true,
              assignCoHosts: true,
              closeRoom: true,
            ),
          ),
      session: _session,
    );
  }

  @override
  Future<RoomSessionEnvelope> joinRoom({
    required Uri server,
    required String slug,
    required String displayName,
  }) async {
    if (joinFailure != null) {
      throw joinFailure!;
    }
    return RoomSessionEnvelope(
      room: room ??
          _room(
            status: 'open',
            permissions: const RoomPermissions(
              manageSession: false,
              manageSurface: false,
              manageQueue: true,
              manageFinalists: true,
              editRoomSettings: false,
              manageParticipants: false,
              assignCoHosts: false,
              closeRoom: false,
            ),
          ),
      session: _session,
    );
  }

  @override
  Future<void> submitFeedback({
    required Uri server,
    String? roomSlug,
    String? shareId,
    required String promptFamily,
    required String sentiment,
    String? message,
    String? route,
    Map<String, dynamic> metadata = const <String, dynamic>{},
  }) async {}

  @override
  Future<RoomRecap> getRoomRecap({
    required Uri server,
    required String shareId,
  }) async {
    return recap!;
  }

  @override
  Future<RoomSnapshot> getRoom({
    required Uri server,
    required String slug,
    required String sessionToken,
  }) async {
    return room!;
  }

  @override
  Future<void> closeRoom({
    required Uri server,
    required String slug,
    required String sessionToken,
  }) async {
    closeRoomCalled = true;
    room = _room(
      status: 'closed',
      permissions: room!.permissions,
    );
  }
}

class FakeSseClient extends SseClient {
  FakeSseClient();

  @override
  Stream<SseMessage> connect({
    required Uri uri,
    required String sessionToken,
  }) {
    return const Stream<SseMessage>.empty();
  }
}

class _FakeWakelockPlatform extends WakelockPlusPlatformInterface {
  bool _enabled = false;

  @override
  Future<void> toggle({required bool enable}) async {
    _enabled = enable;
  }

  @override
  Future<bool> get enabled async => _enabled;
}
