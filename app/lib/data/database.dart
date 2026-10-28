import 'dart:io';

import 'package:path/path.dart' as p;
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

import '../domain/fsrs.dart';
import 'app_paths.dart';
import 'ai_disputed.dart';
import 'cmke_diff.dart';
import 'db_info.dart';
import 'duplicate_groups.dart';
import 'question_categories.dart';
import 'seed_database.dart';

class AppDatabase {
  AppDatabase._(this.db);

  final Database db;
  static AppDatabase? _instance;

  static const _explanationCacheSql = '''
    CREATE TABLE explanation_cache (
      question_id INTEGER NOT NULL,
      content_hash TEXT NOT NULL,
      explanation TEXT NOT NULL,
      model TEXT NOT NULL,
      created_at_ms INTEGER NOT NULL,
      PRIMARY KEY (question_id, content_hash)
    )
  ''';

  static const _srsV2Sql = '''
    CREATE TABLE srs_cards (
      question_id INTEGER PRIMARY KEY,
      repetitions INTEGER NOT NULL DEFAULT 0,
      interval_days INTEGER NOT NULL DEFAULT 0,
      ease_factor REAL NOT NULL DEFAULT 2.5,
      due_ms INTEGER NOT NULL,
      lapses INTEGER NOT NULL DEFAULT 0,
      state INTEGER NOT NULL DEFAULT 0,
      step INTEGER NOT NULL DEFAULT 0,
      stability REAL,
      difficulty REAL,
      last_review_ms INTEGER,
      FOREIGN KEY (question_id) REFERENCES questions(id)
    )
  ''';

  static Future<AppDatabase> open() async {
    if (_instance != null) return _instance!;
    if (Platform.isWindows || Platform.isLinux) {
      sqfliteFfiInit();
      databaseFactory = databaseFactoryFfi;
    }
    final dir = await AppPaths.dataDir();
    final path = p.join(dir.path, 'memonic_app.db');
    await SeedDatabase.ensureInstalled(path);
    final database = await openDatabase(
      path,
      version: 8,
      onCreate: (db, version) async {
        await _createV1Tables(db);
        if (version >= 2) {
          await db.execute(_srsV2Sql);
        }
        if (version >= 3) {
          await db.execute(_explanationCacheSql);
        }
        await migrateStudyStats(db);
        await _createIndexes(db);
      },
      onUpgrade: (db, oldVersion, newVersion) async {
        if (oldVersion < 2) {
          await _migrateSrsToV2(db);
        }
        if (oldVersion < 3) {
          await _migrateExplanationCache(db);
        }
        if (oldVersion < 4) {
          await migrateSrsToFsrs(db);
        }
        if (oldVersion < 5) {
          await migrateImagePath(db);
        }
        if (oldVersion < 6) {
          await migrateStudyStats(db);
        }
        if (oldVersion < 7) {
          await migrateStudyStats(db); // idempotentnie: dodaje streak_before/streak_after do review_log
        }
        if (oldVersion < 8) {
          await DuplicateGroups.ensureColumn(db); // v8: grupy powtórzonych pytań (dup_group)
        }
      },
    );
    // grupy powtórzonych pytań: przeliczenie (po imporcie/edycji/nowych pytaniach) i ujednolicenie postępu kopii
    await DuplicateGroups.refresh(database);
    await DuplicateGroups.align(database);
    await AiDisputed.load(database); // tymczasowe oznaczenie pytań bez konsensusu AI
    await CmkeDiff.load(database); // pytania z inną odpowiedzią niż w arkuszach CMKE
    await DbInfo.load(database); // wersja zawartości bazy (np. 3.0)
    await QuestionCategories.ensure(database); // działy pytań (wielokrotna przynależność); uzupełnia wg dotychczasowej kategorii
    _instance = AppDatabase._(database);
    return _instance!;
  }

