import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/board_models.dart';
import '../models/catalog_models.dart';
import '../models/product_models.dart';
import '../models/provider_models.dart';
import '../models/runtime_models.dart';
import '../models/room_models.dart';
import '../models/session_models.dart';

final Provider<ApiClient> apiClientProvider = Provider<ApiClient>((Ref ref) {
  return ApiClient();
});

class ApiFailure implements Exception {
  const ApiFailure({
    required this.message,
    this.statusCode,
    this.code,
  });

  final String message;
  final int? statusCode;
  final String? code;

  bool get isAuthFailure {
    return statusCode == 401 ||
        code == 'session_expired' ||
        code == 'session_invalid' ||
        code == 'session_required' ||
        code == 'unauthorized';
  }

  factory ApiFailure.fromDio(DioException error) {
    final Response<dynamic>? response = error.response;
    final dynamic payload = response?.data;
    if (payload is Map<String, dynamic>) {
      final String? message = payload['error'] as String?;
      final String? code = payload['code'] as String?;
      return ApiFailure(
        message: message?.trim().isNotEmpty == true
            ? message!.trim()
            : error.message ?? 'Request failed.',
        statusCode: response?.statusCode,
        code: code,
      );
    }
    return ApiFailure(
      message: error.message ?? 'Request failed.',
      statusCode: response?.statusCode,
    );
  }

  @override
  String toString() => message;
}

class ApiClient {
  ApiClient();

  Uri apiBase(Uri server) => server.resolve('/api/');

  Dio _clientFor(Uri server) {
    return Dio(
      BaseOptions(
        baseUrl: apiBase(server).toString(),
        connectTimeout: const Duration(seconds: 12),
        receiveTimeout: const Duration(seconds: 12),
        sendTimeout: const Duration(seconds: 12),
        headers: const <String, String>{
          'Accept': 'application/json',
        },
      ),
    );
  }

  Options _authOptions(String sessionToken) {
    return Options(
      headers: <String, String>{
        'Authorization': 'Bearer $sessionToken',
      },
    );
  }

  Never _throwFailure(DioException error) {
    throw ApiFailure.fromDio(error);
  }

  Map<String, dynamic> _mapPayload(dynamic data) {
    return (data as Map<String, dynamic>?) ?? <String, dynamic>{};
  }

  Future<List<ProviderCapability>> getProviderCapabilities(Uri server) async {
    try {
      final Response<dynamic> response =
          await _clientFor(server).get<dynamic>('providers/capabilities');
      final Map<String, dynamic> payload = _mapPayload(response.data);
      final List<dynamic> rawProviders =
          (payload['providers'] as List<dynamic>?) ?? <dynamic>[];
      return rawProviders
          .whereType<Map<String, dynamic>>()
          .map(ProviderCapability.fromJson)
          .toList(growable: false);
    } on DioException catch (error) {
      _throwFailure(error);
    }
  }

  Future<List<SessionSummary>> getRecentSessions({
    required Uri server,
    int limit = 6,
  }) async {
    try {
      final Response<dynamic> response = await _clientFor(server).get<dynamic>(
        'sessions/recent',
        queryParameters: <String, dynamic>{'limit': limit},
      );
      final Map<String, dynamic> payload = _mapPayload(response.data);
      final List<dynamic> rawSessions =
          (payload['sessions'] as List<dynamic>?) ?? <dynamic>[];
      return rawSessions
          .whereType<Map<String, dynamic>>()
          .map(SessionSummary.fromJson)
          .toList(growable: false);
    } on DioException catch (error) {
      _throwFailure(error);
    }
  }

  Future<RuntimeStatus> getRuntimeStatus({
    required Uri server,
  }) async {
    try {
      final Response<dynamic> response =
          await _clientFor(server).get<dynamic>('runtime/status');
      return RuntimeStatus.fromJson(_mapPayload(response.data));
    } on DioException catch (error) {
      _throwFailure(error);
    }
  }

