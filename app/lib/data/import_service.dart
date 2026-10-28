import 'package:sqlite3/sqlite3.dart' as sqlite3;
import 'package:sqflite/sqflite.dart';

class ImportResult {
  ImportResult({
    required this.added,
    required this.updated,
    required this.skipped,
  });

  final int added;
  final int updated;
  final int skipped;
}

class ImportService {
  ImportService(this._db);

  final Database _db;

  static const _selectSql = '''
    SELECT id, kategoria, podkategoria, poziom, tematyka, nr_pytania,
           typ_pytania, pytanie, odp_a, odp_b, odp_c, odp_d,
           poprawna_odpowiedz, poprawna_odpowiedz_tekst, zrodlo_pliku,
           review_status, review_notes
    FROM questions
    WHERE kategoria != 'Chief Officer'
      AND (zrodlo_pliku IS NULL OR zrodlo_pliku NOT LIKE '%colpkg%')
      AND lower(trim(coalesce(typ_pytania, 'testowe'))) = 'testowe'
      AND upper(trim(coalesce(poprawna_odpowiedz, ''))) IN ('A','B','C','D')
      AND trim(coalesce(pytanie, '')) != ''
  ''';

  Future<ImportResult> importFromFile(String sourcePath) async {
    final source = sqlite3.sqlite3.open(sourcePath, mode: sqlite3.OpenMode.readOnly);
    try {
      final rows = source.select(_selectSql);
      var added = 0;
      var updated = 0;
      var skipped = 0;

      await _db.transaction((txn) async {
        for (final row in rows) {
          final id = row['id'] as int;
          final existing = await txn.query(
            'questions',
            columns: ['id'],
            where: 'id = ?',
            whereArgs: [id],
            limit: 1,
          );

          final map = _rowToMap(row);
          if (existing.isEmpty) {
            await txn.insert('questions', map);
            if (_isStudyEligible(map)) {
              await _ensureSrs(txn, id);
            }
            added++;
          } else {
            map.remove('study_hidden');
            await txn.update(
              'questions',
              map,
              where: 'id = ?',
              whereArgs: [id],
            );
            if (_isStudyEligible(map)) {
              await _ensureSrs(txn, id);
            }
            updated++;
          }
        }

        await txn.delete('import_meta');
        await txn.insert('import_meta', {
          'id': 1,
          'source_path': sourcePath,
          'imported_at_ms': DateTime.now().millisecondsSinceEpoch,
          'added_count': added,
          'updated_count': updated,
        });
      });

      return ImportResult(added: added, updated: updated, skipped: skipped);
    } finally {
      source.dispose();
    }
  }

  bool _isStudyEligible(Map<String, Object?> map) {
    final status = (map['review_status'] as String? ?? '').trim().toLowerCase();
    return status == 'ok';
  }

  Future<void> _ensureSrs(Transaction txn, int questionId) async {
    final exists = await txn.query(
      'srs_cards',
      where: 'question_id = ?',
      whereArgs: [questionId],
      limit: 1,
    );
    if (exists.isNotEmpty) return;
    await txn.insert('srs_cards', {
      'question_id': questionId,
      'repetitions': 0,
      'interval_days': 0,
      'ease_factor': 2.5,
      'due_ms': DateTime.now().millisecondsSinceEpoch,
      'lapses': 0,
    });
  }

  Map<String, Object?> _rowToMap(sqlite3.Row row) {
    return {
      'id': row['id'],
      'kategoria': row['kategoria'],
      'podkategoria': row['podkategoria'],
      'poziom': row['poziom'],
      'tematyka': row['tematyka'] ?? '',
      'nr_pytania': row['nr_pytania'],
      'typ_pytania': row['typ_pytania'] ?? 'testowe',
      'pytanie': row['pytanie'] ?? '',
      'odp_a': row['odp_a'],
      'odp_b': row['odp_b'],
      'odp_c': row['odp_c'],
      'odp_d': row['odp_d'],
      'poprawna_odpowiedz': row['poprawna_odpowiedz'],
      'poprawna_odpowiedz_tekst': row['poprawna_odpowiedz_tekst'],
      'zrodlo_pliku': row['zrodlo_pliku'] ?? '',
      'review_status': row['review_status'],
      'review_notes': row['review_notes'],
      'study_hidden': 0,
    };
  }
}
