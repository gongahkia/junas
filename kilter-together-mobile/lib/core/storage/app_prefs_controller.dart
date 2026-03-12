import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/app_prefs_models.dart';
import '../models/board_models.dart';
import '../models/room_models.dart';
import 'app_preferences.dart';

final StateNotifierProvider<AppPrefsController, AsyncValue<AppPrefs>> appPrefsControllerProvider =
    StateNotifierProvider<AppPrefsController, AsyncValue<AppPrefs>>((Ref ref) {
  return AppPrefsController(
    repository: ref.read(appPreferencesProvider),
  );
});

class AppPrefsController extends StateNotifier<AsyncValue<AppPrefs>> {
  AppPrefsController({
    required AppPreferences repository,
  })  : _repository = repository,
        super(const AsyncValue<AppPrefs>.loading()) {
    unawaited(_load());
  }

  final AppPreferences _repository;

  Future<void> _load() async {
    try {
      final AppPrefs prefs = await _repository.loadAppPrefs();
      state = AsyncValue<AppPrefs>.data(_normalizeAppPrefs(prefs));
    } catch (error, stackTrace) {
      state = AsyncValue<AppPrefs>.error(error, stackTrace);
    }
  }

  Future<AppPrefs> _current() async {
    final AsyncValue<AppPrefs> currentState = state;
    if (currentState.hasValue) {
      return currentState.requireValue;
    }
    final AppPrefs prefs = await _repository.loadAppPrefs();
    final AppPrefs normalized = _normalizeAppPrefs(prefs);
    state = AsyncValue<AppPrefs>.data(normalized);
    return normalized;
  }

  Future<void> _mutate(AppPrefs Function(AppPrefs current) updater) async {
    final AppPrefs current = await _current();
    final AppPrefs next = _normalizeAppPrefs(updater(current));
    await _repository.saveAppPrefs(next);
    state = AsyncValue<AppPrefs>.data(next);
  }

  Future<void> refresh() => _load();

  Future<void> rememberDisplayName(String displayName) {
    return _mutate((AppPrefs current) {
      return AppPrefs(
        savedDisplayName: displayName.trim(),
        lastProviderId: current.lastProviderId,
        lastKilterBoardId: current.lastKilterBoardId,
        lastKilterAngle: current.lastKilterAngle,
        lastCruxGymSlug: current.lastCruxGymSlug,
        lastCruxWallId: current.lastCruxWallId,
        hostDefaults: current.hostDefaults,
        savedCredentials: current.savedCredentials,
        recentRooms: current.recentRooms,
        savedSoloFilters: current.savedSoloFilters,
        soloFavorites: current.soloFavorites,
        soloShortlist: current.soloShortlist,
        pendingRoomSeed: current.pendingRoomSeed,
        soloResume: current.soloResume,
        intro: current.intro,
        onboarding: current.onboarding,
        guidedTour: current.guidedTour,
        feedbackPrompts: current.feedbackPrompts,
        settings: current.settings,
      );
    });
  }

  Future<void> rememberLastProvider(String providerId) {
    return _mutate((AppPrefs current) => _copy(
          current,
          lastProviderId: providerId,
        ));
  }

  Future<void> updateHostDefaults({
    String? roomNameTemplate,
    bool? defaultFistBumpsEnabled,
  }) {
    return _mutate((AppPrefs current) {
      return _copy(
        current,
        hostDefaults: HostDefaults(
          roomNameTemplate: roomNameTemplate ?? current.hostDefaults.roomNameTemplate,
          defaultFistBumpsEnabled:
              defaultFistBumpsEnabled ?? current.hostDefaults.defaultFistBumpsEnabled,
        ),
      );
    });
  }

  Future<void> rememberKilterCredentials({
    required String username,
    required bool remember,
  }) {
    return _mutate((AppPrefs current) {
      final Map<String, SavedCredentialPreference> providers =
          Map<String, SavedCredentialPreference>.from(current.savedCredentials.providers);
      providers['kilter'] = SavedCredentialPreference(
        remember: remember,
        username: remember ? username.trim() : null,
      );
      return _copy(
        current,
        savedCredentials: SavedCredentials(providers: providers),
      );
    });
  }

