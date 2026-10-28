import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/foundation.dart' show visibleForTesting;

import 'package:sqflite/sqflite.dart';
import 'package:sqlite3/sqlite3.dart' as s3;

import 'ai_disputed.dart';
import 'cmke_diff.dart';
import 'database.dart';
import 'db_info.dart';
import 'duplicate_groups.dart';
import 'question_categories.dart';

/// Tryby importu bazy z zewnątrz.
enum ImportMode {
  /// A — pełny import: obecna baza zostaje zastąpiona plikiem z zewnątrz.
  fullOverwrite('A', 'Pełny import z nadpisaniem',
      'Usuwa obecną bazę (postęp nauki, statusy, cache wyjaśnień) i zastępuje ją importowaną. '
          'Kopia obecnej bazy zostanie zapisana obok pliku bazy.'),

  /// B — tylko statusy OK/ERROR (oraz oznaczenie „Błąd”) pytań już obecnych.
  statusesOnly('B', 'Tylko statusy pytań (OK / ERROR)',
      'Aktualizuje wyłącznie statusy pytań, które już są w bazie. '
          'Nie dodaje pytań i nie rusza postępu nauki.'),

  /// C — dodanie pytań, których nie ma w obecnej bazie (wraz ze statusami).
  missingQuestions('C', 'Pytania nieobecne w obecnej bazie',
      'Dodaje tylko pytania, których nie ma w obecnej bazie (razem z ich statusami). '
          'Istniejące pytania i postęp nauki pozostają bez zmian.'),

  /// D — aktualizacja bazy z zachowaniem postępu nauki (pytania łączone po numerze ID).
  updateKeepProgress('D', 'Aktualizacja bazy (zachowaj postęp nauki)',
      'Dla bazy po poprawkach: dodaje nowe pytania, nadpisuje treść pytań, odpowiedzi i poprawny klucz pytań już obecnych '
          '(łączenie po numerze ID) oraz dołącza gotowe wyjaśnienia. Postęp nauki, historia odpowiedzi i Twoje oznaczenia „Błąd” '
          'zostają bez zmian. Pytań, których nie ma w pliku, nie usuwa.');

  const ImportMode(this.letter, this.title, this.description);
  final String letter;
  final String title;
  final String description;
}

class TransferResult {
  TransferResult({
    this.added = 0,
    this.updated = 0,
    this.unchanged = 0,
    this.notFound = 0,
    this.ambiguous = 0,
    this.skipped = 0,
    this.keyChanged = 0,
    this.notInSource = 0,
    this.backupPath,
  });

  final int added;
  final int updated;
  final int unchanged;
  final int notFound;
  final int ambiguous;
  final int skipped;

  /// Tryb D: ile pytań zmieniło poprawną odpowiedź oraz ile pytań z obecnej bazy nie ma w pliku.
  final int keyChanged;
  final int notInSource;
  final String? backupPath;
}

class ImportSourceException implements Exception {
  ImportSourceException(this.message);
  final String message;
  @override
  String toString() => message;
}

/// Eksport i import bazy aplikacji (pytania + statusy + postęp SM-2).
class DbTransferService {
  DbTransferService(this._db);

  final Database _db;

  // ---------------------------------------------------------------- eksport

  /// Spójna kopia pliku bazy (wszystkie tabele, w tym statusy i oznaczenia „Błąd”).
  Future<Uint8List> snapshotBytes() async {
    try {
      await _db.rawQuery('PRAGMA wal_checkpoint(TRUNCATE)');
    } catch (_) {}
    return File(_db.path).readAsBytes();
  }

  // ----------------------------------------------------------------- import

