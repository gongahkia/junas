import 'board_models.dart';
import 'provider_models.dart';

class RecentRoom {
  const RecentRoom({
    required this.server,
    required this.slug,
    required this.providerId,
    required this.lastVisitedAt,
    this.roomName,
    this.displayName,
    this.surfaceName,
    this.pinned = false,
    this.angle,
    this.climbCount,
    this.rematchConfig,
  });

  final String server;
  final String slug;
  final String providerId;
  final String lastVisitedAt;
  final String? roomName;
  final String? displayName;
  final String? surfaceName;
  final bool pinned;
  final int? angle;
  final int? climbCount;
  final Map<String, dynamic>? rematchConfig;

  factory RecentRoom.fromJson(Map<String, dynamic> json) {
    return RecentRoom(
      server: json['server'] as String? ?? '',
      slug: json['slug'] as String? ?? '',
      providerId: json['provider_id'] as String? ?? '',
      lastVisitedAt: json['last_visited_at'] as String? ?? '',
      roomName: json['room_name'] as String?,
      displayName: json['display_name'] as String?,
      surfaceName: json['surface_name'] as String?,
      pinned: json['pinned'] as bool? ?? false,
      angle: (json['angle'] as num?)?.toInt(),
      climbCount: (json['climb_count'] as num?)?.toInt(),
      rematchConfig: json['rematch_config'] as Map<String, dynamic>?,
    );
  }

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'server': server,
      'slug': slug,
      'provider_id': providerId,
      'last_visited_at': lastVisitedAt,
      'room_name': roomName,
      'display_name': displayName,
      'surface_name': surfaceName,
      'pinned': pinned,
      'angle': angle,
      'climb_count': climbCount,
      'rematch_config': rematchConfig,
    };
  }
}

class SoloResumeState {
  const SoloResumeState({
    required this.boardId,
    required this.angle,
    required this.sort,
    this.q,
    this.setter,
    this.grade,
    this.climb,
  });

  final String boardId;
  final int angle;
  final String sort;
  final String? q;
  final String? setter;
  final String? grade;
  final String? climb;

  factory SoloResumeState.fromJson(Map<String, dynamic> json) {
    return SoloResumeState(
      boardId: json['board_id'] as String? ?? '',
      angle: (json['angle'] as num?)?.toInt() ?? defaultBoardAngle,
      sort: json['sort'] as String? ?? defaultClimbSort,
      q: json['q'] as String?,
      setter: json['setter'] as String?,
      grade: json['grade'] as String?,
      climb: json['climb'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'board_id': boardId,
      'angle': angle,
      'sort': sort,
      'q': q,
      'setter': setter,
      'grade': grade,
      'climb': climb,
    };
  }
}

class IntroProgress {
  const IntroProgress({
    required this.version,
    required this.landingDismissed,
    required this.soloDismissed,
  });

  final int version;
  final bool landingDismissed;
  final bool soloDismissed;

  factory IntroProgress.fromJson(Map<String, dynamic> json) {
    return IntroProgress(
      version: (json['version'] as num?)?.toInt() ?? 1,
      landingDismissed: json['landing_dismissed'] as bool? ?? false,
      soloDismissed: json['solo_dismissed'] as bool? ?? false,
    );
  }

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'version': version,
      'landing_dismissed': landingDismissed,
      'solo_dismissed': soloDismissed,
    };
  }
}

class OnboardingProgress {
  const OnboardingProgress({
    required this.version,
    required this.dismissed,
    required this.hostCompleted,
    required this.guestCompleted,
    required this.hostConnectedProvider,
    required this.hostSelectedSurface,
    required this.guestJoinedRoom,
    required this.guestParticipated,
  });

  final int version;
  final bool dismissed;
  final bool hostCompleted;
  final bool guestCompleted;
  final bool hostConnectedProvider;
  final bool hostSelectedSurface;
  final bool guestJoinedRoom;
  final bool guestParticipated;

