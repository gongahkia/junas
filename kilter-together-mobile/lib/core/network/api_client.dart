import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/board_models.dart';
import '../models/catalog_models.dart';
import '../models/product_models.dart';
import '../models/provider_models.dart';

final Provider<ApiClient> apiClientProvider = Provider<ApiClient>((Ref ref) {
  return ApiClient();
});

class ApiFailure implements Exception {
  const ApiFailure({required this.message, this.statusCode, this.code});
  final String message;
  final int? statusCode;
  final String? code;
  factory ApiFailure.fromDio(DioException error) {
    final Response<dynamic>? response = error.response;
    final dynamic payload = response?.data;
    if (payload is Map<String, dynamic>) {
      final String? message = payload['error'] as String?;
      final String? code = payload['code'] as String?;
      return ApiFailure(
        message: message?.trim().isNotEmpty == true ? message!.trim() : error.message ?? 'Request failed.',
        statusCode: response?.statusCode,
        code: code,
      );
    }
    return ApiFailure(message: error.message ?? 'Request failed.', statusCode: response?.statusCode);
  }
  @override
  String toString() => message;
}

/// stripped api client — only direct provider/catalog calls used by solo mode
class ApiClient {
  ApiClient();
  Dio _clientFor(Uri server) {
    return Dio(BaseOptions(
      baseUrl: server.resolve('/api/').toString(),
      connectTimeout: const Duration(seconds: 12),
      receiveTimeout: const Duration(seconds: 12),
      sendTimeout: const Duration(seconds: 12),
      headers: const <String, String>{'Accept': 'application/json'},
    ));
  }
  Never _throwFailure(DioException error) => throw ApiFailure.fromDio(error);
  Map<String, dynamic> _mapPayload(dynamic data) => (data as Map<String, dynamic>?) ?? <String, dynamic>{};

  Future<List<ProviderCapability>> getProviderCapabilities(Uri server) async {
    try {
      final Response<dynamic> response = await _clientFor(server).get<dynamic>('providers/capabilities');
      final Map<String, dynamic> payload = _mapPayload(response.data);
      final List<dynamic> rawProviders = (payload['providers'] as List<dynamic>?) ?? <dynamic>[];
      return rawProviders.whereType<Map<String, dynamic>>().map(ProviderCapability.fromJson).toList(growable: false);
    } on DioException catch (error) { _throwFailure(error); }
  }

