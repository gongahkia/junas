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
  final FlutterLocalNotificationsPlugin notifications = FlutterLocalNotificationsPlugin();
  const AndroidInitializationSettings android = AndroidInitializationSettings('@mipmap/ic_launcher');
  const DarwinInitializationSettings ios = DarwinInitializationSettings();
  const InitializationSettings settings = InitializationSettings(android: android, iOS: ios);
  await notifications.initialize(settings);
  runApp(ProviderScope(
    overrides: <Override>[
      localNotificationsProvider.overrideWithValue(notifications),
    ],
    child: const KilterTogetherApp(),
  ));
}
