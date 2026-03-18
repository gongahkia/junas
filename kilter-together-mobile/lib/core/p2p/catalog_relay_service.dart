import 'dart:async';
import 'dart:developer' as developer;
import '../models/board_models.dart';
import '../models/catalog_models.dart';
import '../storage/offline_kilter_catalog_repository.dart';
import 'p2p_message_types.dart';
import 'p2p_transport.dart';

class CatalogRelayService {
  CatalogRelayService({
    required this.transport,
    required this.catalogRepository,
  });
  final P2pTransport transport;
  final OfflineKilterCatalogRepository catalogRepository;
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
    final String boardId = message.payload['board_id'] as String? ?? '';
    final int angle = (message.payload['angle'] as num?)?.toInt() ?? 40;
    final int page = (message.payload['page'] as num?)?.toInt() ?? 1;
    final int pageSize = (message.payload['page_size'] as num?)?.toInt() ?? 10;
    final String? q = message.payload['q'] as String?;
    final String? sort = message.payload['sort'] as String?;
    final String? gradeMin = message.payload['grade_min'] as String?;
    final String? gradeMax = message.payload['grade_max'] as String?;
    try {
      final PaginatedBoardClimbsResponse result = await catalogRepository.queryClimbs(
        OfflineCatalogQuery(
          boardId: boardId,
          angle: angle,
          page: page,
          pageSize: pageSize,
          name: q,
          sort: sort,
          gradeMin: gradeMin,
          gradeMax: gradeMax,
        ),
      );
      unawaited(transport.send(senderId, P2pMessage(
        type: P2pMessageType.catalogResponse,
        payload: <String, dynamic>{
          'climbs': result.climbs.map((BoardClimb c) => c.toJson()).toList(growable: false),
          'has_more': result.hasMore,
          'page_size': result.pageSize,
        },
      )));
    } catch (e) {
      developer.log('Catalog relay query failed: $e', name: 'CatalogRelay');
      unawaited(transport.send(senderId, P2pMessage(
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