  static Future<void> _createV1Tables(Database db) async {
    await db.execute('''
      CREATE TABLE questions (
        id INTEGER PRIMARY KEY,
        kategoria TEXT NOT NULL,
        podkategoria TEXT,
        poziom TEXT,
        tematyka TEXT NOT NULL,
        nr_pytania INTEGER,
        typ_pytania TEXT NOT NULL DEFAULT 'testowe',
        pytanie TEXT NOT NULL,
        odp_a TEXT,
        odp_b TEXT,
        odp_c TEXT,
        odp_d TEXT,
        poprawna_odpowiedz TEXT,
        poprawna_odpowiedz_tekst TEXT,
        zrodlo_pliku TEXT NOT NULL,
        review_status TEXT,
        review_notes TEXT,
        study_hidden INTEGER NOT NULL DEFAULT 0,
        image_path TEXT
      )
    ''');
    await db.execute('''
      CREATE TABLE import_meta (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        source_path TEXT,
        imported_at_ms INTEGER,
        added_count INTEGER DEFAULT 0,
        updated_count INTEGER DEFAULT 0
      )
    ''');
  }

  static Future<void> _createIndexes(Database db) async {
    await db.execute(
      'CREATE INDEX IF NOT EXISTS idx_questions_kategoria ON questions(kategoria)',
    );
    await db.execute(
      'CREATE INDEX IF NOT EXISTS idx_questions_review ON questions(review_status)',
    );
    await db.execute(
      'CREATE INDEX IF NOT EXISTS idx_questions_hidden ON questions(study_hidden)',
    );
    await db.execute(
      'CREATE INDEX IF NOT EXISTS idx_srs_due ON srs_cards(due_ms)',
    );
    await db.execute(
      'CREATE INDEX IF NOT EXISTS idx_srs_repetitions ON srs_cards(repetitions)',
    );
    final srsCols = (await db.rawQuery('PRAGMA table_info(srs_cards)'))
        .map((c) => c['name'] as String)
        .toSet();
    if (srsCols.contains('state')) {
      await db.execute(
        'CREATE INDEX IF NOT EXISTS idx_srs_state ON srs_cards(state, due_ms)',
      );
    }
  }

  static Future<void> _migrateSrsToV2(Database db) async {
    final oldExists = await db.rawQuery(
      "SELECT name FROM sqlite_master WHERE type='table' AND name='srs_cards'",
    );
    if (oldExists.isEmpty) {
      await db.execute(_srsV2Sql);
      return;
    }

    final columns = await db.rawQuery('PRAGMA table_info(srs_cards)');
    final names = columns.map((c) => c['name'] as String).toSet();
    if (names.contains('repetitions') && !names.contains('state')) {
      return;
    }

    await db.execute('ALTER TABLE srs_cards RENAME TO srs_cards_old');
    await db.execute(_srsV2Sql);

    final rows = await db.query('srs_cards_old');
    for (final r in rows) {
      final state = r['state'] as String? ?? 'new';
      final reps = r['reps'] as int? ?? 0;
      final interval = r['interval_days'] as int? ?? 0;
      final ease = (r['ease'] as num?)?.toDouble() ?? 2.5;
      final dueMs = r['due_ms'] as int? ?? DateTime.now().millisecondsSinceEpoch;
      final lapses = r['lapses'] as int? ?? 0;

      int repetitions;
      int intervalDays;
      if (state == 'new') {
        repetitions = 0;
        intervalDays = 0;
      } else if (state == 'learning' || state == 'relearning') {
        repetitions = reps > 0 ? reps : 1;
        intervalDays = interval > 0 ? interval : 1;
      } else {
        repetitions = reps > 0 ? reps : 1;
        intervalDays = interval > 0 ? interval : 1;
      }

      await db.insert('srs_cards', {
        'question_id': r['question_id'],
        'repetitions': repetitions,
        'interval_days': intervalDays,
        'ease_factor': ease,
        'due_ms': dueMs,
        'lapses': lapses,
      });
    }
    await db.execute('DROP TABLE srs_cards_old');
  }