  /// Klucz treści pytania — odporny na różnice w interpunkcji/wielkości liter.
  static String contentKey({
    Object? poziom,
    Object? pytanie,
    Object? a,
    Object? b,
    Object? c,
    Object? d,
    Object? image,
  }) {
    String norm(Object? s) => (s?.toString() ?? '')
        .toLowerCase()
        .replaceAll(RegExp(r'[^\p{L}\p{N}]+', unicode: true), '');
    // pytania z obrazkiem (np. flagi) mają identyczną treść — rozróżnia je obrazek
    return [poziom, pytanie, a, b, c, d, image].map(norm).join('|');
  }

  /// Sprawdza, czy plik jest użyteczną bazą pytań; zwraca zestaw kolumn.
  static Set<String> inspectSource(String path) {
    if (!File(path).existsSync()) {
      throw ImportSourceException('Nie znaleziono pliku: $path');
    }
    s3.Database? src;
    try {
      src = s3.sqlite3.open(path, mode: s3.OpenMode.readOnly);
      final cols = src
          .select('PRAGMA table_info(questions)')
          .map((r) => r['name'] as String)
          .toSet();
      const required = {
        'id', 'pytanie', 'odp_a', 'odp_b', 'odp_c', 'odp_d', 'poprawna_odpowiedz',
      };
      if (cols.isEmpty || !cols.containsAll(required)) {
        throw ImportSourceException(
          'Wybrany plik nie jest bazą pytań (brak tabeli „questions” lub kolumn).',
        );
      }
      final n = src.select('SELECT COUNT(*) AS c FROM questions').first['c'] as int;
      if (n == 0) throw ImportSourceException('Importowana baza nie zawiera pytań.');
      return cols;
    } on s3.SqliteException catch (e) {
      throw ImportSourceException('Nie można otworzyć pliku jako bazy SQLite: ${e.message}');
    } finally {
      src?.dispose();
    }
  }

  /// A — pełny import. Zamyka obecną bazę, zapisuje kopię, podmienia plik i otwiera ponownie.
  static Future<TransferResult> fullOverwrite(String sourcePath) async {
    inspectSource(sourcePath);
    final appDb = await AppDatabase.open();
    final path = appDb.db.path;
    final stamp = DateTime.now().toIso8601String().replaceAll(RegExp(r'[^0-9]'), '').substring(0, 14);
    final backup = '$path.bak_before_import_$stamp';

    try {
      await appDb.db.rawQuery('PRAGMA wal_checkpoint(TRUNCATE)');
    } catch (_) {}
    await appDb.db.close();
    AppDatabase.resetInstance();
    await File(path).copy(backup);
    for (final suffix in ['-wal', '-shm', '-journal']) {
      final f = File('$path$suffix');
      if (await f.exists()) await f.delete();
    }

    try {
      await File(sourcePath).copy(path);
      normalizeFile(path);
    } catch (e) {
      // przywróć poprzednią bazę, jeśli coś poszło nie tak
      await File(backup).copy(path);
      await AppDatabase.open();
      rethrow;
    }
    await AppDatabase.open();
    return TransferResult(backupPath: backup);
  }

