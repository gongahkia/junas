import 'package:flutter/material.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app.dart';

final Provider<FlutterLocalNotificationsPlugin> localNotificationsProvider =
    Provider<FlutterLocalNotificationsPlugin>((Ref ref) {
  return FlutterLocalNotificationsPlugin();
});

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final FlutterLocalNotificationsPlugin notifications =
      await _createLocalNotificationsPlugin();

  runApp(
    ProviderScope(
      overrides: <Override>[
        localNotificationsProvider.overrideWithValue(notifications),
      ],
      child: const KilterTogetherApp(),
    ),
  );
}

Future<FlutterLocalNotificationsPlugin>
    _createLocalNotificationsPlugin() async {
  final FlutterLocalNotificationsPlugin notifications =
      FlutterLocalNotificationsPlugin();
  const AndroidInitializationSettings androidInitializationSettings =
      AndroidInitializationSettings('@mipmap/ic_launcher');
  const DarwinInitializationSettings iosInitializationSettings =
      DarwinInitializationSettings();
  const InitializationSettings settings = InitializationSettings(
    android: androidInitializationSettings,
    iOS: iosInitializationSettings,
  );

  await notifications.initialize(settings);
  return notifications;
}
