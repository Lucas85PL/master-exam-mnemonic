import 'package:sqflite/sqflite.dart';

/// Wersja zawartości bazy pytań (np. „3.0”) — tabela `db_info(key, value)`, niezależna od schematu SQLite.
/// Ustawiana poza aplikacją (skrypt wydania) i przenoszona razem z bazą przy imporcie; baza bez wpisu pokazuje „—”.
class DbInfo {
  static String? version;

  static Future<void> createTable(DatabaseExecutor db) =>
      db.execute('CREATE TABLE IF NOT EXISTS db_info (key TEXT PRIMARY KEY, value TEXT)');

  /// Tworzy tabelę (idempotentnie) i wczytuje wersję bazy do pamięci.
  static Future<void> load(DatabaseExecutor db) async {
    await createTable(db);
    final rows = await db.query('db_info', where: 'key = ?', whereArgs: ['db_version'], limit: 1);
    version = rows.isEmpty ? null : rows.first['value'] as String?;
  }
}