  Future<void> submitFeedback({
    required Uri server,
    String? roomSlug,
    String? shareId,
    required String promptFamily,
    required String sentiment,
    String? message,
    String? route,
    Map<String, dynamic> metadata = const <String, dynamic>{},
  }) async {
    try {
      await _clientFor(server).post<dynamic>(
        'feedback',
        data: <String, dynamic>{
          'room_slug': roomSlug,
          'share_id': shareId,
          'prompt_family': promptFamily,
          'sentiment': sentiment,
          'message': message,
          'route': route,
          'metadata': metadata,
        },
      );
    } on DioException catch (error) {
      _throwFailure(error);
    }
  }

  Future<RoomRecap> getRoomRecap({
    required Uri server,
    required String shareId,
  }) async {
    try {
      final Response<dynamic> response = await _clientFor(server)
          .get<dynamic>('recaps/${Uri.encodeComponent(shareId)}');
      return RoomRecap.fromJson(_mapPayload(response.data));
    } on DioException catch (error) {
      _throwFailure(error);
    }
  }

  Future<SoloPlanSnapshot> createSoloPlan({
    required Uri server,
    required String providerId,
    required String title,
    String? notes,
    required ProviderSurface surface,
    Map<String, String> context = const <String, String>{},
    Map<String, String> filters = const <String, String>{},
    required List<ProviderClimb> climbs,
    String? openPath,
    String? createdBy,
  }) async {
    try {
      final Response<dynamic> response = await _clientFor(server).post<dynamic>(
        'solo/plans',
        data: <String, dynamic>{
          'provider_id': providerId,
          'title': title,
          'notes': notes,
          'surface': surface.toJson(),
          'context': context,
          'filters': filters,
          'climbs': climbs
              .map((ProviderClimb item) => item.toJson())
              .toList(growable: false),
          'open_path': openPath,
          'created_by': createdBy,
        },
      );
      return SoloPlanSnapshot.fromJson(_mapPayload(response.data));
    } on DioException catch (error) {
      _throwFailure(error);
    }
  }

  Future<SoloPlanSnapshot> getSoloPlan({
    required Uri server,
    required String shareId,
  }) async {
    try {
      final Response<dynamic> response = await _clientFor(server)
          .get<dynamic>('solo/plans/${Uri.encodeComponent(shareId)}');
      return SoloPlanSnapshot.fromJson(_mapPayload(response.data));
    } on DioException catch (error) {
      _throwFailure(error);
    }
  }

  Future<List<BoardOption>> getBoards(Uri server) async {
    try {
      final Response<dynamic> response =
          await _clientFor(server).get<dynamic>('boards');
      final Map<String, dynamic> payload = _mapPayload(response.data);
      final List<dynamic> rawBoards =
          (payload['boards'] as List<dynamic>?) ?? <dynamic>[];
      return rawBoards
          .whereType<Map<String, dynamic>>()
          .map(BoardOption.fromJson)
          .toList(growable: false);
    } on DioException catch (error) {
      _throwFailure(error);
    }
  }

  Future<PaginatedBoardClimbsResponse> getPaginatedClimbs({
    required Uri server,
    required String boardId,
    required int angle,
    String? cursor,
    int pageSize = 10,
    String? name,
    String? setter,
    String? grade,
    String? sort,
  }) async {
    try {
      final Response<dynamic> response = await _clientFor(server).get<dynamic>(
        'climbs',
        queryParameters: <String, dynamic>{
          'board_id': boardId,
          'angle': angle,
          'page_size': pageSize,
          'cursor': cursor,
          'name': name,
          'setter': setter,
          'grade': grade,
          'sort': sort,
        },
      );
      return PaginatedBoardClimbsResponse.fromJson(_mapPayload(response.data));
    } on DioException catch (error) {
      _throwFailure(error);
    }
  }

  Future<CatalogManifest> getKilterCatalogManifest({
    required Uri server,
  }) async {
    try {
      final Response<dynamic> response =
          await _clientFor(server).get<dynamic>('catalog/kilter/manifest');
      return CatalogManifest.fromJson(_mapPayload(response.data));
    } on DioException catch (error) {
      _throwFailure(error);
    }
  }

