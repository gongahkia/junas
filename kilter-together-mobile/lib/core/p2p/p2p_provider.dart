import 'dart:io' show Platform;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'multipeer_transport.dart';
import 'nearby_transport.dart';
import 'stub_transport.dart';
import 'p2p_transport.dart';

const String p2pServiceId = 'com.gongahkia.kilterTogether';

final Provider<P2pTransport> p2pTransportProvider = Provider<P2pTransport>((Ref ref) {
  final P2pTransport transport;
  if (Platform.isAndroid) {
    transport = NearbyTransport();
  } else if (Platform.isIOS) {
    transport = MultipeerTransport();
  } else {
    transport = StubTransport(); // desktop/web fallback
  }
  ref.onDispose(() => transport.dispose());
  return transport;
});