  factory OnboardingProgress.fromJson(Map<String, dynamic> json) {
    return OnboardingProgress(
      version: (json['version'] as num?)?.toInt() ?? 1,
      dismissed: json['dismissed'] as bool? ?? false,
      hostCompleted: json['host_completed'] as bool? ?? false,
      guestCompleted: json['guest_completed'] as bool? ?? false,
      hostConnectedProvider: json['host_connected_provider'] as bool? ?? false,
      hostSelectedSurface: json['host_selected_surface'] as bool? ?? false,
      guestJoinedRoom: json['guest_joined_room'] as bool? ?? false,
      guestParticipated: json['guest_participated'] as bool? ?? false,
    );
  }

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'version': version,
      'dismissed': dismissed,
      'host_completed': hostCompleted,
      'guest_completed': guestCompleted,
      'host_connected_provider': hostConnectedProvider,
      'host_selected_surface': hostSelectedSurface,
      'guest_joined_room': guestJoinedRoom,
      'guest_participated': guestParticipated,
    };
  }
}

class GuidedTourProgress {
  const GuidedTourProgress({
    required this.version,
    required this.landingCompleted,
    required this.hostCompleted,
    required this.guestCompleted,
    required this.soloCompleted,
    this.activeBranch,
  });

  final int version;
  final bool landingCompleted;
  final bool hostCompleted;
  final bool guestCompleted;
  final bool soloCompleted;
  final String? activeBranch;

  factory GuidedTourProgress.fromJson(Map<String, dynamic> json) {
    return GuidedTourProgress(
      version: (json['version'] as num?)?.toInt() ?? 2,
      landingCompleted: json['landing_completed'] as bool? ?? false,
      hostCompleted: json['host_completed'] as bool? ?? false,
      guestCompleted: json['guest_completed'] as bool? ?? false,
      soloCompleted: json['solo_completed'] as bool? ?? false,
      activeBranch: json['active_branch'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'version': version,
      'landing_completed': landingCompleted,
      'host_completed': hostCompleted,
      'guest_completed': guestCompleted,
      'solo_completed': soloCompleted,
      'active_branch': activeBranch,
    };
  }
}

class SavedCredentialPreference {
  const SavedCredentialPreference({
    required this.remember,
    this.username,
  });

  final bool remember;
  final String? username;

  factory SavedCredentialPreference.fromJson(Map<String, dynamic> json) {
    return SavedCredentialPreference(
      remember: json['remember'] as bool? ?? false,
      username: json['username'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'remember': remember,
      'username': username,
    };
  }
}

class SavedCredentials {
  const SavedCredentials({
    required this.providers,
  });

  final Map<String, SavedCredentialPreference> providers;

  factory SavedCredentials.fromJson(Map<String, dynamic> json) {
    final Map<String, dynamic> rawProviders =
        (json['providers'] as Map<String, dynamic>?) ?? <String, dynamic>{};
    return SavedCredentials(
      providers: rawProviders.map(
        (String key, dynamic value) => MapEntry(
          key,
          SavedCredentialPreference.fromJson(
              (value as Map<dynamic, dynamic>).cast<String, dynamic>()),
        ),
      ),
    );
  }

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'providers': providers.map(
        (String key, SavedCredentialPreference value) =>
            MapEntry(key, value.toJson()),
      ),
    };
  }
}

class HostDefaults {
  const HostDefaults({
    required this.roomNameTemplate,
    required this.defaultFistBumpsEnabled,
  });

  final String roomNameTemplate;
  final bool defaultFistBumpsEnabled;

  factory HostDefaults.fromJson(Map<String, dynamic> json) {
    return HostDefaults(
      roomNameTemplate: json['room_name_template'] as String? ?? '',
      defaultFistBumpsEnabled:
          json['default_fist_bumps_enabled'] as bool? ?? true,
    );
  }

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'room_name_template': roomNameTemplate,
      'default_fist_bumps_enabled': defaultFistBumpsEnabled,
    };
  }
}

class AppSettings {
  const AppSettings({
    required this.clickCheersEnabled,
    required this.playfulMotionEnabled,
    required this.autoGuidesEnabled,
    required this.recentRoomsEnabled,
    required this.soloDefaultSort,
    this.notifyOnClimbChange = false,
  });

  final bool clickCheersEnabled;
  final bool playfulMotionEnabled;
  final bool autoGuidesEnabled;
  final bool recentRoomsEnabled;
  final String soloDefaultSort;
  final bool notifyOnClimbChange;