  Future<CatalogBootstrapResponse> getKilterCatalogBootstrap({
    required Uri server,
    String? cursor,
    int pageSize = 200,
  }) async {
    try {
      final Response<dynamic> response = await _clientFor(server).get<dynamic>(
        'catalog/kilter/bootstrap',
        queryParameters: <String, dynamic>{
          'cursor': cursor,
          'page_size': pageSize,
        },
      );
      final Map<String, dynamic> payload = _mapPayload(response.data);
      final List<dynamic> rawBoards =
          (payload['boards'] as List<dynamic>?) ?? <dynamic>[];
      final List<dynamic> rawClimbs =
          (payload['climbs'] as List<dynamic>?) ?? <dynamic>[];
      return CatalogBootstrapResponse(
        manifest: CatalogManifest.fromJson(
          (payload['manifest'] as Map<String, dynamic>?) ?? <String, dynamic>{},
        ),
        boards: rawBoards
            .whereType<Map<String, dynamic>>()
            .map(BoardOption.fromJson)
            .toList(growable: false),
        climbs: rawClimbs
            .whereType<Map<String, dynamic>>()
            .map(CatalogClimb.fromJson)
            .toList(growable: false),
        hasMore: payload['has_more'] as bool? ?? false,
        pageSize: (payload['page_size'] as num?)?.toInt() ?? pageSize,
        syncToken: payload['sync_token'] as String?,
        nextCursor: payload['next_cursor'] as String?,
      );
    } on DioException catch (error) {
      _throwFailure(error);
    }
  }

  Future<CatalogDeltaResponse> getKilterCatalogDelta({
    required Uri server,
    String? afterToken,
  }) async {
    try {
      final Response<dynamic> response = await _clientFor(server).get<dynamic>(
        'catalog/kilter/delta',
        queryParameters: <String, dynamic>{
          'after_token': afterToken,
        },
      );
      final Map<String, dynamic> payload = _mapPayload(response.data);
      final List<dynamic> rawClimbs =
          (payload['climbs'] as List<dynamic>?) ?? <dynamic>[];
      return CatalogDeltaResponse(
        manifest: CatalogManifest.fromJson(
          (payload['manifest'] as Map<String, dynamic>?) ?? <String, dynamic>{},
        ),
        climbs: rawClimbs
            .whereType<Map<String, dynamic>>()
            .map(CatalogClimb.fromJson)
            .toList(growable: false),
        requiresFullResync: payload['requires_full_resync'] as bool? ?? false,
        nextToken: payload['next_token'] as String?,
      );
    } on DioException catch (error) {
      _throwFailure(error);
    }
  }

  Future<List<int>> downloadImageBytes({
    required Uri server,
    required String filename,
  }) async {
    try {
      final Response<List<int>> response =
          await _clientFor(server).get<List<int>>(
        'images/${Uri.encodeComponent(filename.contains('/') ? filename.split('/').last : filename)}',
        options: Options(responseType: ResponseType.bytes),
      );
      return response.data ?? const <int>[];
    } on DioException catch (error) {
      _throwFailure(error);
    }
  }

  String getImageUrl({
    required Uri server,
    required String filename,
  }) {
    final String baseName =
        filename.contains('/') ? filename.split('/').last : filename;
    return apiBase(server).resolve('images/$baseName').toString();
  }

  String resolveMediaUrl({
    required Uri server,
    required String url,
  }) {
    final String trimmed = url.trim();
    if (trimmed.isEmpty) {
      return trimmed;
    }
    if (trimmed.startsWith('data:') ||
        RegExp(r'^(https?:)?//', caseSensitive: false).hasMatch(trimmed)) {
      return trimmed;
    }
    return server.resolve(trimmed).toString();
  }

