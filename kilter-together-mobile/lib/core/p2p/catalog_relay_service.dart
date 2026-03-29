import 'dart:async';
import 'dart:developer' as developer;
import '../models/provider_models.dart';
import '../models/product_models.dart';
import '../models/room_models.dart';
import '../models/board_models.dart';
import '../models/catalog_models.dart';
import '../network/api_client.dart';
import '../storage/session_repository.dart';
import '../storage/offline_kilter_catalog_repository.dart';
import 'p2p_message_types.dart';
import 'p2p_transport.dart';

class CatalogRelayService {
  CatalogRelayService({
    required this.transport,
    required this.catalogRepository,
    required this.apiClient,
    required this.sessionRepository,
  });
  final P2pTransport transport;
  final OfflineKilterCatalogRepository catalogRepository;
  final ApiClient apiClient;
  final SessionRepository sessionRepository;
  StreamSubscription<P2pMessage>? _sub;

  void start() {
    _sub = transport.messages.listen(_handleMessage);
  }

  void dispose() {
    _sub?.cancel();
  }

  Future<void> _handleMessage(P2pMessage message) async {
    if (message.type != P2pMessageType.catalogQuery) return;
    final String? senderId = message.senderId;
    if (senderId == null) return;
    final String providerId = message.payload['provider_id'] as String? ?? '';
    final String surfaceId = message.payload['surface_id'] as String? ?? '';
    final Map<String, dynamic> rawContext =
        (message.payload['context'] as Map<String, dynamic>?) ??
            <String, dynamic>{};
    final Map<String, String> context =
        rawContext.map((String key, dynamic value) => MapEntry(key, '$value'));
    final int angle = int.tryParse(context['angle'] ?? '') ?? 40;
    final int page = (message.payload['page'] as num?)?.toInt() ?? 1;
    final int pageSize = (message.payload['page_size'] as num?)?.toInt() ?? 10;
    final String? q = message.payload['q'] as String?;
    final String? sort = message.payload['sort'] as String?;
    final String? gradeMin = message.payload['grade_min'] as String?;
    final String? gradeMax = message.payload['grade_max'] as String?;
    try {
      late final RoomCatalogClimbsResponse result;
      if (providerId == 'kilter') {
        final PaginatedBoardClimbsResponse catalogResult =
            await catalogRepository
                .queryClimbs(
                  OfflineCatalogQuery(
                    boardId: surfaceId,
                    angle: angle,
                    page: page,
                    pageSize: pageSize,
                    name: q,
                    sort: sort,
                    gradeMin: gradeMin,
                    gradeMax: gradeMax,
                  ),
                )
                .timeout(const Duration(seconds: 10));
        result = RoomCatalogClimbsResponse(
          climbs: catalogResult.climbs
              .map((BoardClimb climb) => ProviderClimb(
                    id: 'kilter:${climb.productSizeId}:${climb.uuid}',
                    externalId: climb.uuid,
                    providerId: 'kilter',
                    surfaceId: surfaceId,
                    name: climb.climbName,
                    description: climb.description,
                    setterName: climb.setterName,
                    primaryGrade: climb.gradeForAngle(angle),
                    createdAt: climb.createdAt,
                    popularity: climb.ascends,
                    highlightedHolds: climb.highlightedHolds,
                    meta: <String, String>{
                      'board_id': surfaceId,
                      'angle': '$angle',
                    },
                  ))
              .toList(growable: false),
          hasMore: catalogResult.hasMore,
          pageSize: catalogResult.pageSize,
          voteCounts: const <String, int>{},
          myVotes: const <String>[],
        );
      } else {
        final Uri? server = await sessionRepository.loadActiveServer();
        if (server == null) {
          throw StateError('No active server configured for provider relay.');
        }
        final ProviderCatalogClimbsResponse providerResult =
            await apiClient.getSoloProviderClimbs(
          server: server,
          providerId: providerId,
          secret: const <String, String>{},
          surfaceId: surfaceId.isEmpty ? null : surfaceId,
          context: context,
          q: q,
          sort: sort,
          gradeMin: gradeMin,
          gradeMax: gradeMax,
          pageSize: pageSize,
        );
        result = RoomCatalogClimbsResponse(
          climbs: providerResult.climbs
              .map(
                (ProviderClimb climb) => ProviderClimb(
                  id: climb.id,
                  externalId: climb.externalId,
                  providerId: climb.providerId,
                  surfaceId: climb.surfaceId,
                  name: climb.name,
                  description: climb.description,
                  setterName: climb.setterName,
                  primaryGrade: climb.primaryGrade,
                  secondaryGrade: climb.secondaryGrade,
                  createdAt: climb.createdAt,
                  popularity: climb.popularity,
                  media: climb.media
                      .map(
                        (ProviderClimbMedia item) => ProviderClimbMedia(
                          url: apiClient.resolveMediaUrl(
                            server: server,
                            url: item.url,
                          ),
                          kind: item.kind,
                        ),
                      )
                      .toList(growable: false),
                  highlightedHolds: climb.highlightedHolds,
                  meta: climb.meta,
                ),
              )
              .toList(growable: false),
          hasMore: providerResult.hasMore,
          pageSize: providerResult.pageSize,
          voteCounts: const <String, int>{},
          myVotes: const <String>[],
          nextCursor: providerResult.nextCursor,
        );
      }
      unawaited(transport.send(
          senderId,
          P2pMessage(
            type: P2pMessageType.catalogResponse,
            payload: <String, dynamic>{
              'climbs': result.climbs
                  .map((ProviderClimb c) => c.toJson())
                  .toList(growable: false),
              'has_more': result.hasMore,
              'page_size': result.pageSize,
              'vote_counts': result.voteCounts,
              'my_votes': result.myVotes,
              'next_cursor': result.nextCursor,
            },
          )));
    } catch (e) {
      developer.log('Catalog relay query failed: $e', name: 'CatalogRelay');
      unawaited(transport.send(
          senderId,
          P2pMessage(
            type: P2pMessageType.catalogResponse,
            payload: <String, dynamic>{
              'climbs': <dynamic>[],
              'has_more': false,
              'page_size': pageSize,
              'error': '$e',
            },
          )));
    }
  }
}