  /// Uzupełnia strukturę obcej bazy do schematu aplikacji (wersja 3; migracja do FSRS przy otwarciu).
  @visibleForTesting
  static void normalizeFile(String path) {
    final db = s3.sqlite3.open(path);
    try {
      final cols = db
          .select('PRAGMA table_info(questions)')
          .map((r) => r['name'] as String)
          .toSet();
      void addCol(String name, String ddl) {
        if (!cols.contains(name)) db.execute('ALTER TABLE questions ADD COLUMN $name $ddl');
      }

      addCol('podkategoria', 'TEXT');
      addCol('poziom', 'TEXT');
      addCol('nr_pytania', 'INTEGER');
      addCol('typ_pytania', "TEXT NOT NULL DEFAULT 'testowe'");
      addCol('poprawna_odpowiedz_tekst', 'TEXT');
      addCol('zrodlo_pliku', "TEXT NOT NULL DEFAULT ''");
      addCol('review_status', 'TEXT');
      addCol('review_notes', 'TEXT');
      addCol('study_hidden', 'INTEGER NOT NULL DEFAULT 0');
      addCol('ai_verified', 'TEXT');
      addCol('image_path', 'TEXT');

      db.execute('''
        CREATE TABLE IF NOT EXISTS import_meta (
          id INTEGER PRIMARY KEY CHECK (id = 1),
          source_path TEXT, imported_at_ms INTEGER,
          added_count INTEGER DEFAULT 0, updated_count INTEGER DEFAULT 0)
      ''');
      db.execute('''
        CREATE TABLE IF NOT EXISTS explanation_cache (
          question_id INTEGER NOT NULL, content_hash TEXT NOT NULL,
          explanation TEXT NOT NULL, model TEXT NOT NULL, created_at_ms INTEGER NOT NULL,
          PRIMARY KEY (question_id, content_hash))
      ''');

      final srsCols = db
          .select('PRAGMA table_info(srs_cards)')
          .map((r) => r['name'] as String)
          .toSet();
      if (srsCols.isNotEmpty && !srsCols.contains('repetitions')) {
        db.execute('DROP TABLE srs_cards'); // stary schemat z obcej bazy
      }
      db.execute('''
        CREATE TABLE IF NOT EXISTS srs_cards (
          question_id INTEGER PRIMARY KEY,
          repetitions INTEGER NOT NULL DEFAULT 0,
          interval_days INTEGER NOT NULL DEFAULT 0,
          ease_factor REAL NOT NULL DEFAULT 2.5,
          due_ms INTEGER NOT NULL,
          lapses INTEGER NOT NULL DEFAULT 0,
          state INTEGER NOT NULL DEFAULT 0,
          step INTEGER NOT NULL DEFAULT 0,
          stability REAL, difficulty REAL, last_review_ms INTEGER,
          FOREIGN KEY (question_id) REFERENCES questions(id))
      ''');
      db.execute(
        'INSERT INTO srs_cards (question_id, repetitions, interval_days, ease_factor, due_ms, lapses) '
        'SELECT id, 0, 0, 2.5, ${DateTime.now().millisecondsSinceEpoch}, 0 FROM questions '
        'WHERE id NOT IN (SELECT question_id FROM srs_cards)',
      );
      db.execute('CREATE INDEX IF NOT EXISTS idx_questions_kategoria ON questions(kategoria)');
      db.execute('CREATE INDEX IF NOT EXISTS idx_questions_review ON questions(review_status)');
      db.execute('CREATE INDEX IF NOT EXISTS idx_questions_hidden ON questions(study_hidden)');
      db.execute('CREATE INDEX IF NOT EXISTS idx_srs_due ON srs_cards(due_ms)');
      db.execute('CREATE INDEX IF NOT EXISTS idx_srs_repetitions ON srs_cards(repetitions)');
      // nie obniżaj wersji schematu (baza z nowszej aplikacji ma już kolumny FSRS)
      final uv = db.select('PRAGMA user_version').first.values.first as int;
      if (uv < 3) db.execute('PRAGMA user_version = 3');
    } finally {
      db.dispose();
    }
  }