  Future<RoomSessionEnvelope> createRoom({
    required Uri server,
    required String providerId,
    required String roomName,
    required String displayName,
    required Map<String, String> secret,
    required bool fistBumpsEnabled,
  }) async {
    try {
      final Response<dynamic> response = await _clientFor(server).post<dynamic>(
        'rooms',
        data: <String, dynamic>{
          'provider_id': providerId,
          'room_name': roomName,
          'display_name': displayName,
          'secret': secret,
          'fist_bumps_enabled': fistBumpsEnabled,
        },
      );
      return RoomSessionEnvelope.fromJson(_mapPayload(response.data));
    } on DioException catch (error) {
      _throwFailure(error);
    }
  }

  Future<RoomSessionEnvelope> joinRoom({
    required Uri server,
    required String slug,
    required String displayName,
  }) async {
    try {
      final Response<dynamic> response = await _clientFor(server).post<dynamic>(
        'rooms/$slug/join',
        data: <String, dynamic>{
          'display_name': displayName,
        },
      );
      return RoomSessionEnvelope.fromJson(_mapPayload(response.data));
    } on DioException catch (error) {
      _throwFailure(error);
    }
  }

  Future<RoomSnapshot> getRoom({
    required Uri server,
    required String slug,
    required String sessionToken,
  }) async {
    try {
      final Response<dynamic> response = await _clientFor(server).get<dynamic>(
        'rooms/$slug',
        options: _authOptions(sessionToken),
      );
      return RoomSnapshot.fromJson(_mapPayload(response.data));
    } on DioException catch (error) {
      _throwFailure(error);
    }
  }

  Future<RoomSnapshot> updateRoom({
    required Uri server,
    required String slug,
    required String sessionToken,
    required String roomName,
  }) async {
    try {
      final Response<dynamic> response =
          await _clientFor(server).patch<dynamic>(
        'rooms/$slug',
        data: <String, dynamic>{'room_name': roomName},
        options: _authOptions(sessionToken),
      );
      return RoomSnapshot.fromJson(_mapPayload(response.data));
    } on DioException catch (error) {
      _throwFailure(error);
    }
  }

  Future<RoomSnapshot> setRoomFistBumpsEnabled({
    required Uri server,
    required String slug,
    required String sessionToken,
    required bool enabled,
  }) async {
    try {
      final Response<dynamic> response = await _clientFor(server).put<dynamic>(
        'rooms/$slug/fist-bumps/settings',
        data: <String, dynamic>{'enabled': enabled},
        options: _authOptions(sessionToken),
      );
      return RoomSnapshot.fromJson(_mapPayload(response.data));
    } on DioException catch (error) {
      _throwFailure(error);
    }
  }

  Future<RoomSnapshot> updateRoomAssistantMode({
    required Uri server,
    required String slug,
    required String sessionToken,
    required String mode,
  }) async {
    try {
      final Response<dynamic> response = await _clientFor(server).put<dynamic>(
        'rooms/$slug/assistant/settings',
        data: <String, dynamic>{'mode': mode},
        options: _authOptions(sessionToken),
      );
      return RoomSnapshot.fromJson(_mapPayload(response.data));
    } on DioException catch (error) {
      _throwFailure(error);
    }
  }

  Future<ProviderConnectionState> connectRoomProvider({
    required Uri server,
    required String slug,
    required String sessionToken,
    required Map<String, String> secret,
  }) async {
    try {
      final Response<dynamic> response = await _clientFor(server).post<dynamic>(
        'rooms/$slug/provider/connect',
        data: <String, dynamic>{'secret': secret},
        options: _authOptions(sessionToken),
      );
      return ProviderConnectionState.fromJson(_mapPayload(response.data));
    } on DioException catch (error) {
      _throwFailure(error);
    }
  }

  Future<List<ProviderSurface>> getRoomCatalogSurfaces({
    required Uri server,
    required String slug,
    required String sessionToken,
    String? parentId,
  }) async {
    try {
      final Response<dynamic> response = await _clientFor(server).get<dynamic>(
        'rooms/$slug/catalog/surfaces',
        queryParameters: <String, dynamic>{'parent_id': parentId},
        options: _authOptions(sessionToken),
      );
      final Map<String, dynamic> payload = _mapPayload(response.data);
      final List<dynamic> rawSurfaces =
          (payload['surfaces'] as List<dynamic>?) ?? <dynamic>[];
      return rawSurfaces
          .whereType<Map<String, dynamic>>()
          .map(ProviderSurface.fromJson)
          .toList(growable: false);
    } on DioException catch (error) {
      _throwFailure(error);
    }
  }