  /// Dodaje kolumny FSRS do `srs_cards` i przenosi postęp z SM-2 (idempotentnie).
  static Future<void> migrateSrsToFsrs(Database db) async {
    final cols = (await db.rawQuery('PRAGMA table_info(srs_cards)'))
        .map((c) => c['name'] as String)
        .toSet();
    const adds = {
      'state': 'INTEGER NOT NULL DEFAULT 0',
      'step': 'INTEGER NOT NULL DEFAULT 0',
      'stability': 'REAL',
      'difficulty': 'REAL',
      'last_review_ms': 'INTEGER',
    };
    for (final e in adds.entries) {
      if (!cols.contains(e.key)) {
        await db.execute('ALTER TABLE srs_cards ADD COLUMN ${e.key} ${e.value}');
      }
    }
    final rows = await db.query(
      'srs_cards',
      where: 'stability IS NULL AND (repetitions > 0 OR interval_days > 0)',
    );
    final batch = db.batch();
    for (final r in rows) {
      final fields = Sm2Migration.convert(
        repetitions: r['repetitions'] as int? ?? 0,
        intervalDays: r['interval_days'] as int? ?? 0,
        easeFactor: (r['ease_factor'] as num?)?.toDouble() ?? 2.5,
        dueMs: r['due_ms'] as int? ?? DateTime.now().millisecondsSinceEpoch,
        lapses: r['lapses'] as int? ?? 0,
      );
      batch.update('srs_cards', fields, where: 'question_id = ?', whereArgs: [r['question_id']]);
    }
    await batch.commit(noResult: true);
    await db.execute('CREATE INDEX IF NOT EXISTS idx_srs_state ON srs_cards(state, due_ms)');
  }

  /// v5: kolumna `image_path` (nazwa pliku w assets/question_images) — idempotentnie.
  static Future<void> migrateImagePath(Database db) async {
    final cols = (await db.rawQuery('PRAGMA table_info(questions)'))
        .map((c) => c['name'] as String)
        .toSet();
    if (!cols.contains('image_path')) {
      await db.execute('ALTER TABLE questions ADD COLUMN image_path TEXT');
    }
  }

  /// v6: dziennik odpowiedzi (`review_log`), seria dni (`streak_days`, `last_good_day`) i flaga „trudne” (`hard`).
  /// Idempotentnie. Seria istniejących kart jest szacowana z dotychczasowych powtórek (jednorazowo).
  static Future<void> migrateStudyStats(Database db) async {
    await QuestionCategories.createTable(db); // tabela działów pytań (filtry puli odwołują się do niej)
    await db.execute('''
      CREATE TABLE IF NOT EXISTS review_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        question_id INTEGER NOT NULL,
        ts_ms INTEGER NOT NULL,
        day INTEGER NOT NULL,
        correct INTEGER NOT NULL,
        rating INTEGER NOT NULL,
        seconds INTEGER,
        streak_before INTEGER,
        streak_after INTEGER
      )
    ''');
    // v7: seria przed/po odpowiedzi (do wyliczania tempa nauki); dla starszych tabel dodajemy kolumny
    final logCols = (await db.rawQuery('PRAGMA table_info(review_log)')).map((c) => c['name'] as String).toSet();
    for (final c in const ['streak_before', 'streak_after']) {
      if (!logCols.contains(c)) await db.execute('ALTER TABLE review_log ADD COLUMN $c INTEGER');
    }
    await db.execute('CREATE INDEX IF NOT EXISTS idx_review_log_q ON review_log(question_id, id)');
    await db.execute('CREATE INDEX IF NOT EXISTS idx_review_log_day ON review_log(day)');
    final cols = (await db.rawQuery('PRAGMA table_info(srs_cards)'))
        .map((c) => c['name'] as String)
        .toSet();
    final fresh = !cols.contains('streak_days');
    const adds = {
      'streak_days': 'INTEGER NOT NULL DEFAULT 0',
      'last_good_day': 'INTEGER',
      'hard': 'INTEGER NOT NULL DEFAULT 0',
    };
    for (final e in adds.entries) {
      if (!cols.contains(e.key)) {
        await db.execute('ALTER TABLE srs_cards ADD COLUMN ${e.key} ${e.value}');
      }
    }
    if (fresh && cols.contains('state')) {
      // szacunek startowy: karta w powtórkach ma serię min(3, powtórzenia − błędy)
      await db.execute('''
        UPDATE srs_cards
        SET streak_days = MIN(3, MAX(0, repetitions - lapses)),
            last_good_day = CAST((last_review_ms / 86400000) AS INTEGER)
        WHERE state = 2 AND repetitions > 0
      ''');
    }
    await db.execute('CREATE INDEX IF NOT EXISTS idx_srs_streak ON srs_cards(streak_days)');
    await DuplicateGroups.ensureColumn(db);
  }

  static Future<void> _migrateExplanationCache(Database db) async {
    final exists = await db.rawQuery(
      "SELECT name FROM sqlite_master WHERE type='table' AND name='explanation_cache'",
    );
    if (exists.isNotEmpty) return;
    await db.execute(_explanationCacheSql);
  }

  static void resetInstance() {
    _instance = null;
  }
}
