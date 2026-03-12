import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

class SseMessage {
  const SseMessage({
    required this.event,
    required this.data,
  });

  final String event;
  final String data;
}

class SseClient {
  SseClient({http.Client? client}) : _client = client ?? http.Client();

  final http.Client _client;

  Stream<SseMessage> connect({
    required Uri uri,
    required String sessionToken,
  }) async* {
    Duration retryDelay = const Duration(seconds: 1);

    while (true) {
      final http.Request request = http.Request('GET', uri);
      request.headers['Accept'] = 'text/event-stream';
      request.headers['Authorization'] = 'Bearer $sessionToken';

      http.StreamedResponse response;
      try {
        response = await _client.send(request);
      } catch (_) {
        await Future<void>.delayed(retryDelay);
        retryDelay = _nextDelay(retryDelay);
        continue;
      }

      if (response.statusCode != 200) {
        throw StateError('SSE connection failed with status ${response.statusCode}.');
      }

      retryDelay = const Duration(seconds: 1);
      String currentEvent = 'message';
      StringBuffer currentData = StringBuffer();

      try {
        await for (final String chunk in response.stream.transform(utf8.decoder).transform(const LineSplitter())) {
          if (chunk.isEmpty) {
            if (currentData.isNotEmpty) {
              yield SseMessage(
                event: currentEvent,
                data: currentData.toString().trim(),
              );
            }
            currentEvent = 'message';
            currentData = StringBuffer();
            continue;
          }

          if (chunk.startsWith('event:')) {
            currentEvent = chunk.substring(6).trim();
            continue;
          }

          if (chunk.startsWith('data:')) {
            currentData.writeln(chunk.substring(5).trim());
          }
        }
      } catch (_) {
        await Future<void>.delayed(retryDelay);
        retryDelay = _nextDelay(retryDelay);
        continue;
      }
    }
  }

  Duration _nextDelay(Duration current) {
    if (current.inSeconds >= 30) {
      return const Duration(seconds: 30);
    }
    return Duration(seconds: current.inSeconds * 2);
  }
}