  Future<ProviderSurface> setRoomSurface({
    required Uri server,
    required String slug,
    required String sessionToken,
    required String surfaceId,
    Map<String, String> context = const <String, String>{},
  }) async {
    try {
      final Response<dynamic> response = await _clientFor(server).post<dynamic>(
        'rooms/$slug/surface',
        data: <String, dynamic>{
          'surface_id': surfaceId,
          'context': context,
        },
        options: _authOptions(sessionToken),
      );
      return ProviderSurface.fromJson(_mapPayload(response.data));
    } on DioException catch (error) {
      _throwFailure(error);
    }
  }

  Future<RoomCatalogClimbsResponse> getRoomCatalogClimbs({
    required Uri server,
    required String slug,
    required String sessionToken,
    String? q,
    String? sort,
    String? cursor,
    int pageSize = 10,
  }) async {
    try {
      final Response<dynamic> response = await _clientFor(server).get<dynamic>(
        'rooms/$slug/catalog/climbs',
        queryParameters: <String, dynamic>{
          'q': q,
          'sort': sort,
          'cursor': cursor,
          'page_size': pageSize,
        },
        options: _authOptions(sessionToken),
      );
      return RoomCatalogClimbsResponse.fromJson(_mapPayload(response.data));
    } on DioException catch (error) {
      _throwFailure(error);
    }
  }

  Future<RoomCatalogClimbResponse> getRoomCatalogClimb({
    required Uri server,
    required String slug,
    required String sessionToken,
    required String climbId,
  }) async {
    try {
      final Response<dynamic> response = await _clientFor(server).get<dynamic>(
        'rooms/$slug/catalog/climbs/${Uri.encodeComponent(climbId)}',
        options: _authOptions(sessionToken),
      );
      return RoomCatalogClimbResponse.fromJson(_mapPayload(response.data));
    } on DioException catch (error) {
      _throwFailure(error);
    }
  }

  Future<void> toggleRoomVote({
    required Uri server,
    required String slug,
    required String sessionToken,
    required String climbId,
  }) async {
    try {
      await _clientFor(server).put<dynamic>(
        'rooms/$slug/votes/${Uri.encodeComponent(climbId)}',
        options: _authOptions(sessionToken),
      );
    } on DioException catch (error) {
      _throwFailure(error);
    }
  }

  Future<void> addRoomQueueEntry({
    required Uri server,
    required String slug,
    required String sessionToken,
    required String climbId,
  }) async {
    try {
      await _clientFor(server).post<dynamic>(
        'rooms/$slug/queue',
        data: <String, dynamic>{'climb_id': climbId},
        options: _authOptions(sessionToken),
      );
    } on DioException catch (error) {
      _throwFailure(error);
    }
  }

  Future<void> addRoomFinalist({
    required Uri server,
    required String slug,
    required String sessionToken,
    required String climbId,
  }) async {
    try {
      await _clientFor(server).post<dynamic>(
        'rooms/$slug/finalists',
        data: <String, dynamic>{'climb_id': climbId},
        options: _authOptions(sessionToken),
      );
    } on DioException catch (error) {
      _throwFailure(error);
    }
  }

  Future<void> reorderRoomFinalists({
    required Uri server,
    required String slug,
    required String sessionToken,
    required List<int> entryIds,
  }) async {
    try {
      await _clientFor(server).patch<dynamic>(
        'rooms/$slug/finalists/reorder',
        data: <String, dynamic>{'entry_ids': entryIds},
        options: _authOptions(sessionToken),
      );
    } on DioException catch (error) {
      _throwFailure(error);
    }
  }

  Future<void> deleteRoomFinalist({
    required Uri server,
    required String slug,
    required String sessionToken,
    required int entryId,
  }) async {
    try {
      await _clientFor(server).delete<dynamic>(
        'rooms/$slug/finalists/$entryId',
        options: _authOptions(sessionToken),
      );
    } on DioException catch (error) {
      _throwFailure(error);
    }
  }