  Future<void> rememberProviderSecretPreference({
    required String providerId,
    required bool remember,
  }) {
    return _mutate((AppPrefs current) {
      final Map<String, SavedCredentialPreference> providers =
          Map<String, SavedCredentialPreference>.from(current.savedCredentials.providers);
      final SavedCredentialPreference previous =
          providers[providerId] ?? const SavedCredentialPreference(remember: false);
      providers[providerId] = SavedCredentialPreference(
        remember: remember,
        username: previous.username,
      );
      return _copy(
        current,
        savedCredentials: SavedCredentials(providers: providers),
      );
    });
  }

  Future<void> clearSavedCredentialPreferences() {
    return _mutate((AppPrefs current) {
      return _copy(
        current,
        savedCredentials: const SavedCredentials(
          providers: <String, SavedCredentialPreference>{
            'kilter': SavedCredentialPreference(remember: false),
            'crux': SavedCredentialPreference(remember: false),
          },
        ),
      );
    });
  }

  Future<void> rememberLastKilterSurface({
    required String boardId,
    required int angle,
  }) {
    return _mutate((AppPrefs current) {
      return _copy(
        current,
        lastKilterBoardId: boardId,
        lastKilterAngle: angle,
      );
    });
  }

  Future<void> rememberLastCruxSurface({
    required String gymSlug,
    required String wallId,
  }) {
    return _mutate((AppPrefs current) {
      return _copy(
        current,
        lastCruxGymSlug: gymSlug,
        lastCruxWallId: wallId,
      );
    });
  }

  Future<void> updateSettings({
    bool? clickCheersEnabled,
    bool? playfulMotionEnabled,
    bool? autoGuidesEnabled,
    bool? recentRoomsEnabled,
    String? soloDefaultSort,
  }) {
    return _mutate((AppPrefs current) {
      final AppSettings settings = AppSettings(
        clickCheersEnabled: clickCheersEnabled ?? current.settings.clickCheersEnabled,
        playfulMotionEnabled: playfulMotionEnabled ?? current.settings.playfulMotionEnabled,
        autoGuidesEnabled: autoGuidesEnabled ?? current.settings.autoGuidesEnabled,
        recentRoomsEnabled: recentRoomsEnabled ?? current.settings.recentRoomsEnabled,
        soloDefaultSort: soloDefaultSort ?? current.settings.soloDefaultSort,
      );
      return _copy(
        current,
        settings: settings,
        recentRooms: settings.recentRoomsEnabled ? current.recentRooms : const <RecentRoom>[],
      );
    });
  }

  Future<void> rememberRoomVisit({
    required Uri server,
    required RoomSnapshot room,
  }) {
    return _mutate((AppPrefs current) {
      if (!current.settings.recentRoomsEnabled) {
        return current;
      }
      final RecentRoom nextRoom = RecentRoom(
        server: server.toString(),
        slug: room.slug,
        providerId: room.providerId,
        lastVisitedAt: DateTime.now().toUtc().toIso8601String(),
        roomName: room.roomName,
        displayName: room.displayName,
        surfaceName: room.surface?.name,
        pinned: current.recentRooms.any(
          (RecentRoom candidate) => candidate.server == server.toString() && candidate.slug == room.slug && candidate.pinned,
        ),
      );
      final List<RecentRoom> remaining = current.recentRooms.where((RecentRoom candidate) {
        return !(candidate.server == nextRoom.server && candidate.slug == nextRoom.slug);
      }).toList(growable: true);
      return _copy(
        current,
        recentRooms: <RecentRoom>[nextRoom, ...remaining],
      );
    });
  }

  Future<void> togglePinnedRecentRoom({
    required Uri server,
    required String slug,
  }) {
    return _mutate((AppPrefs current) {
      final List<RecentRoom> next = current.recentRooms
          .map((RecentRoom item) => item.server == server.toString() && item.slug == slug
              ? RecentRoom(
                  server: item.server,
                  slug: item.slug,
                  providerId: item.providerId,
                  lastVisitedAt: item.lastVisitedAt,
                  roomName: item.roomName,
                  displayName: item.displayName,
                  surfaceName: item.surfaceName,
                  pinned: !item.pinned,
                )
              : item)
          .toList(growable: false);
      return _copy(current, recentRooms: next);
    });
  }

  Future<void> removeRecentRoom({
    required Uri server,
    required String slug,
  }) {
    return _mutate((AppPrefs current) {
      return _copy(
        current,
        recentRooms: current.recentRooms
            .where((RecentRoom item) => !(item.server == server.toString() && item.slug == slug))
            .toList(growable: false),
      );
    });
  }

