import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:kilter_together_mobile/core/deep_links/invite_links.dart';
import 'package:kilter_together_mobile/core/models/app_prefs_models.dart';
import 'package:kilter_together_mobile/core/models/board_models.dart';
import 'package:kilter_together_mobile/core/models/catalog_models.dart';
import 'package:kilter_together_mobile/core/models/product_models.dart';
import 'package:kilter_together_mobile/core/models/provider_models.dart';
import 'package:kilter_together_mobile/core/models/room_models.dart';
import 'package:kilter_together_mobile/core/models/session_models.dart';
import 'package:kilter_together_mobile/core/network/api_client.dart';
import 'package:kilter_together_mobile/core/network/sse_client.dart';
import 'package:kilter_together_mobile/core/presentation/app_bottom_bar.dart';
import 'package:kilter_together_mobile/core/router/app_router.dart';
import 'package:kilter_together_mobile/core/storage/app_preferences.dart';
import 'package:kilter_together_mobile/core/storage/catalog_storage_platform.dart';
import 'package:kilter_together_mobile/core/storage/offline_kilter_catalog_controller.dart';
import 'package:kilter_together_mobile/core/storage/offline_kilter_catalog_repository.dart';
import 'package:kilter_together_mobile/core/storage/secure_store.dart';
import 'package:kilter_together_mobile/core/storage/session_repository.dart';
import 'package:kilter_together_mobile/features/create_room/presentation/create_room_screen.dart';
import 'package:kilter_together_mobile/features/join/presentation/join_screen.dart';
import 'package:kilter_together_mobile/features/landing/presentation/landing_screen.dart';
import 'package:kilter_together_mobile/features/recap/presentation/recap_screen.dart';
import 'package:kilter_together_mobile/features/room/presentation/room_screen.dart';
import 'package:kilter_together_mobile/features/settings/presentation/settings_screen.dart';
import 'package:kilter_together_mobile/features/solo_entry/presentation/solo_entry_screen.dart';
import 'package:kilter_together_mobile/features/solo_kilter/presentation/solo_board_screen.dart';
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

  test('extracts room slugs from original web join links', () {
    expect(
      extractRoomSlugFromValue(
        'https://boards.example.com/join/moonboard-night',
      ),
      'moonboard-night',
    );
    expect(
      extractRoomSlugFromValue(
        'https://boards.example.com/rooms/session-room',
      ),
      'session-room',
    );
  });

  test('resolves room join targets from web invite links', () {
    final RoomJoinTarget? target = parseRoomJoinTarget(
      'https://boards.example.com/join/moonboard-night',
    );

    expect(target, isNotNull);
    expect(target!.slug, 'moonboard-night');
    expect(target.server, _server);
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

  testWidgets('landing quick join routes web invites into the join flow',
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

    await tester.pumpAndSettle();

    await tester.enterText(
      find.widgetWithText(TextField, 'Invite or room slug'),
      'https://boards.example.com/join/moonboard-night',
    );
    final Finder quickJoinButton = find.widgetWithText(
      FilledButton,
      'Quick join',
    );
    await tester.dragUntilVisible(
      quickJoinButton,
      find.byType(ListView).first,
      const Offset(0, -160),
    );
    await tester.pumpAndSettle();
    await tester.tap(quickJoinButton);
    await tester.pumpAndSettle();

    final Finder serverField = find.byWidgetPredicate(
      (Widget widget) =>
          widget is TextField &&
          widget.decoration?.labelText == 'Self-hosted server URL' &&
          widget.controller?.text == 'https://boards.example.com',
    );
    final Finder inviteField = find.byWidgetPredicate(
      (Widget widget) =>
          widget is TextField &&
          widget.decoration?.labelText == 'Invite or room slug' &&
          widget.controller?.text == 'moonboard-night',
    );

    expect(serverField, findsOneWidget);
    expect(inviteField, findsOneWidget);
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
    await tester.ensureVisible(find.text('Create room'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Create room'));
    await tester.pumpAndSettle();

    expect(find.text('Was the room creation failure useful?'), findsOneWidget);
  });

  testWidgets('create room restores the saved Kilter username preference',
      (WidgetTester tester) async {
    final FakeApiClient apiClient = FakeApiClient()
      ..capabilities = <ProviderCapability>[
        const ProviderCapability(
          id: 'kilter',
          label: 'Kilter',
          roomSupported: true,
          soloSupported: true,
          surfaceHierarchy: 'board',
          authFields: <ProviderAuthField>[
            ProviderAuthField(
              key: 'username',
              label: 'Username',
              type: 'text',
            ),
            ProviderAuthField(
              key: 'password',
              label: 'Password',
              type: 'password',
            ),
          ],
        ),
      ];

    await _pumpScreen(
      tester,
      child: const CreateRoomScreen(),
      appPreferences: FakeAppPreferences(
        activeServer: _server,
        prefs: _buildPrefs(
          savedCredentials: const SavedCredentials(
            providers: <String, SavedCredentialPreference>{
              'kilter': SavedCredentialPreference(
                remember: true,
                username: 'captain',
              ),
              'crux': SavedCredentialPreference(remember: false),
            },
          ),
        ),
      ),
      apiClient: apiClient,
    );

    await tester.pumpAndSettle();
    await tester.tap(find.text('Load providers'));
    await tester.pumpAndSettle();

    final Finder usernameField = find.byWidgetPredicate(
      (Widget widget) =>
          widget is TextField &&
          widget.decoration?.labelText == 'Username' &&
          widget.controller?.text == 'captain',
    );
    expect(usernameField, findsOneWidget);

    final Finder rememberToggle = find.widgetWithText(
      SwitchListTile,
      'Remember Kilter username on this device',
    );
    expect(rememberToggle, findsOneWidget);
    expect(
      tester.widget<SwitchListTile>(rememberToggle).value,
      isTrue,
    );
    expect(
      find.text(
        'This room only opens after the Kilter credentials validate. The next step inside the room is choosing the board plus angle.',
      ),
      findsOneWidget,
    );
  });

  testWidgets(
      'create room shows Crux auth guidance and saves the remember preference',
      (WidgetTester tester) async {
    final FakeAppPreferences appPreferences = FakeAppPreferences(
      activeServer: _server,
      prefs: _buildPrefs(
        savedCredentials: const SavedCredentials(
          providers: <String, SavedCredentialPreference>{
            'kilter': SavedCredentialPreference(remember: false),
            'crux': SavedCredentialPreference(remember: false),
          },
        ),
      ),
    );
    final FakeApiClient apiClient = FakeApiClient()
      ..capabilities = <ProviderCapability>[
        const ProviderCapability(
          id: 'crux',
          label: 'Crux',
          roomSupported: true,
          soloSupported: true,
          surfaceHierarchy: 'nested',
          authFields: <ProviderAuthField>[
            ProviderAuthField(
              key: 'token',
              label: 'Token',
              type: 'password',
            ),
          ],
        ),
      ];

    await _pumpScreen(
      tester,
      child: const CreateRoomScreen(),
      appPreferences: appPreferences,
      apiClient: apiClient,
    );

    await tester.pumpAndSettle();

    expect(
      find.text(
          'Paste either the raw Crux token or the full Bearer ... value.'),
      findsOneWidget,
    );
    expect(
      find.text(
        'This room only opens after the Crux token validates. The next step inside the room is choosing the gym and wall.',
      ),
      findsOneWidget,
    );

    final Finder rememberToggle = find.widgetWithText(
      SwitchListTile,
      'Remember this Crux auth preference on this device',
    );
    expect(rememberToggle, findsOneWidget);
    expect(
      tester.widget<SwitchListTile>(rememberToggle).value,
      isFalse,
    );

    await tester.enterText(
      find.widgetWithText(TextField, 'Token'),
      'Bearer test-token',
    );
    await tester.dragUntilVisible(
      rememberToggle,
      find.byType(ListView).first,
      const Offset(0, -160),
    );
    await tester.pumpAndSettle();
    await tester.tap(rememberToggle);
    await tester.pumpAndSettle();
    final Finder submitButton = find.widgetWithText(
      FilledButton,
      'Validate and create room',
    );
    await tester.ensureVisible(submitButton);
    await tester.tap(submitButton);
    await tester.pumpAndSettle();

    expect(
      appPreferences._prefs.savedCredentials.providers['crux']?.remember,
      isTrue,
    );
  });

  testWidgets('create room auto-loads providers for the remembered server',
      (WidgetTester tester) async {
    final FakeApiClient apiClient = FakeApiClient()
      ..capabilities = <ProviderCapability>[
        const ProviderCapability(
          id: 'kilter',
          label: 'Kilter',
          roomSupported: true,
          soloSupported: true,
          surfaceHierarchy: 'board',
          authFields: <ProviderAuthField>[
            ProviderAuthField(
              key: 'username',
              label: 'Username',
              type: 'text',
            ),
          ],
        ),
      ];

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

    final Finder usernameField = find.byWidgetPredicate(
      (Widget widget) =>
          widget is TextField && widget.decoration?.labelText == 'Username',
    );
    expect(usernameField, findsOneWidget);
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

  testWidgets('join screen rejects non-room invites before hitting the API',
      (WidgetTester tester) async {
    await _pumpScreen(
      tester,
      child: const JoinRoomScreen(
        initialServer: 'https://boards.example.com',
        initialSlug:
            'kiltertogether://recap?server=https%3A%2F%2Fboards.example.com&share_id=recap-1',
      ),
      appPreferences: FakeAppPreferences(
        prefs: _buildPrefs(),
      ),
      apiClient: FakeApiClient(),
    );

    await tester.pumpAndSettle();
    await tester.tap(find.text('Join room'));
    await tester.pumpAndSettle();

    expect(
      find.text(
        'That link opens a recap, not a room invite. Ask the host for the room invite instead.',
      ),
      findsWidgets,
    );
  });

  testWidgets('join screen maps display-name conflicts to actionable copy',
      (WidgetTester tester) async {
    final FakeApiClient apiClient = FakeApiClient()
      ..joinFailure = const ApiFailure(
        message: 'display name is already taken',
        code: 'display_name_taken',
      );

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

    expect(
      find.text(
        'That display name is already taken in this room. Choose another name and try again.',
      ),
      findsOneWidget,
    );
  });

  testWidgets('join screen accepts web invite links from the original app',
      (WidgetTester tester) async {
    final FakeApiClient apiClient = FakeApiClient()
      ..joinFailure = const ApiFailure(
        message: 'display name is already taken',
        code: 'display_name_taken',
      );

    await _pumpScreen(
      tester,
      child: const JoinRoomScreen(
        initialSlug: 'https://boards.example.com/join/moonboard-night',
      ),
      appPreferences: FakeAppPreferences(
        prefs: _buildPrefs(),
      ),
      apiClient: apiClient,
    );

    await tester.pumpAndSettle();
    await tester.tap(find.text('Join room'));
    await tester.pumpAndSettle();

    expect(apiClient.lastJoinServer, _server);
    expect(apiClient.lastJoinSlug, 'moonboard-night');
    expect(
      find.text(
        'That display name is already taken in this room. Choose another name and try again.',
      ),
      findsOneWidget,
    );
  });

  testWidgets('recent rooms preview is capped and view-all can remove entries',
      (WidgetTester tester) async {
    final FakeAppPreferences appPreferences = FakeAppPreferences(
      prefs: _buildPrefs(
        settings: _buildSettings(autoGuidesEnabled: false),
        recentRooms: <RecentRoom>[
          _recentRoom(1),
          _recentRoom(2),
          _recentRoom(3),
          _recentRoom(4),
        ],
      ),
    );

    await _pumpScreen(
      tester,
      child: const LandingScreen(),
      appPreferences: appPreferences,
      apiClient: FakeApiClient(),
    );

    await tester.pumpAndSettle();
    expect(find.byIcon(Icons.push_pin_outlined), findsNWidgets(3));
    expect(find.text('View all (4)'), findsOneWidget);
    expect(find.text('Open room'), findsNWidgets(3));
    expect(find.textContaining('Last seen '), findsNWidgets(3));

    await tester.ensureVisible(find.text('View all (4)'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('View all (4)'));
    await tester.pumpAndSettle();

    expect(find.byIcon(Icons.delete_outline), findsWidgets);

    await tester.tap(find.byIcon(Icons.delete_outline).first);
    await tester.pumpAndSettle();

    expect(appPreferences._prefs.recentRooms.length, 3);
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
    expect(find.text('Open room'), findsOneWidget);

    await tester.tap(find.byIcon(Icons.push_pin_outlined));
    await tester.pumpAndSettle();

    expect(find.byIcon(Icons.push_pin_outlined), findsNothing);
    expect(find.text('Pinned'), findsOneWidget);
  });

  testWidgets('landing recent sessions show top-voted and wrap-up summaries',
      (WidgetTester tester) async {
    await _pumpScreen(
      tester,
      child: const LandingScreen(),
      appPreferences: FakeAppPreferences(
        activeServer: _server,
        prefs: _buildPrefs(
          settings: _buildSettings(autoGuidesEnabled: false),
        ),
      ),
      apiClient: FakeApiClient()
        ..recentSessions = <SessionSummary>[
          SessionSummary(
            roomSlug: 'room-1',
            roomName: 'Moonboard Session',
            providerId: 'kilter',
            surfaceName: 'Main Board',
            participantCount: 4,
            recapShareId: 'recap-1',
            closedAt: DateTime.utc(2025, 1, 1),
            topVoted: <SessionSummaryClimb>[
              SessionSummaryClimb(
                climb: _providerClimb(id: 'climb-1', name: 'Final Burn'),
                voteCount: 5,
              ),
            ],
            finalQueue: <SessionSummaryClimb>[
              SessionSummaryClimb(
                climb: _providerClimb(id: 'climb-1'),
              ),
              SessionSummaryClimb(
                climb: _providerClimb(id: 'climb-2'),
              ),
              SessionSummaryClimb(
                climb: _providerClimb(id: 'climb-3'),
              ),
            ],
            finalists: <SessionSummaryClimb>[
              SessionSummaryClimb(
                climb: _providerClimb(id: 'climb-1'),
              ),
              SessionSummaryClimb(
                climb: _providerClimb(id: 'climb-2'),
              ),
            ],
          ),
        ],
    );

    await tester.pumpAndSettle();

    expect(find.text('Top fist-bumped'), findsOneWidget);
    expect(find.text('Final Burn'), findsOneWidget);
    expect(find.text('5 fist bumps'), findsOneWidget);
    expect(find.text('3 queued · 2 finalists'), findsOneWidget);
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

  testWidgets('router shell shows the central bottom bar and navigates tabs',
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

    await tester.pumpAndSettle();

    expect(find.byType(AppBottomBar), findsOneWidget);
    expect(find.byIcon(Icons.home_rounded), findsOneWidget);

    await tester.tap(find.text('Solo'));
    await tester.pumpAndSettle();

    expect(find.text('Solo Browse'), findsOneWidget);
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

  testWidgets(
      'room screen shows share readiness blockers before invite handoff',
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
        connected: false,
        surface: null,
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

    expect(find.text('Room not ready to share yet'), findsOneWidget);
    expect(
      find.textContaining('Reconnect the provider'),
      findsWidgets,
    );

    final FilledButton shareButton = tester.widget<FilledButton>(
      find.widgetWithText(FilledButton, 'Share invite'),
    );
    expect(shareButton.onPressed, isNull);
  });

  testWidgets('room screen unlocks invite actions once the room is share-ready',
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
        connected: true,
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

    expect(find.text('Room is ready to share'), findsOneWidget);
    expect(find.text('Join path'), findsOneWidget);
    expect(find.text('/join/room-1'), findsOneWidget);

    final FilledButton shareButton = tester.widget<FilledButton>(
      find.widgetWithText(FilledButton, 'Share invite'),
    );
    expect(shareButton.onPressed, isNotNull);
  });

  testWidgets('room screen marks the invite as copied after copy action',
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
        connected: true,
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
    final Finder copyButton = find.widgetWithText(FilledButton, 'Copy invite');
    await tester.dragUntilVisible(
      copyButton,
      find.byType(ListView).first,
      const Offset(0, -200),
    );
    await tester.pumpAndSettle();
    await tester.tap(copyButton);
    await tester.pump(const Duration(milliseconds: 100));

    expect(find.text('Copied'), findsOneWidget);
  });

  testWidgets('room seed card clears imported seeds when every climb is queued',
      (WidgetTester tester) async {
    final FakeAppPreferences appPreferences = FakeAppPreferences(
      activeServer: _server,
      prefs: _buildPrefs(
        settings: _buildSettings(autoGuidesEnabled: false),
        pendingRoomSeed: PendingRoomSeed(
          providerId: 'kilter',
          surface: const ProviderSurface(
            id: 'board-1',
            kind: 'board',
            name: 'Main Board',
          ),
          climbs: <ProviderClimb>[_providerClimb(id: 'climb-1')],
          createdAt: DateTime.utc(2025, 1, 1).toIso8601String(),
        ),
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
        connected: true,
        queue: <QueueEntry>[
          QueueEntry(
            id: 1,
            status: 'queued',
            position: 1,
            addedBy: 'Host',
            climb: _providerClimb(id: 'climb-1'),
          ),
        ],
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

    expect(
      find.text('Every saved climb is already in the room queue.'),
      findsOneWidget,
    );
    expect(find.text('Clear imported seed'), findsOneWidget);
  });

  testWidgets(
      'room seed card keeps angle-sensitive Kilter seeds blocked until the surface context matches',
      (WidgetTester tester) async {
    final FakeAppPreferences appPreferences = FakeAppPreferences(
      activeServer: _server,
      prefs: _buildPrefs(
        settings: _buildSettings(autoGuidesEnabled: false),
        pendingRoomSeed: PendingRoomSeed(
          providerId: 'kilter',
          surface: const ProviderSurface(
            id: 'board-1',
            kind: 'board',
            name: 'Main Board',
            meta: <String, String>{'angle': '40'},
          ),
          climbs: <ProviderClimb>[_providerClimb(id: 'climb-1')],
          createdAt: DateTime.utc(2025, 1, 1).toIso8601String(),
        ),
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
        connected: true,
        surface: const ProviderSurface(
          id: 'board-1',
          kind: 'board',
          name: 'Main Board',
          meta: <String, String>{'angle': '20'},
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

    expect(
      find.text(
        'Choose Main Board as the room surface first, then import the saved queue.',
      ),
      findsOneWidget,
    );
    expect(find.text('Import plan to queue'), findsNothing);
  });

  testWidgets('room screen validates reconnect input before calling the API',
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
        connected: false,
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
    await tester.ensureVisible(find.text('Reconnect provider'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Reconnect provider'));
    await tester.pumpAndSettle();

    expect(apiClient.connectRoomProviderCalled, isFalse);
    expect(
      find.text(
        'Enter the Kilter username before reconnecting the provider on this phone.',
      ),
      findsOneWidget,
    );
  });

  testWidgets('room screen surfaces live signal context from the room snapshot',
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
        connected: true,
        queue: <QueueEntry>[
          QueueEntry(
            id: 1,
            status: 'next',
            position: 1,
            addedBy: 'Host',
            climb: _providerClimb(
              id: 'climb-2',
              name: 'Final Burn',
            ),
          ),
        ],
        voteCounts: const <String, int>{
          'climb-2': 4,
        },
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

    expect(find.text('Live signal'), findsOneWidget);
    expect(find.text('Final Burn'), findsWidgets);
    expect(find.text('Top fist-bumped right now'), findsOneWidget);
    expect(find.text('4 fist bumps'), findsWidgets);
  });

  testWidgets('solo entry gates Kilter behind the offline catalog download',
      (WidgetTester tester) async {
    final FakeApiClient apiClient = FakeApiClient()
      ..capabilities = const <ProviderCapability>[
        ProviderCapability(
          id: 'kilter',
          label: 'Kilter',
          roomSupported: true,
          soloSupported: true,
          surfaceHierarchy: 'board',
          authFields: <ProviderAuthField>[],
        ),
        ProviderCapability(
          id: 'crux',
          label: 'Crux',
          roomSupported: true,
          soloSupported: true,
          surfaceHierarchy: 'hierarchy',
          authFields: <ProviderAuthField>[],
        ),
      ];

    await _pumpScreen(
      tester,
      child: const SoloEntryScreen(),
      appPreferences: FakeAppPreferences(
        activeServer: _server,
        prefs: _buildPrefs(
          settings: _buildSettings(autoGuidesEnabled: false),
        ),
      ),
      apiClient: apiClient,
      offlineCatalogRepository: FakeOfflineKilterCatalogRepository(),
    );

    await tester.pumpAndSettle();

    expect(find.text('Offline Kilter catalog'), findsOneWidget);
    expect(find.text('Download catalog'), findsOneWidget);
    expect(find.text('Other solo providers'), findsOneWidget);
  });

  testWidgets('settings delete only clears the offline catalog',
      (WidgetTester tester) async {
    final FakeOfflineKilterCatalogRepository offlineCatalogRepository =
        FakeOfflineKilterCatalogRepository(
      status: const CatalogStatus(
        installed: true,
        sourceServer: 'https://boards.example.com',
        revision: 'rev-1',
        climbCount: 1234,
        imageCount: 32,
        estimatedBytes: 2048,
        storedBytes: 2048,
        lastFullSyncAt: '2026-03-14T00:00:00Z',
      ),
    );

    await _pumpScreen(
      tester,
      child: const SettingsScreen(),
      appPreferences: FakeAppPreferences(
        activeServer: _server,
        prefs: _buildPrefs(
          settings: _buildSettings(autoGuidesEnabled: false),
        ),
      ),
      apiClient: FakeApiClient(),
      offlineCatalogRepository: offlineCatalogRepository,
    );

    await tester.pumpAndSettle();

    expect(find.text('Offline Kilter catalog'), findsOneWidget);
    expect(find.text('1,234 climbs'), findsNothing);
    expect(find.text('1234 climbs'), findsOneWidget);

    final Finder deleteAction =
        find.widgetWithText(OutlinedButton, 'Delete').first;
    await tester.ensureVisible(deleteAction);
    await tester.pumpAndSettle();
    await tester.tap(deleteAction);
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilledButton, 'Delete'));
    await tester.pumpAndSettle();

    expect(offlineCatalogRepository.deleteCalled, isTrue);
    expect(find.text('Deleted offline Kilter catalog.'), findsOneWidget);
  });

  testWidgets('settings download confirms the estimated catalog size',
      (WidgetTester tester) async {
    final FakeOfflineKilterCatalogRepository offlineCatalogRepository =
        FakeOfflineKilterCatalogRepository();

    await _pumpScreen(
      tester,
      child: const SettingsScreen(),
      appPreferences: FakeAppPreferences(
        activeServer: _server,
        prefs: _buildPrefs(
          settings: _buildSettings(autoGuidesEnabled: false),
        ),
      ),
      apiClient: FakeApiClient(),
      offlineCatalogRepository: offlineCatalogRepository,
    );

    await tester.pumpAndSettle();

    final Finder downloadButton =
        find.widgetWithText(FilledButton, 'Download').first;
    await tester.ensureVisible(downloadButton);
    await tester.pumpAndSettle();
    await tester.tap(downloadButton);
    await tester.pumpAndSettle();

    expect(find.text('Download offline Kilter catalog?'), findsOneWidget);
    expect(find.textContaining('stores about 2.0 KB'), findsOneWidget);

    await tester.tap(find.widgetWithText(FilledButton, 'Download').last);
    await tester.pumpAndSettle();

    expect(offlineCatalogRepository.downloadCalled, isTrue);
    expect(find.text('Downloaded offline Kilter catalog.'), findsOneWidget);
  });

  testWidgets('solo board handles a corrupt offline catalog gracefully',
      (WidgetTester tester) async {
    await _pumpScreen(
      tester,
      child: const SoloBoardScreen(boardId: '1'),
      appPreferences: FakeAppPreferences(
        activeServer: _server,
        prefs: _buildPrefs(
          settings: _buildSettings(autoGuidesEnabled: false),
        ),
      ),
      apiClient: FakeApiClient(),
      offlineCatalogRepository: FakeOfflineKilterCatalogRepository(
        statusError: const CatalogCorruptionException(),
      ),
    );

    await tester.pumpAndSettle();

    expect(
      find.text(CatalogCorruptionException.message),
      findsOneWidget,
    );
  });

  test('offline catalog controller clears corrupt state during auto-sync',
      () async {
    final OfflineKilterCatalogController controller =
        OfflineKilterCatalogController(
      repository: FakeOfflineKilterCatalogRepository(
        statusError: const CatalogCorruptionException(),
      ),
      sessionRepository: SessionRepository(
        appPreferences: FakeAppPreferences(
          activeServer: _server,
          prefs: _buildPrefs(),
        ),
        secureStore: FakeSecureStore(),
      ),
    );

    await controller.autoSyncIfNeeded();

    expect(controller.state.status.installed, isFalse);
    expect(controller.state.errorMessage, CatalogCorruptionException.message);

    controller.dispose();
  });
}

Future<void> _pumpScreen(
  WidgetTester tester, {
  required Widget child,
  FakeAppPreferences? appPreferences,
  FakeSecureStore? secureStore,
  FakeApiClient? apiClient,
  FakeOfflineKilterCatalogRepository? offlineCatalogRepository,
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
        offlineKilterCatalogRepositoryProvider.overrideWithValue(
          offlineCatalogRepository ?? FakeOfflineKilterCatalogRepository(),
        ),
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
  FakeOfflineKilterCatalogRepository? offlineCatalogRepository,
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
        offlineKilterCatalogRepositoryProvider.overrideWithValue(
          offlineCatalogRepository ?? FakeOfflineKilterCatalogRepository(),
        ),
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
  SavedCredentials? savedCredentials,
  PendingRoomSeed? pendingRoomSeed,
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
    savedCredentials: savedCredentials ?? defaults.savedCredentials,
    recentRooms: recentRooms ?? defaults.recentRooms,
    savedSoloFilters: defaults.savedSoloFilters,
    soloFavorites: defaults.soloFavorites,
    soloShortlist: defaults.soloShortlist,
    pendingRoomSeed: pendingRoomSeed ?? defaults.pendingRoomSeed,
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
  bool connected = false,
  ProviderSurface? surface,
  List<QueueEntry>? queue,
  Map<String, int>? voteCounts,
}) {
  return RoomSnapshot(
    slug: 'room-1',
    roomName: 'Moonboard Night',
    status: status,
    providerId: 'kilter',
    version: status == 'closed' ? 2 : 1,
    surface: surface ??
        const ProviderSurface(
          id: 'board-1',
          kind: 'board',
          name: 'Main Board',
        ),
    connection: ProviderConnectionState(
      connected: connected,
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
    queue: queue ?? const <QueueEntry>[],
    voteCounts: voteCounts ?? const <String, int>{},
    myVotes: const <String>[],
    fistBumpsEnabled: true,
    canManage: true,
    permissions: permissions,
    displayName: 'Host',
    assistant: const AssistantState(mode: 'manual'),
  );
}

ProviderClimb _providerClimb({
  required String id,
  String name = 'Warmup Circuit',
  String surfaceId = 'board-1',
}) {
  return ProviderClimb(
    id: id,
    externalId: id,
    providerId: 'kilter',
    surfaceId: surfaceId,
    name: name,
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

class FakeCatalogStoragePlatform extends CatalogStoragePlatform {
  FakeCatalogStoragePlatform({
    Directory? directory,
  }) : _directory = directory ??
            Directory.systemTemp.createTempSync('kt_catalog_test_');

  final Directory _directory;

  @override
  Future<Directory> appSupportDirectory() async => _directory;

  @override
  Future<void> excludeFromBackup(String path) async {}
}

class FakeOfflineKilterCatalogRepository
    extends OfflineKilterCatalogRepository {
  FakeOfflineKilterCatalogRepository({
    CatalogStatus? status,
    CatalogManifest? manifest,
    List<BoardOption>? boards,
    Map<String, String>? imagePaths,
    this.statusError,
    this.boardsError,
    this.queryError,
  })  : _status = status ?? CatalogStatus.empty(),
        _manifest = manifest ??
            const CatalogManifest(
              revision: 'rev-1',
              generatedAt: '2026-03-14T00:00:00Z',
              climbCount: 1234,
              imageCount: 32,
              estimatedBytes: 2048,
              requiresFullResync: false,
            ),
        _boards = boards ?? const <BoardOption>[],
        _imagePaths = imagePaths ?? <String, String>{},
        super(
          apiClient: FakeApiClient(),
          storagePlatform: FakeCatalogStoragePlatform(),
        );

  CatalogStatus _status;
  final CatalogManifest _manifest;
  final List<BoardOption> _boards;
  final Map<String, String> _imagePaths;
  final Object? statusError;
  final Object? boardsError;
  final Object? queryError;
  bool deleteCalled = false;
  bool downloadCalled = false;
  bool syncCalled = false;

  @override
  Future<CatalogStatus> getStatus() async {
    if (statusError != null) {
      throw statusError!;
    }
    return _status;
  }

  @override
  Future<CatalogManifest> getManifest(Uri server) async => _manifest;

  @override
  Future<List<BoardOption>> getBoards() async {
    if (boardsError != null) {
      throw boardsError!;
    }
    return List<BoardOption>.from(_boards);
  }

  @override
  Future<PaginatedBoardClimbsResponse> queryClimbs(
    OfflineCatalogQuery query,
  ) async {
    if (queryError != null) {
      throw queryError!;
    }
    return const PaginatedBoardClimbsResponse(
      climbs: <BoardClimb>[],
      hasMore: false,
      pageSize: 10,
    );
  }

  @override
  Future<void> downloadCatalog(Uri server) async {
    downloadCalled = true;
    _status = _status.copyWith(
      installed: true,
      sourceServer: server.toString(),
      revision: 'rev-1',
      climbCount: _boards.fold<int>(
        0,
        (int total, BoardOption item) => total + (item.climbCount ?? 0),
      ),
      imageCount: _imagePaths.length,
      estimatedBytes: 1024,
      storedBytes: 1024,
      lastFullSyncAt: '2026-03-14T00:00:00Z',
      lastPollAt: '2026-03-14T00:00:00Z',
      updateAvailable: false,
      requiresFullResync: false,
    );
  }

  @override
  Future<CatalogSyncResult> syncCatalog(
    Uri server, {
    bool allowFullResync = true,
  }) async {
    syncCalled = true;
    _status = _status.copyWith(
      installed: true,
      sourceServer: server.toString(),
      lastFullSyncAt: '2026-03-14T01:00:00Z',
      lastPollAt: '2026-03-14T01:00:00Z',
      updateAvailable: false,
      requiresFullResync: false,
    );
    return CatalogSyncResult(status: _status, performedSync: true);
  }

  @override
  Future<void> deleteCatalog() async {
    deleteCalled = true;
    _status = CatalogStatus.empty();
  }

  @override
  Future<String?> resolveImagePath(String filename) async {
    return _imagePaths[filename];
  }
}

class FakeApiClient extends ApiClient {
  FakeApiClient();

  List<ProviderCapability> capabilities = const <ProviderCapability>[];
  List<SessionSummary> recentSessions = const <SessionSummary>[];
  ApiFailure? createFailure;
  ApiFailure? joinFailure;
  ApiFailure? reconnectFailure;
  RoomRecap? recap;
  RoomSnapshot? room;
  bool closeRoomCalled = false;
  bool connectRoomProviderCalled = false;
  Uri? lastJoinServer;
  String? lastJoinSlug;

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
    lastJoinServer = server;
    lastJoinSlug = slug;
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
  Future<List<ProviderSurface>> getRoomCatalogSurfaces({
    required Uri server,
    required String slug,
    required String sessionToken,
    String? parentId,
  }) async {
    return room?.surface == null
        ? const <ProviderSurface>[]
        : <ProviderSurface>[room!.surface!];
  }

  @override
  Future<RoomCatalogClimbsResponse> getRoomCatalogClimbs({
    required Uri server,
    required String slug,
    required String sessionToken,
    String? q,
    String? sort,
    String? cursor,
    int pageSize = 10,
  }) async {
    final List<ProviderClimb> climbs = <ProviderClimb>[
      for (final QueueEntry entry in room?.queue ?? const <QueueEntry>[])
        entry.climb,
      if (room?.currentClimb != null) room!.currentClimb!,
    ];
    return RoomCatalogClimbsResponse(
      climbs: climbs,
      hasMore: false,
      pageSize: climbs.isEmpty ? pageSize : climbs.length,
      voteCounts: room?.voteCounts ?? const <String, int>{},
      myVotes: room?.myVotes ?? const <String>[],
    );
  }

  @override
  Future<RoomCatalogClimbResponse> getRoomCatalogClimb({
    required Uri server,
    required String slug,
    required String sessionToken,
    required String climbId,
  }) async {
    ProviderClimb? queuedClimb;
    for (final QueueEntry entry in room?.queue ?? const <QueueEntry>[]) {
      if (entry.climb.id == climbId) {
        queuedClimb = entry.climb;
        break;
      }
    }
    final ProviderClimb climb =
        queuedClimb ?? room?.currentClimb ?? _providerClimb(id: climbId);
    return RoomCatalogClimbResponse(
      climb: climb,
      voteCount: room?.voteCounts[climbId] ?? 0,
      myVote: room?.myVotes.contains(climbId) ?? false,
      isQueued: (room?.queue ?? const <QueueEntry>[])
          .any((QueueEntry entry) => entry.climb.id == climbId),
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
  Future<ProviderConnectionState> connectRoomProvider({
    required Uri server,
    required String slug,
    required String sessionToken,
    required Map<String, String> secret,
  }) async {
    connectRoomProviderCalled = true;
    if (reconnectFailure != null) {
      throw reconnectFailure!;
    }
    if (room != null) {
      room = RoomSnapshot(
        slug: room!.slug,
        roomName: room!.roomName,
        status: room!.status,
        providerId: room!.providerId,
        version: room!.version + 1,
        surface: room!.surface,
        connection: ProviderConnectionState(
          connected: true,
          providerId: room!.providerId,
        ),
        currentClimb: room!.currentClimb,
        participants: room!.participants,
        finalists: room!.finalists,
        queue: room!.queue,
        voteCounts: room!.voteCounts,
        myVotes: room!.myVotes,
        fistBumpsEnabled: room!.fistBumpsEnabled,
        canManage: room!.canManage,
        permissions: room!.permissions,
        displayName: room!.displayName,
        assistant: room!.assistant,
      );
    }
    return ProviderConnectionState(
      connected: true,
      providerId: room?.providerId ?? 'kilter',
    );
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
