import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path_provider/path_provider.dart';

final Provider<CatalogStoragePlatform> catalogStoragePlatformProvider =
    Provider<CatalogStoragePlatform>((Ref ref) {
  return const CatalogStoragePlatform();
});

class CatalogStoragePlatform {
  const CatalogStoragePlatform({
    MethodChannel? channel,
  }) : _channel =
            channel ?? const MethodChannel('kilter_together/catalog_storage');

  final MethodChannel _channel;

  Future<Directory> appSupportDirectory() {
    return getApplicationSupportDirectory();
  }

  Future<void> excludeFromBackup(String path) async {
    if (kIsWeb || !Platform.isIOS) {
      return;
    }
    try {
      await _channel.invokeMethod<void>('excludeFromBackup', <String, String>{
        'path': path,
      });
    } on PlatformException {
      return;
    }
  }

  Future<int?> availableBytesAt(String path) async {
    if (kIsWeb || !(Platform.isIOS || Platform.isAndroid)) {
      return null;
    }
    try {
      return await _channel.invokeMethod<int>(
        'availableBytes',
        <String, String>{'path': path},
      );
    } on PlatformException {
      return null;
    }
  }
}