  Future<void> clearRecentRooms() {
    return _mutate((AppPrefs current) => _copy(current, recentRooms: const <RecentRoom>[]));
  }

  Future<void> rememberSoloResume(SoloResumeState soloResume) {
    return _mutate((AppPrefs current) {
      return _copy(
        current,
        soloResume: soloResume,
        lastKilterBoardId: soloResume.boardId,
        lastKilterAngle: soloResume.angle,
      );
    });
  }

  Future<void> clearSoloResume() {
    return _mutate((AppPrefs current) => _copy(current, clearSoloResume: true));
  }

  Future<void> toggleSoloFavorite(SoloSavedClimb climb) {
    return _mutate((AppPrefs current) {
      final bool exists = current.soloFavorites.any((SoloSavedClimb item) => item.key == climb.key);
      final List<SoloSavedClimb> next = exists
          ? current.soloFavorites.where((SoloSavedClimb item) => item.key != climb.key).toList(growable: false)
          : <SoloSavedClimb>[climb, ...current.soloFavorites];
      return _copy(current, soloFavorites: next);
    });
  }

  Future<void> toggleSoloShortlist(SoloSavedClimb climb) {
    return _mutate((AppPrefs current) {
      final bool exists = current.soloShortlist.any((SoloSavedClimb item) => item.key == climb.key);
      final List<SoloSavedClimb> next = exists
          ? current.soloShortlist.where((SoloSavedClimb item) => item.key != climb.key).toList(growable: false)
          : <SoloSavedClimb>[climb, ...current.soloShortlist];
      return _copy(current, soloShortlist: next);
    });
  }

  Future<void> removeSoloFavorite(String climbKey) {
    return _mutate((AppPrefs current) {
      return _copy(
        current,
        soloFavorites: current.soloFavorites
            .where((SoloSavedClimb item) => item.key != climbKey)
            .toList(growable: false),
      );
    });
  }

  Future<void> removeSoloShortlist(String climbKey) {
    return _mutate((AppPrefs current) {
      return _copy(
        current,
        soloShortlist: current.soloShortlist
            .where((SoloSavedClimb item) => item.key != climbKey)
            .toList(growable: false),
      );
    });
  }

  Future<void> saveSoloFilterPreset(SoloFilterPreset preset) {
    return _mutate((AppPrefs current) {
      final List<SoloFilterPreset> remaining = current.savedSoloFilters
          .where((SoloFilterPreset item) => item.id != preset.id)
          .toList(growable: true);
      return _copy(
        current,
        savedSoloFilters: <SoloFilterPreset>[preset, ...remaining],
      );
    });
  }

  Future<void> removeSoloFilterPreset(String presetId) {
    return _mutate((AppPrefs current) {
      return _copy(
        current,
        savedSoloFilters: current.savedSoloFilters
            .where((SoloFilterPreset item) => item.id != presetId)
            .toList(growable: false),
      );
    });
  }

  Future<void> setPendingRoomSeed(PendingRoomSeed? pendingRoomSeed) {
    return _mutate((AppPrefs current) {
      return _copy(
        current,
        pendingRoomSeed: pendingRoomSeed,
      );
    });
  }

  Future<void> clearPendingRoomSeed() {
    return _mutate((AppPrefs current) => _copy(current, clearPendingRoomSeed: true));
  }

  Future<void> dismissLandingIntro() {
    return _mutate((AppPrefs current) {
      return _copy(
        current,
        intro: IntroProgress(
          version: current.intro.version,
          landingDismissed: true,
          soloDismissed: current.intro.soloDismissed,
        ),
      );
    });
  }

  Future<void> dismissSoloIntro() {
    return _mutate((AppPrefs current) {
      return _copy(
        current,
        intro: IntroProgress(
          version: current.intro.version,
          landingDismissed: current.intro.landingDismissed,
          soloDismissed: true,
        ),
      );
    });
  }

  Future<void> resetGuides() {
    return _mutate((AppPrefs current) {
      return _copy(
        current,
        intro: IntroProgress(
          version: current.intro.version,
          landingDismissed: false,
          soloDismissed: false,
        ),
        onboarding: OnboardingProgress(
          version: current.onboarding.version,
          dismissed: false,
          hostCompleted: false,
          guestCompleted: false,
          hostConnectedProvider: false,
          hostSelectedSurface: false,
          guestJoinedRoom: false,
          guestParticipated: false,
        ),
        guidedTour: GuidedTourProgress(
          version: current.guidedTour.version,
          landingCompleted: false,
          hostCompleted: false,
          guestCompleted: false,
          soloCompleted: false,
        ),
      );
    });
  }

