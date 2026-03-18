import 'dart:io' show Platform;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'nearby_transport.dart';
import 'stub_transport.dart';
import 'p2p_transport.dart';

const String p2pServiceId = 'com.gongahkia.kilterTogether';

final Provider<P2pTransport> p2pTransportProvider = Provider<P2pTransport>((Ref ref) {
  if (Platform.isAndroid) {
    final NearbyTransport transport = NearbyTransport();
    ref.onDispose(() => transport.dispose());
    return transport;
  }
  // iOS / other — nearby_connections has no native implementation
  final StubTransport transport = StubTransport();
  ref.onDispose(() => transport.dispose());
  return transport;
});