  /// B — aktualizuje review_status (i „Błąd”) pytań już obecnych w bazie.
  Future<TransferResult> importStatuses(String sourcePath) async {
    final cols = inspectSource(sourcePath);
    final hasStatus = cols.contains('review_status');
    final hasHidden = cols.contains('study_hidden');
    if (!hasStatus && !hasHidden) {
      throw ImportSourceException('Importowana baza nie zawiera statusów pytań.');
    }

    final target = await _db.query('questions',
        columns: ['id', 'poziom', 'pytanie', 'odp_a', 'odp_b', 'odp_c', 'odp_d',
          'review_status', 'study_hidden', 'image_path']);
    final keyOf = <int, String>{};
    final byKey = <String, List<Map<String, Object?>>>{};
    for (final r in target) {
      final k = contentKey(
        poziom: r['poziom'], pytanie: r['pytanie'],
        a: r['odp_a'], b: r['odp_b'], c: r['odp_c'], d: r['odp_d'],
        image: r['image_path'],
      );
      keyOf[r['id'] as int] = k;
      byKey.putIfAbsent(k, () => []).add(r);
    }
    final byId = {for (final r in target) r['id'] as int: r};

    final src = s3.sqlite3.open(sourcePath, mode: s3.OpenMode.readOnly);
    var updated = 0, unchanged = 0, notFound = 0, ambiguous = 0;
    try {
      final rows = src.select('SELECT * FROM questions');
      await _db.transaction((txn) async {
        for (final row in rows) {
          final k = contentKey(
            poziom: cols.contains('poziom') ? row['poziom'] : null,
            pytanie: row['pytanie'], a: row['odp_a'], b: row['odp_b'],
            c: row['odp_c'], d: row['odp_d'],
            image: cols.contains('image_path') ? row['image_path'] : null,
          );
          Map<String, Object?>? t;
          final sid = row['id'] as int;
          if (byId.containsKey(sid) && keyOf[sid] == k) {
            t = byId[sid];
          } else {
            final cands = byKey[k];
            if (cands == null) {
              notFound++;
              continue;
            }
            if (cands.length > 1) {
              ambiguous++;
              continue;
            }
            t = cands.first;
          }

          final changes = <String, Object?>{};
          if (hasStatus) {
            final ns = row['review_status'];
            if (ns != t!['review_status']) changes['review_status'] = ns;
          }
          if (hasHidden) {
            final nh = (row['study_hidden'] as int?) ?? 0;
            if (nh != ((t!['study_hidden'] as int?) ?? 0)) changes['study_hidden'] = nh;
          }
          if (changes.isEmpty) {
            unchanged++;
            continue;
          }
          final tid = t!['id'] as int;
          await txn.update('questions', changes, where: 'id = ?', whereArgs: [tid]);
          if ((changes['review_status'] as String?)?.toLowerCase() == 'ok') {
            await _ensureSrs(txn, tid);
          }
          updated++;
        }
      });
    } finally {
      src.dispose();
    }
    return TransferResult(updated: updated, unchanged: unchanged, notFound: notFound, ambiguous: ambiguous);
  }

  /// C — dodaje pytania nieobecne w obecnej bazie (ze statusami).
  Future<TransferResult> importMissing(String sourcePath) async {
    final cols = inspectSource(sourcePath);
    final existing = await _db.query('questions',
        columns: ['poziom', 'pytanie', 'odp_a', 'odp_b', 'odp_c', 'odp_d', 'image_path']);
    final known = <String>{
      for (final r in existing)
        contentKey(
          poziom: r['poziom'], pytanie: r['pytanie'],
          a: r['odp_a'], b: r['odp_b'], c: r['odp_c'], d: r['odp_d'],
          image: r['image_path'],
        ),
    };

    final src = s3.sqlite3.open(sourcePath, mode: s3.OpenMode.readOnly);
    var added = 0, skipped = 0;
    try {
      final rows = src.select('SELECT * FROM questions ORDER BY id');
      await _db.transaction((txn) async {
        final maxId = Sqflite.firstIntValue(
              await txn.rawQuery('SELECT MAX(id) FROM questions'),
            ) ??
            0;
        var nextId = maxId + 1;
        String? col(s3.Row r, String name) => cols.contains(name) ? r[name] as String? : null;

        for (final row in rows) {
          final answer = ((row['poprawna_odpowiedz'] as String?) ?? '').trim().toUpperCase();
          final question = ((row['pytanie'] as String?) ?? '').trim();
          final kat = col(row, 'kategoria') ?? '';
          final src0 = col(row, 'zrodlo_pliku') ?? '';
          final typ = (col(row, 'typ_pytania') ?? 'testowe').trim().toLowerCase();
          if (question.isEmpty || !'ABCD'.contains(answer) || answer.isEmpty ||
              kat == 'Chief Officer' || src0.contains('colpkg') || typ != 'testowe') {
            skipped++;
            continue;
          }
          final k = contentKey(
            poziom: col(row, 'poziom'), pytanie: row['pytanie'],
            a: row['odp_a'], b: row['odp_b'], c: row['odp_c'], d: row['odp_d'],
            image: col(row, 'image_path'),
          );
          if (!known.add(k)) {
            skipped++; // już jest w bazie (lub duplikat w pliku)
            continue;
          }
          final id = nextId++;
          await txn.insert('questions', {
            'id': id,
            'kategoria': kat,
            'podkategoria': col(row, 'podkategoria'),
            'poziom': col(row, 'poziom'),
            'tematyka': col(row, 'tematyka') ?? '',
            'nr_pytania': cols.contains('nr_pytania') ? row['nr_pytania'] : null,
            'typ_pytania': 'testowe',
            'pytanie': row['pytanie'],
            'odp_a': row['odp_a'],
            'odp_b': row['odp_b'],
            'odp_c': row['odp_c'],
            'odp_d': row['odp_d'],
            'poprawna_odpowiedz': answer,
            'poprawna_odpowiedz_tekst': col(row, 'poprawna_odpowiedz_tekst'),
            'zrodlo_pliku': src0,
            'review_status': col(row, 'review_status'),
            'review_notes': col(row, 'review_notes'),
            'study_hidden': cols.contains('study_hidden') ? ((row['study_hidden'] as int?) ?? 0) : 0,
            'ai_verified': col(row, 'ai_verified'),
            'image_path': col(row, 'image_path'),
          });
          await _ensureSrs(txn, id);
          added++;
        }
      });
    } finally {
      src.dispose();
    }
    return TransferResult(added: added, skipped: skipped);
  }