  Future<void> queueGuideBranch(String branch) {
    return _mutate((AppPrefs current) {
      return _copy(
        current,
        guidedTour: GuidedTourProgress(
          version: current.guidedTour.version,
          landingCompleted: current.guidedTour.landingCompleted,
          hostCompleted: current.guidedTour.hostCompleted,
          guestCompleted: current.guidedTour.guestCompleted,
          soloCompleted: current.guidedTour.soloCompleted,
          activeBranch: branch,
        ),
      );
    });
  }

  Future<void> clearGuideBranch() {
    return _mutate((AppPrefs current) {
      return _copy(
        current,
        guidedTour: GuidedTourProgress(
          version: current.guidedTour.version,
          landingCompleted: current.guidedTour.landingCompleted,
          hostCompleted: current.guidedTour.hostCompleted,
          guestCompleted: current.guidedTour.guestCompleted,
          soloCompleted: current.guidedTour.soloCompleted,
        ),
      );
    });
  }

  Future<void> completeLandingGuide() {
    return _mutate((AppPrefs current) {
      return _copy(
        current,
        guidedTour: GuidedTourProgress(
          version: current.guidedTour.version,
          landingCompleted: true,
          hostCompleted: current.guidedTour.hostCompleted,
          guestCompleted: current.guidedTour.guestCompleted,
          soloCompleted: current.guidedTour.soloCompleted,
          activeBranch: current.guidedTour.activeBranch,
        ),
      );
    });
  }

  Future<void> completeGuideBranch(String branch) {
    return _mutate((AppPrefs current) {
      return _copy(
        current,
        guidedTour: GuidedTourProgress(
          version: current.guidedTour.version,
          landingCompleted: current.guidedTour.landingCompleted,
          hostCompleted: branch == 'host' ? true : current.guidedTour.hostCompleted,
          guestCompleted: branch == 'guest' ? true : current.guidedTour.guestCompleted,
          soloCompleted: branch == 'solo' ? true : current.guidedTour.soloCompleted,
        ),
      );
    });
  }

  Future<void> markHostProviderConnected() {
    return _mutate((AppPrefs current) {
      final OnboardingProgress onboarding = OnboardingProgress(
        version: current.onboarding.version,
        dismissed: current.onboarding.dismissed,
        hostCompleted:
            current.onboarding.hostSelectedSurface && true,
        guestCompleted: current.onboarding.guestCompleted,
        hostConnectedProvider: true,
        hostSelectedSurface: current.onboarding.hostSelectedSurface,
        guestJoinedRoom: current.onboarding.guestJoinedRoom,
        guestParticipated: current.onboarding.guestParticipated,
      );
      return _copy(current, onboarding: onboarding);
    });
  }

  Future<void> markHostSurfaceSelected() {
    return _mutate((AppPrefs current) {
      final OnboardingProgress onboarding = OnboardingProgress(
        version: current.onboarding.version,
        dismissed: current.onboarding.dismissed,
        hostCompleted:
            current.onboarding.hostConnectedProvider && true,
        guestCompleted: current.onboarding.guestCompleted,
        hostConnectedProvider: current.onboarding.hostConnectedProvider,
        hostSelectedSurface: true,
        guestJoinedRoom: current.onboarding.guestJoinedRoom,
        guestParticipated: current.onboarding.guestParticipated,
      );
      return _copy(current, onboarding: onboarding);
    });
  }

  Future<void> markGuestJoinedRoom() {
    return _mutate((AppPrefs current) {
      final OnboardingProgress onboarding = OnboardingProgress(
        version: current.onboarding.version,
        dismissed: current.onboarding.dismissed,
        hostCompleted: current.onboarding.hostCompleted,
        guestCompleted: current.onboarding.guestParticipated && true,
        hostConnectedProvider: current.onboarding.hostConnectedProvider,
        hostSelectedSurface: current.onboarding.hostSelectedSurface,
        guestJoinedRoom: true,
        guestParticipated: current.onboarding.guestParticipated,
      );
      return _copy(current, onboarding: onboarding);
    });
  }