  factory AppSettings.fromJson(Map<String, dynamic> json) {
    return AppSettings(
      clickCheersEnabled: json['click_cheers_enabled'] as bool? ?? true,
      playfulMotionEnabled: json['playful_motion_enabled'] as bool? ?? true,
      autoGuidesEnabled: json['auto_guides_enabled'] as bool? ?? true,
      recentRoomsEnabled: json['recent_rooms_enabled'] as bool? ?? true,
      soloDefaultSort: json['solo_default_sort'] as String? ?? defaultClimbSort,
      notifyOnClimbChange: json['notify_on_climb_change'] as bool? ?? false,
    );
  }

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'click_cheers_enabled': clickCheersEnabled,
      'playful_motion_enabled': playfulMotionEnabled,
      'auto_guides_enabled': autoGuidesEnabled,
      'recent_rooms_enabled': recentRoomsEnabled,
      'solo_default_sort': soloDefaultSort,
      'notify_on_climb_change': notifyOnClimbChange,
    };
  }
}

class PendingRoomSeed {
  const PendingRoomSeed({
    required this.providerId,
    required this.surface,
    required this.climbs,
    required this.createdAt,
    this.title,
    this.openPath,
  });

  final String providerId;
  final String? title;
  final ProviderSurface surface;
  final List<ProviderClimb> climbs;
  final String? openPath;
  final String createdAt;

  factory PendingRoomSeed.fromJson(Map<String, dynamic> json) {
    final List<dynamic> rawClimbs =
        (json['climbs'] as List<dynamic>?) ?? <dynamic>[];
    return PendingRoomSeed(
      providerId: json['provider_id'] as String? ?? '',
      title: json['title'] as String?,
      surface: ProviderSurface.fromJson(
          (json['surface'] as Map<String, dynamic>?) ?? <String, dynamic>{}),
      climbs: rawClimbs
          .whereType<Map<String, dynamic>>()
          .map(ProviderClimb.fromJson)
          .toList(growable: false),
      openPath: json['open_path'] as String?,
      createdAt: json['created_at'] as String? ?? '',
    );
  }

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'provider_id': providerId,
      'title': title,
      'surface': surface.toJson(),
      'climbs': climbs
          .map((ProviderClimb item) => item.toJson())
          .toList(growable: false),
      'open_path': openPath,
      'created_at': createdAt,
    };
  }
}

class RoomTemplate {
  const RoomTemplate({
    required this.id,
    required this.name,
    required this.server,
    required this.providerId,
    this.surfaceId,
    this.surfaceContext = const <String, String>{},
    this.roomNameTemplate = '',
    this.fistBumpsEnabled = true,
    required this.createdAt,
  });

  final String id;
  final String name;
  final String server;
  final String providerId;
  final String? surfaceId;
  final Map<String, String> surfaceContext;
  final String roomNameTemplate;
  final bool fistBumpsEnabled;
  final String createdAt;

  factory RoomTemplate.fromJson(Map<String, dynamic> json) {
    final Map<String, dynamic> rawCtx =
        (json['surface_context'] as Map<String, dynamic>?) ??
            <String, dynamic>{};
    return RoomTemplate(
      id: json['id'] as String? ?? '',
      name: json['name'] as String? ?? '',
      server: json['server'] as String? ?? '',
      providerId: json['provider_id'] as String? ?? '',
      surfaceId: json['surface_id'] as String?,
      surfaceContext:
          rawCtx.map((String key, dynamic value) => MapEntry(key, '$value')),
      roomNameTemplate: json['room_name_template'] as String? ?? '',
      fistBumpsEnabled: json['fist_bumps_enabled'] as bool? ?? true,
      createdAt: json['created_at'] as String? ?? '',
    );
  }

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'id': id,
      'name': name,
      'server': server,
      'provider_id': providerId,
      'surface_id': surfaceId,
      'surface_context': surfaceContext,
      'room_name_template': roomNameTemplate,
      'fist_bumps_enabled': fistBumpsEnabled,
      'created_at': createdAt,
    };
  }
}

class AppPrefs {
  const AppPrefs({
    required this.savedDisplayName,
    required this.lastProviderId,
    required this.lastKilterBoardId,
    required this.lastKilterAngle,
    required this.lastCruxGymSlug,
    required this.lastCruxWallId,
    required this.hostDefaults,
    required this.savedCredentials,
    required this.recentRooms,
    required this.savedSoloFilters,
    required this.soloFavorites,
    required this.soloShortlist,
    required this.intro,
    required this.onboarding,
    required this.guidedTour,
    required this.feedbackPrompts,
    required this.settings,
    required this.roomTemplates,
    this.pendingRoomSeed,
    this.soloResume,
  });

