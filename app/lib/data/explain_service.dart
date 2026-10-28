import 'dart:convert';

import 'package:crypto/crypto.dart';
import 'package:sqflite/sqflite.dart';

import '../domain/explain_prompt.dart';
import '../domain/openrouter_models.dart';
import 'openrouter_client.dart';
import 'question_repository.dart';

class ExplainService {
  ExplainService(this._db, {OpenRouterClient? client})
      : _client = client ?? OpenRouterClient();

  final Database _db;
  final OpenRouterClient _client;

  static String contentHash(QuestionRow q) {
    final raw = [
      q.pytanie,
      q.odpA ?? '',
      q.odpB ?? '',
      q.odpC ?? '',
      q.odpD ?? '',
      q.poprawnaOdpowiedz,
      // Wersja promptu — zmiana unieważnia stare wyjaśnienia bez weryfikacji.
      explainPromptVersion,
    ].join('|');
    return sha256.convert(utf8.encode(raw)).toString();
  }

  /// Gotowe wyjaśnienie z pamięci podręcznej (bez klucza API i bez sieci); null, gdy go brak.
  Future<String?> cachedExplanation(QuestionRow question) =>
      _loadCache(question.id, contentHash(question));

  Future<String> explain({
    required String apiKey,
    required String modelId,
    required QuestionRow question,
    required String? userPicked,
    required bool userWasCorrect,
  }) async {
    final hash = contentHash(question);
    final cached = await _loadCache(question.id, hash);
    if (cached != null) return cached;

    final raw = await _client.chatCompletion(
      apiKey: apiKey,
      model: modelId,
      reasoningEffort: OpenRouterModels.byModelId(modelId).reasoningEffort,
      systemPrompt: buildExplainSystemPrompt(),
      userPrompt: buildExplainUserPrompt(
        question: question,
        userPicked: userPicked,
        userWasCorrect: userWasCorrect,
      ),
    );

    final text = formatExplanation(raw, question.poprawnaOdpowiedz);

    await _saveCache(
      questionId: question.id,
      hash: hash,
      explanation: text,
      model: modelId,
    );
    return text;
  }

  Future<String?> _loadCache(int questionId, String hash) async {
    final rows = await _db.query(
      'explanation_cache',
      where: 'question_id = ? AND content_hash = ?',
      whereArgs: [questionId, hash],
      limit: 1,
    );
    if (rows.isEmpty) return null;
    return rows.first['explanation'] as String?;
  }

  Future<void> _saveCache({
    required int questionId,
    required String hash,
    required String explanation,
    required String model,
  }) async {
    await _db.insert(
      'explanation_cache',
      {
        'question_id': questionId,
        'content_hash': hash,
        'explanation': explanation,
        'model': model,
        'created_at_ms': DateTime.now().millisecondsSinceEpoch,
      },
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }
}
