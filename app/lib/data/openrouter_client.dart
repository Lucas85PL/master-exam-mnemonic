import 'dart:convert';

import 'package:http/http.dart' as http;

class OpenRouterException implements Exception {
  OpenRouterException(this.message);
  final String message;
  @override
  String toString() => message;
}

class OpenRouterClient {
  OpenRouterClient({
    http.Client? httpClient,
    this.baseUrl = 'https://openrouter.ai/api/v1',
  }) : _http = httpClient ?? http.Client();

  final http.Client _http;
  final String baseUrl;

  Future<String> chatCompletion({
    required String apiKey,
    required String model,
    required String systemPrompt,
    required String userPrompt,
    int maxTokens = 600,
    String? reasoningEffort,
  }) async {
    final uri = Uri.parse('$baseUrl/chat/completions');
    final body = {
      'model': model,
      'temperature': 0.3,
      // Tokeny reasoning wliczają się do limitu — modele z reasoning dostają zapas.
      'max_tokens': reasoningEffort == null ? maxTokens : maxTokens + 6000,
      if (reasoningEffort != null) 'reasoning': {'effort': reasoningEffort},
      'messages': [
        {'role': 'system', 'content': systemPrompt},
        {'role': 'user', 'content': userPrompt},
      ],
    };

    final response = await _http
        .post(
          uri,
          headers: {
            'Authorization': 'Bearer $apiKey',
            'Content-Type': 'application/json',
            'HTTP-Referer': 'https://memonic-app.local',
            'X-Title': 'Master Exam Mnemonic',
          },
          body: jsonEncode(body),
        )
        .timeout(const Duration(seconds: 120));

    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw OpenRouterException(
        'OpenRouter ${response.statusCode}: ${response.body}',
      );
    }

    final decoded = jsonDecode(response.body) as Map<String, dynamic>;
    final choices = decoded['choices'] as List<dynamic>?;
    if (choices == null || choices.isEmpty) {
      throw OpenRouterException('Brak odpowiedzi modelu');
    }
    final message = choices.first['message'] as Map<String, dynamic>?;
    final content = (message?['content'] as String?)?.trim() ?? '';
    if (content.isEmpty) {
      throw OpenRouterException('Pusta odpowiedź modelu');
    }
    return _stripThinking(content);
  }

  String _stripThinking(String text) {
    var out = text;
    final redactedOpen = '<${'redacted_thinking'}>';
    final redactedClose = '</${'redacted_thinking'}>';
    final thinkOpen = '<${'think'}>';
    final thinkClose = '</${'think'}>';
    for (final pair in [
      (redactedOpen, redactedClose),
      (thinkOpen, thinkClose),
    ]) {
      out = _removeWrappedBlocks(out, pair.$1, pair.$2);
    }
    final legacyEnd = '</${'think'}>';
    final legacyIdx = out.indexOf(legacyEnd);
    if (legacyIdx >= 0) {
      out = out.substring(legacyIdx + legacyEnd.length).trim();
    }
    return out.trim();
  }

  String _removeWrappedBlocks(String text, String open, String close) {
    var out = text;
    while (true) {
      final start = out.indexOf(open);
      if (start < 0) break;
      final end = out.indexOf(close, start + open.length);
      if (end < 0) break;
      out = out.substring(0, start) + out.substring(end + close.length);
    }
    return out.trim();
  }

  void close() => _http.close();
}