  final String savedDisplayName;
  final String lastProviderId;
  final String lastKilterBoardId;
  final int lastKilterAngle;
  final String lastCruxGymSlug;
  final String lastCruxWallId;
  final HostDefaults hostDefaults;
  final SavedCredentials savedCredentials;
  final List<RecentRoom> recentRooms;
  final List<SoloFilterPreset> savedSoloFilters;
  final List<SoloSavedClimb> soloFavorites;
  final List<SoloSavedClimb> soloShortlist;
  final List<RoomTemplate> roomTemplates;
  final PendingRoomSeed? pendingRoomSeed;
  final SoloResumeState? soloResume;
  final IntroProgress intro;
  final OnboardingProgress onboarding;
  final GuidedTourProgress guidedTour;
  final Map<String, String> feedbackPrompts;
  final AppSettings settings;

  factory AppPrefs.defaults() {
    return AppPrefs(
      savedDisplayName: '',
      lastProviderId: 'kilter',
      lastKilterBoardId: '',
      lastKilterAngle: defaultBoardAngle,
      lastCruxGymSlug: '',
      lastCruxWallId: '',
      hostDefaults: const HostDefaults(
        roomNameTemplate: '',
        defaultFistBumpsEnabled: true,
      ),
      savedCredentials: const SavedCredentials(
        providers: <String, SavedCredentialPreference>{
          'kilter': SavedCredentialPreference(remember: false),
          'crux': SavedCredentialPreference(remember: false),
        },
      ),
      recentRooms: const <RecentRoom>[],
      savedSoloFilters: const <SoloFilterPreset>[],
      soloFavorites: const <SoloSavedClimb>[],
      soloShortlist: const <SoloSavedClimb>[],
      intro: const IntroProgress(
        version: 1,
        landingDismissed: false,
        soloDismissed: false,
      ),
      onboarding: const OnboardingProgress(
        version: 1,
        dismissed: false,
        hostCompleted: false,
        guestCompleted: false,
        hostConnectedProvider: false,
        hostSelectedSurface: false,
        guestJoinedRoom: false,
        guestParticipated: false,
      ),
      guidedTour: const GuidedTourProgress(
        version: 2,
        landingCompleted: false,
        hostCompleted: false,
        guestCompleted: false,
        soloCompleted: false,
      ),
      feedbackPrompts: const <String, String>{},
      settings: const AppSettings(
        clickCheersEnabled: true,
        playfulMotionEnabled: true,
        autoGuidesEnabled: true,
        recentRoomsEnabled: true,
        soloDefaultSort: defaultClimbSort,
      ),
      roomTemplates: const <RoomTemplate>[],
    );
  }