  Future<void> markGuestParticipated() {
    return _mutate((AppPrefs current) {
      final OnboardingProgress onboarding = OnboardingProgress(
        version: current.onboarding.version,
        dismissed: current.onboarding.dismissed,
        hostCompleted: current.onboarding.hostCompleted,
        guestCompleted: current.onboarding.guestJoinedRoom && true,
        hostConnectedProvider: current.onboarding.hostConnectedProvider,
        hostSelectedSurface: current.onboarding.hostSelectedSurface,
        guestJoinedRoom: current.onboarding.guestJoinedRoom,
        guestParticipated: true,
      );
      return _copy(current, onboarding: onboarding);
    });
  }

  Future<bool> shouldShowFeedbackPrompt(String promptFamily) async {
    final AppPrefs current = await _current();
    final String? lastShown = current.feedbackPrompts[promptFamily];
    if (lastShown == null || lastShown.isEmpty) {
      return true;
    }
    final DateTime? lastDate = DateTime.tryParse(lastShown);
    if (lastDate == null) {
      return true;
    }
    return DateTime.now().toUtc().difference(lastDate) >= const Duration(days: 7);
  }

  Future<void> markFeedbackPromptSeen(String promptFamily) {
    return _mutate((AppPrefs current) {
      final Map<String, String> nextPrompts = Map<String, String>.from(current.feedbackPrompts);
      nextPrompts[promptFamily] = DateTime.now().toUtc().toIso8601String();
      return _copy(current, feedbackPrompts: nextPrompts);
    });
  }

  String resolveHostRoomNameTemplate(String template, {DateTime? now}) {
    final DateTime value = (now ?? DateTime.now()).toLocal();
    final String normalizedTemplate = template.trim();
    if (normalizedTemplate.isEmpty) {
      return '';
    }
    return normalizedTemplate
        .replaceAll('{weekday}', _weekdayName(value.weekday))
        .replaceAll('{date}', '${_monthName(value.month)} ${value.day}')
        .replaceAll('{iso_date}', value.toIso8601String().split('T').first)
        .trim();
  }

  AppPrefs _copy(
    AppPrefs current, {
    String? savedDisplayName,
    String? lastProviderId,
    String? lastKilterBoardId,
    int? lastKilterAngle,
    String? lastCruxGymSlug,
    String? lastCruxWallId,
    HostDefaults? hostDefaults,
    SavedCredentials? savedCredentials,
    List<RecentRoom>? recentRooms,
    List<SoloFilterPreset>? savedSoloFilters,
    List<SoloSavedClimb>? soloFavorites,
    List<SoloSavedClimb>? soloShortlist,
    PendingRoomSeed? pendingRoomSeed,
    bool clearPendingRoomSeed = false,
    SoloResumeState? soloResume,
    bool clearSoloResume = false,
    IntroProgress? intro,
    OnboardingProgress? onboarding,
    GuidedTourProgress? guidedTour,
    Map<String, String>? feedbackPrompts,
    AppSettings? settings,
  }) {
    return AppPrefs(
      savedDisplayName: savedDisplayName ?? current.savedDisplayName,
      lastProviderId: lastProviderId ?? current.lastProviderId,
      lastKilterBoardId: lastKilterBoardId ?? current.lastKilterBoardId,
      lastKilterAngle: lastKilterAngle ?? current.lastKilterAngle,
      lastCruxGymSlug: lastCruxGymSlug ?? current.lastCruxGymSlug,
      lastCruxWallId: lastCruxWallId ?? current.lastCruxWallId,
      hostDefaults: hostDefaults ?? current.hostDefaults,
      savedCredentials: savedCredentials ?? current.savedCredentials,
      recentRooms: recentRooms ?? current.recentRooms,
      savedSoloFilters: savedSoloFilters ?? current.savedSoloFilters,
      soloFavorites: soloFavorites ?? current.soloFavorites,
      soloShortlist: soloShortlist ?? current.soloShortlist,
      pendingRoomSeed: clearPendingRoomSeed ? null : (pendingRoomSeed ?? current.pendingRoomSeed),
      soloResume: clearSoloResume ? null : (soloResume ?? current.soloResume),
      intro: intro ?? current.intro,
      onboarding: onboarding ?? current.onboarding,
      guidedTour: guidedTour ?? current.guidedTour,
      feedbackPrompts: feedbackPrompts ?? current.feedbackPrompts,
      settings: settings ?? current.settings,
    );
  }