  Future<ProviderClimb> pickRandomRoomClimb({
    required Uri server,
    required String slug,
    required String sessionToken,
    required String source,
  }) async {
    try {
      final Response<dynamic> response = await _clientFor(server).post<dynamic>(
        'rooms/$slug/pick-random',
        data: <String, dynamic>{'source': source},
        options: _authOptions(sessionToken),
      );
      final Map<String, dynamic> payload = _mapPayload(response.data);
      return ProviderClimb.fromJson(
          (payload['climb'] as Map<String, dynamic>?) ?? <String, dynamic>{});
    } on DioException catch (error) {
      _throwFailure(error);
    }
  }

  Future<void> reorderRoomQueue({
    required Uri server,
    required String slug,
    required String sessionToken,
    required List<int> entryIds,
  }) async {
    try {
      await _clientFor(server).patch<dynamic>(
        'rooms/$slug/queue/reorder',
        data: <String, dynamic>{'entry_ids': entryIds},
        options: _authOptions(sessionToken),
      );
    } on DioException catch (error) {
      _throwFailure(error);
    }
  }

  Future<void> promoteRoomQueueClimb({
    required Uri server,
    required String slug,
    required String sessionToken,
    required String climbId,
    required String status,
  }) async {
    try {
      await _clientFor(server).post<dynamic>(
        'rooms/$slug/queue/promote',
        data: <String, dynamic>{
          'climb_id': climbId,
          'status': status,
        },
        options: _authOptions(sessionToken),
      );
    } on DioException catch (error) {
      _throwFailure(error);
    }
  }

  Future<void> updateRoomQueueEntry({
    required Uri server,
    required String slug,
    required String sessionToken,
    required int entryId,
    required String status,
  }) async {
    try {
      await _clientFor(server).patch<dynamic>(
        'rooms/$slug/queue/$entryId',
        data: <String, dynamic>{'status': status},
        options: _authOptions(sessionToken),
      );
    } on DioException catch (error) {
      _throwFailure(error);
    }
  }

  Future<void> deleteRoomQueueEntry({
    required Uri server,
    required String slug,
    required String sessionToken,
    required int entryId,
  }) async {
    try {
      await _clientFor(server).delete<dynamic>(
        'rooms/$slug/queue/$entryId',
        options: _authOptions(sessionToken),
      );
    } on DioException catch (error) {
      _throwFailure(error);
    }
  }

  Future<void> clearRoomVotes({
    required Uri server,
    required String slug,
    required String sessionToken,
  }) async {
    try {
      await _clientFor(server).post<dynamic>(
        'rooms/$slug/clear-votes',
        options: _authOptions(sessionToken),
      );
    } on DioException catch (error) {
      _throwFailure(error);
    }
  }

  Future<void> closeRoom({
    required Uri server,
    required String slug,
    required String sessionToken,
  }) async {
    try {
      await _clientFor(server).post<dynamic>(
        'rooms/$slug/close',
        options: _authOptions(sessionToken),
      );
    } on DioException catch (error) {
      _throwFailure(error);
    }
  }

  Future<void> removeRoomParticipant({
    required Uri server,
    required String slug,
    required String sessionToken,
    required int participantId,
  }) async {
    try {
      await _clientFor(server).delete<dynamic>(
        'rooms/$slug/participants/$participantId',
        options: _authOptions(sessionToken),
      );
    } on DioException catch (error) {
      _throwFailure(error);
    }
  }

  Future<void> updateRoomParticipantRole({
    required Uri server,
    required String slug,
    required String sessionToken,
    required int participantId,
    required String role,
  }) async {
    try {
      await _clientFor(server).patch<dynamic>(
        'rooms/$slug/participants/$participantId/role',
        data: <String, dynamic>{'role': role},
        options: _authOptions(sessionToken),
      );
    } on DioException catch (error) {
      _throwFailure(error);
    }
  }