  /// Kolumny pytania synchronizowane w trybie D (bez `study_hidden` — to oznaczenie użytkownika).
  static const _syncColumns = [
    'kategoria', 'podkategoria', 'poziom', 'tematyka', 'nr_pytania', 'typ_pytania', 'pytanie',
    'odp_a', 'odp_b', 'odp_c', 'odp_d', 'poprawna_odpowiedz', 'poprawna_odpowiedz_tekst',
    'zrodlo_pliku', 'review_status', 'review_notes', 'ai_verified', 'image_path',
  ];

  static bool _similarText(Object? a, Object? b) {
    String n(Object? s) => (s?.toString() ?? '').toLowerCase().replaceAll(RegExp(r'[^\p{L}\p{N}]+', unicode: true), '');
    final x = n(a), y = n(b);
    if (x == y) return true;
    if (x.length < 3 || y.length < 3) return false;
    Set<String> tri(String s) => {for (var i = 0; i + 3 <= s.length; i++) s.substring(i, i + 3)};
    final tx = tri(x), ty = tri(y);
    final inter = tx.intersection(ty).length;
    final union = tx.union(ty).length;
    return union > 0 && inter / union >= 0.4;
  }

  Future<bool> _hasTable(DatabaseExecutor db, String name) async =>
      (await db.rawQuery("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", [name])).isNotEmpty;

