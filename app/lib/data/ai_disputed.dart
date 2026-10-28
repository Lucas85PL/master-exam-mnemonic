import 'dart:ui' show Color;

import 'package:sqflite/sqflite.dart';

/// TYMCZASOWE oznaczenie pytań, dla których trzech agentów AI nie zgodziło się z kluczem w bazie
/// (tabela `ai_disputed`, wypełniana poza aplikacją). Treść takiego pytania jest pokazywana na pastelowo-pomarańczowym
/// tle do czasu ręcznej weryfikacji. Po weryfikacji wystarczy opróżnić tabelę (`DELETE FROM ai_disputed`).
class AiDisputed {
  static Set<int> ids = {};

  /// Tło treści pytania (pastelowy pomarańcz).
  static const background = Color(0xFFFFD8A8);

  /// Tworzy tabelę (idempotentnie) i wczytuje identyfikatory do pamięci.
  static Future<void> load(Database db) async {
    await db.execute('CREATE TABLE IF NOT EXISTS ai_disputed (question_id INTEGER PRIMARY KEY)');
    final rows = await db.rawQuery('SELECT question_id FROM ai_disputed');
    ids = {for (final r in rows) r['question_id'] as int};
  }
}
