import 'package:dio/dio.dart';

import '../models/provider_models.dart';
import '../models/room_models.dart';
import '../models/session_models.dart';

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

  Future<List<ProviderCapability>> getProviderCapabilities(Uri server) async {
    final Response<dynamic> response = await _clientFor(server).get<dynamic>('/providers/capabilities');
    final Map<String, dynamic> payload = (response.data as Map<String, dynamic>?) ?? <String, dynamic>{};
    final List<dynamic> rawProviders = (payload['providers'] as List<dynamic>?) ?? <dynamic>[];
    return rawProviders
        .whereType<Map<String, dynamic>>()
        .map(ProviderCapability.fromJson)
        .toList(growable: false);
  }

  Future<RoomSessionEnvelope> createRoom({
    required Uri server,
    required String providerId,
    required String roomName,
    required String displayName,
    required Map<String, String> secret,
    required bool fistBumpsEnabled,
  }) async {
    final Response<dynamic> response = await _clientFor(server).post<dynamic>(
      '/rooms',
      data: <String, dynamic>{
        'provider_id': providerId,
        'room_name': roomName,
        'display_name': displayName,
        'secret': secret,
        'fist_bumps_enabled': fistBumpsEnabled,
      },
    );
    return RoomSessionEnvelope.fromJson((response.data as Map<String, dynamic>?) ?? <String, dynamic>{});
  }

  Future<RoomSessionEnvelope> joinRoom({
    required Uri server,
    required String slug,
    required String displayName,
  }) async {
    final Response<dynamic> response = await _clientFor(server).post<dynamic>(
      '/rooms/$slug/join',
      data: <String, dynamic>{
        'display_name': displayName,
      },
    );
    return RoomSessionEnvelope.fromJson((response.data as Map<String, dynamic>?) ?? <String, dynamic>{});
  }

  Future<RoomSnapshot> getRoom({
    required Uri server,
    required String slug,
    required String sessionToken,
  }) async {
    final Response<dynamic> response = await _clientFor(server).get<dynamic>(
      '/rooms/$slug',
      options: Options(
        headers: <String, String>{
          'Authorization': 'Bearer $sessionToken',
        },
      ),
    );
    return RoomSnapshot.fromJson((response.data as Map<String, dynamic>?) ?? <String, dynamic>{});
  }

  Uri getRoomEventsUri({
    required Uri server,
    required String slug,
  }) {
    return apiBase(server).resolve('rooms/$slug/events');
  }
}