  /// D — aktualizacja bazy z zachowaniem postępu nauki: nowe pytania są dodawane (z ich ID), pytania obecne w bazie
  /// (to samo ID) dostają nową treść/klucz/status, `srs_cards`, `review_log` i `study_hidden` nie są ruszane.
  Future<TransferResult> updateKeepProgress(String sourcePath) async {
    final cols = inspectSource(sourcePath);
    final src = s3.sqlite3.open(sourcePath, mode: s3.OpenMode.readOnly);
    var added = 0, updated = 0, unchanged = 0, skipped = 0, keyChanged = 0;
    try {
      final rows = src.select('SELECT * FROM questions ORDER BY id');
      final targetRows = await _db.query('questions');
      final byId = {for (final r in targetRows) r['id'] as int: r};

      // zabezpieczenie: plik z inną numeracją ID (np. stara baza sprzed przenumerowania) nie może nadpisać cudzych pytań
      var overlap = 0, similar = 0;
      for (final row in rows) {
        final t = byId[row['id'] as int];
        if (t == null) continue;
        overlap++;
        if (_similarText(row['pytanie'], t['pytanie'])) similar++;
      }
      if (overlap >= 5 && similar < overlap * 0.8) {
        throw ImportSourceException(
          'Numeracja ID w pliku nie zgadza się z obecną bazą ($similar z $overlap wspólnych ID ma podobną treść). '
          'Użyj trybu C (dodanie brakujących pytań).',
        );
      }

      final targetCols = targetRows.isEmpty ? <String>{} : targetRows.first.keys.toSet();
      final syncCols = [for (final c in _syncColumns) if (cols.contains(c) && (targetCols.isEmpty || targetCols.contains(c))) c];
      String norm(Object? v) => (v?.toString() ?? '').trim();

      await _db.transaction((txn) async {
        for (final row in rows) {
          final id = row['id'] as int;
          final answer = norm(row['poprawna_odpowiedz']).toUpperCase();
          final question = norm(row['pytanie']);
          final typ = cols.contains('typ_pytania') ? norm(row['typ_pytania']).toLowerCase() : 'testowe';
          if (question.isEmpty || answer.isEmpty || !'ABCD'.contains(answer) || (typ.isNotEmpty && typ != 'testowe')) {
            skipped++;
            continue;
          }
          final t = byId[id];
          if (t == null) {
            final values = <String, Object?>{
              'id': id,
              'kategoria': cols.contains('kategoria') ? row['kategoria'] : '',
              'tematyka': cols.contains('tematyka') ? row['tematyka'] ?? '' : '',
              'typ_pytania': 'testowe',
              'zrodlo_pliku': cols.contains('zrodlo_pliku') ? row['zrodlo_pliku'] ?? '' : '',
              'study_hidden': cols.contains('study_hidden') ? ((row['study_hidden'] as int?) ?? 0) : 0,
            };
            for (final c in syncCols) {
              if (!values.containsKey(c)) values[c] = row[c];
            }
            values['poprawna_odpowiedz'] = answer;
            await txn.insert('questions', values);
            await _ensureSrs(txn, id);
            added++;
            continue;
          }
          final changes = <String, Object?>{};
          for (final c in syncCols) {
            var nv = row[c];
            if (c == 'poprawna_odpowiedz') nv = answer;
            if (norm(nv) != norm(t[c])) changes[c] = nv;
          }
          if (changes.isEmpty) {
            unchanged++;
            continue;
          }
          if (changes.containsKey('poprawna_odpowiedz')) keyChanged++;
          await txn.update('questions', changes, where: 'id = ?', whereArgs: [id]);
          if ((changes['review_status'] as String?)?.toLowerCase() == 'ok') await _ensureSrs(txn, id);
          updated++;
        }

        // gotowe wyjaśnienia AI z pliku (klucz: id + hash treści, więc zmienione pytania dostają nowe wpisy)
        final srcTables = src.select("SELECT name FROM sqlite_master WHERE type='table'").map((r) => r['name'] as String).toSet();
        if (srcTables.contains('explanation_cache') && await _hasTable(txn, 'explanation_cache')) {
          final ids = {for (final r in await txn.query('questions', columns: ['id'])) r['id'] as int};
          for (final r in src.select('SELECT * FROM explanation_cache')) {
            if (!ids.contains(r['question_id'] as int)) continue;
            await txn.insert(
              'explanation_cache',
              {
                'question_id': r['question_id'],
                'content_hash': r['content_hash'],
                'explanation': r['explanation'],
                'model': r['model'],
                'created_at_ms': r['created_at_ms'],
              },
              conflictAlgorithm: ConflictAlgorithm.replace,
            );
          }
        }
        // oznaczenia pytań z inną odpowiedzią niż w arkuszach CMKE (żółte tło) — jeśli plik je zawiera, zastępują obecne
        if (srcTables.contains('cmke_diff')) {
          await txn.execute('CREATE TABLE IF NOT EXISTS cmke_diff (question_id INTEGER PRIMARY KEY, cmke_letter TEXT NOT NULL)');
          await txn.delete('cmke_diff');
          for (final r in src.select('SELECT question_id, cmke_letter FROM cmke_diff')) {
            await txn.insert('cmke_diff', {'question_id': r['question_id'], 'cmke_letter': r['cmke_letter']},
                conflictAlgorithm: ConflictAlgorithm.replace);
          }
        }
        // tymczasowe oznaczenie pytań do weryfikacji (pomarańczowe tło) — jeśli plik je zawiera, zastępuje obecne
        if (srcTables.contains('ai_disputed')) {
          await txn.execute('CREATE TABLE IF NOT EXISTS ai_disputed (question_id INTEGER PRIMARY KEY)');
          await txn.delete('ai_disputed');
          for (final r in src.select('SELECT question_id FROM ai_disputed')) {
            await txn.insert('ai_disputed', {'question_id': r['question_id']}, conflictAlgorithm: ConflictAlgorithm.ignore);
          }
        }
        // wersja bazy pytań z pliku (np. 3.0)
        if (srcTables.contains('db_info')) {
          await DbInfo.createTable(txn);
          for (final r in src.select('SELECT key, value FROM db_info')) {
            await txn.insert('db_info', {'key': r['key'], 'value': r['value']}, conflictAlgorithm: ConflictAlgorithm.replace);
          }
        }
        // działy pytań (Master / Angielski / Pokład): jeśli plik je zawiera, jego wpisy zastępują obecne dla pytań z pliku
        if (srcTables.contains('question_categories')) {
          await QuestionCategories.ensure(txn);
          final fileIds = {for (final r in rows) r['id'] as int};
          final perId = <int, List<String>>{};
          for (final r in src.select('SELECT question_id, kategoria FROM question_categories')) {
            (perId[r['question_id'] as int] ??= []).add(r['kategoria'] as String);
          }
          for (final e in perId.entries) {
            if (!fileIds.contains(e.key)) continue;
            await txn.delete('question_categories', where: 'question_id = ?', whereArgs: [e.key]);
            for (final k in e.value) {
              await txn.insert('question_categories', {'question_id': e.key, 'kategoria': k}, conflictAlgorithm: ConflictAlgorithm.ignore);
            }
          }
        }
      });
    } finally {
      src.dispose();
    }
    // grupy powtórzeń (nowe/zmienione pytania) i oznaczenia do weryfikacji w pamięci
    try {
      await DuplicateGroups.refresh(_db);
      await DuplicateGroups.align(_db);
      await AiDisputed.load(_db);
      await CmkeDiff.load(_db);
      await QuestionCategories.ensure(_db); // nowe pytania dostają dział wg kategorii
      await DbInfo.load(_db);
    } catch (_) {}
    final notInSource = (await _db.query('questions', columns: ['id'])).length - added - updated - unchanged;
    return TransferResult(
      added: added, updated: updated, unchanged: unchanged, skipped: skipped,
      keyChanged: keyChanged, notInSource: notInSource < 0 ? 0 : notInSource,
    );
  }

  Future<TransferResult> run(ImportMode mode, String sourcePath) {
    switch (mode) {
      case ImportMode.fullOverwrite:
        return fullOverwrite(sourcePath);
      case ImportMode.statusesOnly:
        return importStatuses(sourcePath);
      case ImportMode.missingQuestions:
        return importMissing(sourcePath);
      case ImportMode.updateKeepProgress:
        return updateKeepProgress(sourcePath);
    }
  }

  Future<void> _ensureSrs(Transaction txn, int questionId) async {
    final exists = await txn.query('srs_cards',
        where: 'question_id = ?', whereArgs: [questionId], limit: 1);
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
}