  Future<void> updateMyParticipantStatus({
    required Uri server,
    required String slug,
    required String sessionToken,
    required String status,
  }) async {
    try {
      await _clientFor(server).put<dynamic>(
        'rooms/$slug/participants/me/status',
        data: <String, dynamic>{'status': status},
        options: _authOptions(sessionToken),
      );
    } on DioException catch (error) {
      _throwFailure(error);
    }
  }

  Future<List<ProviderSurface>> getSoloProviderSurfaces({
    required Uri server,
    required String providerId,
    required Map<String, String> secret,
    String? parentId,
  }) async {
    try {
      final Response<dynamic> response = await _clientFor(server).post<dynamic>(
        'solo/providers/$providerId/surfaces',
        data: <String, dynamic>{
          'secret': secret,
          'parent_id': parentId,
        },
      );
      final Map<String, dynamic> payload = _mapPayload(response.data);
      final List<dynamic> rawSurfaces =
          (payload['surfaces'] as List<dynamic>?) ?? <dynamic>[];
      return rawSurfaces
          .whereType<Map<String, dynamic>>()
          .map(ProviderSurface.fromJson)
          .toList(growable: false);
    } on DioException catch (error) {
      _throwFailure(error);
    }
  }

  Future<ProviderCatalogClimbsResponse> getSoloProviderClimbs({
    required Uri server,
    required String providerId,
    required Map<String, String> secret,
    String? surfaceId,
    Map<String, String> context = const <String, String>{},
    String? q,
    String? sort,
    String? cursor,
    int pageSize = 10,
  }) async {
    try {
      final Response<dynamic> response = await _clientFor(server).post<dynamic>(
        'solo/providers/$providerId/climbs',
        data: <String, dynamic>{
          'secret': secret,
          'surface_id': surfaceId,
          'context': context,
          'q': q,
          'sort': sort,
          'cursor': cursor,
          'page_size': pageSize,
        },
      );
      return ProviderCatalogClimbsResponse.fromJson(_mapPayload(response.data));
    } on DioException catch (error) {
      _throwFailure(error);
    }
  }

  Future<ProviderCatalogClimbResponse> getSoloProviderClimb({
    required Uri server,
    required String providerId,
    required String climbId,
    required Map<String, String> secret,
    String? surfaceId,
    Map<String, String> context = const <String, String>{},
  }) async {
    try {
      final Response<dynamic> response = await _clientFor(server).post<dynamic>(
        'solo/providers/$providerId/climbs/${Uri.encodeComponent(climbId)}',
        data: <String, dynamic>{
          'secret': secret,
          'surface_id': surfaceId,
          'context': context,
        },
      );
      return ProviderCatalogClimbResponse.fromJson(_mapPayload(response.data));
    } on DioException catch (error) {
      _throwFailure(error);
    }
  }

  Uri getRoomEventsUri({
    required Uri server,
    required String slug,
  }) {
    return apiBase(server).resolve('rooms/$slug/events');
  }

  Future<({String ticket, DateTime expiresAt})> getSSETicket({
    required Uri server,
    required String slug,
    required String sessionToken,
  }) async {
    try {
      final Response<dynamic> response = await _clientFor(server).post<dynamic>(
        'rooms/$slug/events/ticket',
        options: _authOptions(sessionToken),
      );
      final Map<String, dynamic> payload = _mapPayload(response.data);
      return (
        ticket: payload['ticket'] as String? ?? '',
        expiresAt: DateTime.tryParse(payload['expires_at'] as String? ?? '') ?? DateTime.now().toUtc(),
      );
    } on DioException catch (error) {
      _throwFailure(error);
    }
  }

  Future<RoomSession> refreshSession({
    required Uri server,
    required String slug,
    required String sessionToken,
  }) async {
    try {
      final Response<dynamic> response = await _clientFor(server).post<dynamic>(
        'rooms/$slug/session/refresh',
        options: _authOptions(sessionToken),
      );
      return RoomSession.fromJson(_mapPayload(response.data));
    } on DioException catch (error) {
      _throwFailure(error);
    }
  }
}