  Future<List<BoardOption>> getBoards(Uri server) async {
    try {
      final Response<dynamic> response = await _clientFor(server).get<dynamic>('boards');
      final Map<String, dynamic> payload = _mapPayload(response.data);
      final List<dynamic> rawBoards = (payload['boards'] as List<dynamic>?) ?? <dynamic>[];
      return rawBoards.whereType<Map<String, dynamic>>().map(BoardOption.fromJson).toList(growable: false);
    } on DioException catch (error) { _throwFailure(error); }
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
    String? gradeMin,
    String? gradeMax,
    String? sort,
  }) async {
    try {
      final Response<dynamic> response = await _clientFor(server).get<dynamic>(
        'climbs',
        queryParameters: <String, dynamic>{
          'board_id': boardId, 'angle': angle, 'page_size': pageSize,
          'cursor': cursor, 'name': name, 'setter': setter, 'grade': grade,
          'grade_min': gradeMin, 'grade_max': gradeMax, 'sort': sort,
        },
      );
      return PaginatedBoardClimbsResponse.fromJson(_mapPayload(response.data));
    } on DioException catch (error) { _throwFailure(error); }
  }

  Future<CatalogManifest> getKilterCatalogManifest({required Uri server}) async {
    try {
      final Response<dynamic> response = await _clientFor(server).get<dynamic>('catalog/kilter/manifest');
      return CatalogManifest.fromJson(_mapPayload(response.data));
    } on DioException catch (error) { _throwFailure(error); }
  }

  Future<CatalogBootstrapResponse> getKilterCatalogBootstrap({
    required Uri server,
    String? cursor,
    int pageSize = 200,
  }) async {
    try {
      final Response<dynamic> response = await _clientFor(server).get<dynamic>(
        'catalog/kilter/bootstrap',
        queryParameters: <String, dynamic>{'cursor': cursor, 'page_size': pageSize},
      );
      final Map<String, dynamic> payload = _mapPayload(response.data);
      return CatalogBootstrapResponse(
        manifest: CatalogManifest.fromJson((payload['manifest'] as Map<String, dynamic>?) ?? <String, dynamic>{}),
        boards: ((payload['boards'] as List<dynamic>?) ?? <dynamic>[])
            .whereType<Map<String, dynamic>>().map(BoardOption.fromJson).toList(growable: false),
        climbs: ((payload['climbs'] as List<dynamic>?) ?? <dynamic>[])
            .whereType<Map<String, dynamic>>().map(CatalogClimb.fromJson).toList(growable: false),
        hasMore: payload['has_more'] as bool? ?? false,
        pageSize: (payload['page_size'] as num?)?.toInt() ?? pageSize,
        syncToken: payload['sync_token'] as String?,
        nextCursor: payload['next_cursor'] as String?,
      );
    } on DioException catch (error) { _throwFailure(error); }
  }

  Future<CatalogDeltaResponse> getKilterCatalogDelta({
    required Uri server,
    String? afterToken,
  }) async {
    try {
      final Response<dynamic> response = await _clientFor(server).get<dynamic>(
        'catalog/kilter/delta',
        queryParameters: <String, dynamic>{'after_token': afterToken},
      );
      final Map<String, dynamic> payload = _mapPayload(response.data);
      return CatalogDeltaResponse(
        manifest: CatalogManifest.fromJson((payload['manifest'] as Map<String, dynamic>?) ?? <String, dynamic>{}),
        climbs: ((payload['climbs'] as List<dynamic>?) ?? <dynamic>[])
            .whereType<Map<String, dynamic>>().map(CatalogClimb.fromJson).toList(growable: false),
        requiresFullResync: payload['requires_full_resync'] as bool? ?? false,
        nextToken: payload['next_token'] as String?,
      );
    } on DioException catch (error) { _throwFailure(error); }
  }

  Future<List<int>> downloadImageBytes({required Uri server, required String filename}) async {
    try {
      final Response<List<int>> response = await _clientFor(server).get<List<int>>(
        'images/${Uri.encodeComponent(filename.contains('/') ? filename.split('/').last : filename)}',
        options: Options(responseType: ResponseType.bytes),
      );
      return response.data ?? const <int>[];
    } on DioException catch (error) { _throwFailure(error); }
  }

  String getImageUrl({required Uri server, required String filename}) {
    final String baseName = filename.contains('/') ? filename.split('/').last : filename;
    return server.resolve('/api/').resolve('images/$baseName').toString();
  }

  String resolveMediaUrl({required Uri server, required String url}) {
    final String trimmed = url.trim();
    if (trimmed.isEmpty) return trimmed;
    if (trimmed.startsWith('data:') ||
        RegExp(r'^(https?:)?//', caseSensitive: false).hasMatch(trimmed)) {
      return trimmed;
    }
    return server.resolve(trimmed).toString();
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
        data: <String, dynamic>{'secret': secret, 'parent_id': parentId},
      );
      final Map<String, dynamic> payload = _mapPayload(response.data);
      return ((payload['surfaces'] as List<dynamic>?) ?? <dynamic>[])
          .whereType<Map<String, dynamic>>().map(ProviderSurface.fromJson).toList(growable: false);
    } on DioException catch (error) { _throwFailure(error); }
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
    String? gradeMin,
    String? gradeMax,
    int pageSize = 10,
  }) async {
    try {
      final Response<dynamic> response = await _clientFor(server).post<dynamic>(
        'solo/providers/$providerId/climbs',
        data: <String, dynamic>{
          'secret': secret, 'surface_id': surfaceId, 'context': context,
          'q': q, 'sort': sort, 'cursor': cursor, 'grade_min': gradeMin,
          'grade_max': gradeMax, 'page_size': pageSize,
        },
      );
      return ProviderCatalogClimbsResponse.fromJson(_mapPayload(response.data));
    } on DioException catch (error) { _throwFailure(error); }
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
        data: <String, dynamic>{'secret': secret, 'surface_id': surfaceId, 'context': context},
      );
      return ProviderCatalogClimbResponse.fromJson(_mapPayload(response.data));
    } on DioException catch (error) { _throwFailure(error); }
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
          'provider_id': providerId, 'title': title, 'notes': notes,
          'surface': surface.toJson(), 'context': context, 'filters': filters,
          'climbs': climbs.map((ProviderClimb item) => item.toJson()).toList(growable: false),
          'open_path': openPath, 'created_by': createdBy,
        },
      );
      return SoloPlanSnapshot.fromJson(_mapPayload(response.data));
    } on DioException catch (error) { _throwFailure(error); }
  }

  Future<SoloPlanSnapshot> getSoloPlan({required Uri server, required String shareId}) async {
    try {
      final Response<dynamic> response = await _clientFor(server)
          .get<dynamic>('solo/plans/${Uri.encodeComponent(shareId)}');
      return SoloPlanSnapshot.fromJson(_mapPayload(response.data));
    } on DioException catch (error) { _throwFailure(error); }
  }
}
