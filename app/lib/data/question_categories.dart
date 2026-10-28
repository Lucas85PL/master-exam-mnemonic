import 'package:sqflite/sqflite.dart';

import '../domain/category_filter.dart';

/// Wielokrotna przynależność pytania do działów (Master / Angielski / Pokład).
///
/// Tabela `question_categories(question_id, kategoria)` zawiera wszystkie działy pytania; kolumna `questions.kategoria`
/// pozostaje działem głównym (to on liczy się w rozdziale pul TESTU i w statystykach „wg działu”). Pytanie należy do puli
/// działu, jeśli ten dział jest jego głównym albo dodatkowym — patrz [QuestionCategories.matchSql].
class QuestionCategories {
  /// Wartości `kategoria` w kolejności wyświetlania (jak w ekranie głównym).
  static final order = [for (final c in StudyCategory.selectable) c.values.first];

  static String labelOf(String kategoria) {
    for (final c in StudyCategory.selectable) {
      if (c.values.first == kategoria) return c.label;
    }
    return kategoria;
  }

  /// Tworzy tabelę (idempotentnie) i uzupełnia ją dla pytań, które nie mają jeszcze żadnego wpisu: dział = dotychczasowa kategoria.
  static Future<void> createTable(DatabaseExecutor db) => db.execute(
        'CREATE TABLE IF NOT EXISTS question_categories (question_id INTEGER NOT NULL, kategoria TEXT NOT NULL, '
        'PRIMARY KEY (question_id, kategoria))',
      );

  static Future<void> ensure(DatabaseExecutor db) async {
    await createTable(db);
    await db.execute(
      'INSERT OR IGNORE INTO question_categories(question_id, kategoria) '
      'SELECT id, kategoria FROM questions WHERE kategoria IN (${order.map(_lit).join(',')}) '
      'AND id NOT IN (SELECT question_id FROM question_categories)',
    );
  }

  static String _lit(String v) => "'${v.replaceAll("'", "''")}'";

  /// Warunek SQL „pytanie należy do któregoś z [values]”; [idCol]/[katCol] to (zakwalifikowane) kolumny tabeli `questions`.
  /// Wartości są stałymi z [StudyCategory], więc wpisujemy je wprost (bez parametrów).
  static String matchSql(List<String> values, {String idCol = 'id', String katCol = 'kategoria'}) {
    final list = values.map(_lit).join(',');
    return '($katCol IN ($list) OR $idCol IN (SELECT question_id FROM question_categories WHERE kategoria IN ($list)))';
  }

  /// Działy pytania (główny jako pierwszy), uporządkowane jak [order].
  static Future<List<String>> of(DatabaseExecutor db, int id, String primary) async {
    final rows = await db.query('question_categories', columns: ['kategoria'], where: 'question_id = ?', whereArgs: [id]);
    final set = {primary, for (final r in rows) r['kategoria'] as String};
    return [for (final k in order) if (set.contains(k)) k];
  }

  /// Zapisuje komplet działów pytania. Dział główny zostaje, jeśli nadal jest wybrany; w przeciwnym razie pierwszy wybrany.
  static Future<void> set(DatabaseExecutor db, int id, String currentPrimary, Set<String> chosen) async {
    if (chosen.isEmpty) return;
    final primary = chosen.contains(currentPrimary) ? currentPrimary : order.firstWhere(chosen.contains);
    await db.delete('question_categories', where: 'question_id = ?', whereArgs: [id]);
    for (final k in chosen) {
      await db.insert('question_categories', {'question_id': id, 'kategoria': k});
    }
    if (primary != currentPrimary) {
      await db.update('questions', {'kategoria': primary}, where: 'id = ?', whereArgs: [id]);
    }
  }
}