  AppPrefs _normalizeAppPrefs(AppPrefs current) {
    return AppPrefs(
      savedDisplayName: current.savedDisplayName,
      lastProviderId: current.lastProviderId,
      lastKilterBoardId: current.lastKilterBoardId,
      lastKilterAngle: current.lastKilterAngle,
      lastCruxGymSlug: current.lastCruxGymSlug,
      lastCruxWallId: current.lastCruxWallId,
      hostDefaults: current.hostDefaults,
      savedCredentials: current.savedCredentials,
      recentRooms: _normalizeRecentRooms(current.recentRooms),
      savedSoloFilters: _normalizeSoloFilterPresets(current.savedSoloFilters),
      soloFavorites: _normalizeSoloSavedClimbs(current.soloFavorites),
      soloShortlist: _normalizeSoloSavedClimbs(current.soloShortlist),
      pendingRoomSeed: current.pendingRoomSeed,
      soloResume: current.soloResume,
      intro: current.intro,
      onboarding: current.onboarding,
      guidedTour: current.guidedTour,
      feedbackPrompts: current.feedbackPrompts,
      settings: current.settings,
    );
  }

  List<RecentRoom> _normalizeRecentRooms(List<RecentRoom> value) {
    final Map<String, RecentRoom> deduped = <String, RecentRoom>{};
    for (final RecentRoom room in value) {
      if (room.server.trim().isEmpty || room.slug.trim().isEmpty) {
        continue;
      }
      deduped['${room.server}::${room.slug}'] = room;
    }
    final List<RecentRoom> sorted = deduped.values.toList(growable: false)
      ..sort((RecentRoom left, RecentRoom right) {
        if (left.pinned != right.pinned) {
          return left.pinned ? -1 : 1;
        }
        final int rightTime = DateTime.tryParse(right.lastVisitedAt)?.millisecondsSinceEpoch ?? 0;
        final int leftTime = DateTime.tryParse(left.lastVisitedAt)?.millisecondsSinceEpoch ?? 0;
        return rightTime.compareTo(leftTime);
      });
    return sorted.take(9).toList(growable: false);
  }

  List<SoloSavedClimb> _normalizeSoloSavedClimbs(List<SoloSavedClimb> value) {
    final Map<String, SoloSavedClimb> deduped = <String, SoloSavedClimb>{};
    for (final SoloSavedClimb climb in value) {
      if (climb.uuid.isEmpty || climb.boardId.isEmpty || climb.productSizeId == 0) {
        continue;
      }
      deduped[climb.key] = climb;
    }
    final List<SoloSavedClimb> sorted = deduped.values.toList(growable: false)
      ..sort((SoloSavedClimb left, SoloSavedClimb right) {
        final int rightTime = DateTime.tryParse(right.savedAt)?.millisecondsSinceEpoch ?? 0;
        final int leftTime = DateTime.tryParse(left.savedAt)?.millisecondsSinceEpoch ?? 0;
        return rightTime.compareTo(leftTime);
      });
    return sorted.take(24).toList(growable: false);
  }

  List<SoloFilterPreset> _normalizeSoloFilterPresets(List<SoloFilterPreset> value) {
    final Map<String, SoloFilterPreset> deduped = <String, SoloFilterPreset>{};
    for (final SoloFilterPreset preset in value) {
      if (preset.id.trim().isEmpty || preset.boardId.trim().isEmpty) {
        continue;
      }
      deduped[preset.id] = preset;
    }
    final List<SoloFilterPreset> sorted = deduped.values.toList(growable: false)
      ..sort((SoloFilterPreset left, SoloFilterPreset right) {
        final int rightTime = DateTime.tryParse(right.savedAt)?.millisecondsSinceEpoch ?? 0;
        final int leftTime = DateTime.tryParse(left.savedAt)?.millisecondsSinceEpoch ?? 0;
        return rightTime.compareTo(leftTime);
      });
    return sorted.take(12).toList(growable: false);
  }

  String _weekdayName(int weekday) {
    const List<String> values = <String>[
      'Monday',
      'Tuesday',
      'Wednesday',
      'Thursday',
      'Friday',
      'Saturday',
      'Sunday',
    ];
    final int index = ((weekday - 1).clamp(0, values.length - 1) as num).toInt();
    return values[index];
  }

  String _monthName(int month) {
    const List<String> values = <String>[
      'Jan',
      'Feb',
      'Mar',
      'Apr',
      'May',
      'Jun',
      'Jul',
      'Aug',
      'Sep',
      'Oct',
      'Nov',
      'Dec',
    ];
    final int index = ((month - 1).clamp(0, values.length - 1) as num).toInt();
    return values[index];
  }
}
