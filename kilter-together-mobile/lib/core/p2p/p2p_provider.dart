import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'nearby_transport.dart';
import 'p2p_transport.dart';

const String p2pServiceId = 'com.gongahkia.kilterTogether';

final Provider<P2pTransport> p2pTransportProvider = Provider<P2pTransport>((Ref ref) {
  final NearbyTransport transport = NearbyTransport();
  ref.onDispose(() => transport.dispose());
  return transport;
});