  factory AppPrefs.fromJson(Map<String, dynamic> json) {
    final AppPrefs defaults = AppPrefs.defaults();
    final List<dynamic> rawRecentRooms =
        (json['recent_rooms'] as List<dynamic>?) ?? <dynamic>[];
    final List<dynamic> rawSavedFilters =
        (json['saved_solo_filters'] as List<dynamic>?) ?? <dynamic>[];
    final List<dynamic> rawFavorites =
        (json['solo_favorites'] as List<dynamic>?) ?? <dynamic>[];
    final List<dynamic> rawShortlist =
        (json['solo_shortlist'] as List<dynamic>?) ?? <dynamic>[];
    final List<dynamic> rawRoomTemplates =
        (json['room_templates'] as List<dynamic>?) ?? <dynamic>[];
    final Map<String, dynamic> rawFeedbackPrompts =
        (json['feedback_prompts'] as Map<String, dynamic>?) ??
            <String, dynamic>{};
    return AppPrefs(
      savedDisplayName:
          json['saved_display_name'] as String? ?? defaults.savedDisplayName,
      lastProviderId:
          json['last_provider_id'] as String? ?? defaults.lastProviderId,
      lastKilterBoardId:
          json['last_kilter_board_id'] as String? ?? defaults.lastKilterBoardId,
      lastKilterAngle: (json['last_kilter_angle'] as num?)?.toInt() ??
          defaults.lastKilterAngle,
      lastCruxGymSlug:
          json['last_crux_gym_slug'] as String? ?? defaults.lastCruxGymSlug,
      lastCruxWallId:
          json['last_crux_wall_id'] as String? ?? defaults.lastCruxWallId,
      hostDefaults: json['host_defaults'] is Map<String, dynamic>
          ? HostDefaults.fromJson(json['host_defaults'] as Map<String, dynamic>)
          : defaults.hostDefaults,
      savedCredentials: json['saved_credentials'] is Map<String, dynamic>
          ? SavedCredentials.fromJson(
              json['saved_credentials'] as Map<String, dynamic>)
          : defaults.savedCredentials,
      recentRooms: rawRecentRooms
          .whereType<Map<String, dynamic>>()
          .map(RecentRoom.fromJson)
          .toList(growable: false),
      savedSoloFilters: rawSavedFilters
          .whereType<Map<String, dynamic>>()
          .map(SoloFilterPreset.fromJson)
          .toList(growable: false),
      soloFavorites: rawFavorites
          .whereType<Map<String, dynamic>>()
          .map(SoloSavedClimb.fromJson)
          .toList(growable: false),
      soloShortlist: rawShortlist
          .whereType<Map<String, dynamic>>()
          .map(SoloSavedClimb.fromJson)
          .toList(growable: false),
      roomTemplates: rawRoomTemplates
          .whereType<Map<String, dynamic>>()
          .map(RoomTemplate.fromJson)
          .toList(growable: false),
      pendingRoomSeed: json['pending_room_seed'] is Map<String, dynamic>
          ? PendingRoomSeed.fromJson(
              json['pending_room_seed'] as Map<String, dynamic>)
          : null,
      soloResume: json['solo_resume'] is Map<String, dynamic>
          ? SoloResumeState.fromJson(
              json['solo_resume'] as Map<String, dynamic>)
          : null,
      intro: json['intro'] is Map<String, dynamic>
          ? IntroProgress.fromJson(json['intro'] as Map<String, dynamic>)
          : defaults.intro,
      onboarding: json['onboarding'] is Map<String, dynamic>
          ? OnboardingProgress.fromJson(
              json['onboarding'] as Map<String, dynamic>)
          : defaults.onboarding,
      guidedTour: json['guided_tour'] is Map<String, dynamic>
          ? GuidedTourProgress.fromJson(
              json['guided_tour'] as Map<String, dynamic>)
          : defaults.guidedTour,
      feedbackPrompts: rawFeedbackPrompts
          .map((String key, dynamic value) => MapEntry(key, '$value')),
      settings: json['settings'] is Map<String, dynamic>
          ? AppSettings.fromJson(json['settings'] as Map<String, dynamic>)
          : defaults.settings,
    );
  }

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'saved_display_name': savedDisplayName,
      'last_provider_id': lastProviderId,
      'last_kilter_board_id': lastKilterBoardId,
      'last_kilter_angle': lastKilterAngle,
      'last_crux_gym_slug': lastCruxGymSlug,
      'last_crux_wall_id': lastCruxWallId,
      'host_defaults': hostDefaults.toJson(),
      'saved_credentials': savedCredentials.toJson(),
      'recent_rooms': recentRooms
          .map((RecentRoom item) => item.toJson())
          .toList(growable: false),
      'saved_solo_filters': savedSoloFilters
          .map((SoloFilterPreset item) => item.toJson())
          .toList(growable: false),
      'solo_favorites': soloFavorites
          .map((SoloSavedClimb item) => item.toJson())
          .toList(growable: false),
      'solo_shortlist': soloShortlist
          .map((SoloSavedClimb item) => item.toJson())
          .toList(growable: false),
      'room_templates': roomTemplates
          .map((RoomTemplate item) => item.toJson())
          .toList(growable: false),
      'pending_room_seed': pendingRoomSeed?.toJson(),
      'solo_resume': soloResume?.toJson(),
      'intro': intro.toJson(),
      'onboarding': onboarding.toJson(),
      'guided_tour': guidedTour.toJson(),
      'feedback_prompts': feedbackPrompts,
      'settings': settings.toJson(),
    };
  }
}
