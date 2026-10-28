import 'dart:ui' show Color;

import 'package:sqflite/sqflite.dart';

/// Pytania, w których poprawna odpowiedź w bazie (rzeczywista, zweryfikowana) różni się od klucza w arkuszach CMKE (PDF Urzędu Morskiego).
/// Tabela `cmke_diff(question_id, cmke_letter)` — litera odpowiedzi z arkusza w układzie wariantów bazy; wypełniana poza aplikacją
/// i dołączana przy imporcie bazy (tryb D). Takie pytanie jest podświetlone na ciemny żółty z ostrzeżeniem nad treścią,
/// a po odpowiedzi przy wariancie z arkusza pojawia się pomarańczowa etykieta „Odp. wg. CMKE”.
class CmkeDiff {
  static Map<int, String> letters = {};

  /// Ciemny żółty (tło treści pytania) i ostrzeżenie nad pytaniem.
  static const background = Color(0xFFE6B800);
  static const banner = 'UWAGA: Odp rzeczywista (prawdziwa) ≠ odpowiedź na arkuszach CMKE';

  /// Pomarańczowa etykieta przy odpowiedzi z arkusza.
  static const tag = 'Odp. wg. CMKE';
  static const tagColor = Color(0xFFE65100);

  /// Tworzy tabelę (idempotentnie) i wczytuje oznaczenia do pamięci.
  static Future<void> load(Database db) async {
    await db.execute('CREATE TABLE IF NOT EXISTS cmke_diff (question_id INTEGER PRIMARY KEY, cmke_letter TEXT NOT NULL)');
    final rows = await db.rawQuery('SELECT question_id, cmke_letter FROM cmke_diff');
    letters = {for (final r in rows) r['question_id'] as int: (r['cmke_letter'] as String).toUpperCase()};
  }
}
