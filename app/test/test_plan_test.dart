import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:memonic_app/data/database.dart';
import 'package:memonic_app/data/question_repository.dart';
import 'package:memonic_app/data/test_history.dart';
import 'package:memonic_app/domain/category_filter.dart';
import 'package:memonic_app/domain/fsrs.dart';
import 'package:memonic_app/domain/test_plan.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

void main() {
  sqfliteFfiInit();

  group('losowanie testu', () {
    test('domyślnie 105 pytań: 50% Master / 20% Angielski / 30% Pokład, zaliczenie 70', () {
      const c = TestConfig();
      expect(c.total, 105);
      expect(c.passMark, 70);
      expect(c.pokladPct, 30);
      final counts = allocateTest(c.total, [c.masterPct, c.englishPct, c.pokladPct]);
      expect(counts.reduce((a, b) => a + b), 105);
      expect(counts, [53, 21, 31]); // 52,5 / 21 / 31,5 -> reszty: remis wygrywa większy udział
    });

    test('suma zawsze równa liczbie pytań, także przy nietypowych procentach', () {
      for (final total in [20, 57, 105, 200]) {
        for (final p in [
          [50, 20, 30], [34, 33, 33], [100, 0, 0], [0, 0, 100], [10, 10, 80]
        ]) {
          expect(allocateTest(total, p).reduce((a, b) => a + b), total, reason: '$total $p');
        }
      }
    });

    test('próg zaliczenia: 70 poprawnych zalicza, 69 nie', () {
      const c = TestConfig();
      expect(c.isPassed(70), isTrue);
      expect(c.isPassed(69), isFalse);
    });

    test('zmiana ustawień: Angielski nie przekracza reszty po Master, próg ≤ liczba pytań', () {
      final c = const TestConfig().copyWith(masterPct: 90);
      expect(c.englishPct, 10);
      expect(c.pokladPct, 0);
      expect(const TestConfig().copyWith(total: 50).passMark, 50);
    });

    test('brak pytań w puli: brakujące dobierane z pozostałych pul', () {
      final r = redistributeTest([53, 21, 31], [10, 100, 100], [50, 20, 30]);
      expect(r.reduce((a, b) => a + b), 105);
      expect(r[0], 10);
      expect(r[1] <= 100 && r[2] <= 100, isTrue);
    });

    test('baza mniejsza niż test: bierze wszystko, co jest', () {
      expect(redistributeTest([53, 21, 31], [5, 5, 5], [50, 20, 30]), [5, 5, 5]);
    });
  });

  group('repozytorium testu', () {
    late Database db;
    late QuestionRepository repo;

    Future<void> q(int id, String kat, {int hidden = 0}) async {
      await db.insert('questions', {
        'id': id, 'kategoria': kat, 'tematyka': 't', 'pytanie': 'P$id', 'odp_a': 'a', 'odp_b': 'b',
        'odp_c': 'c', 'poprawna_odpowiedz': 'A', 'zrodlo_pliku': 'x', 'review_status': 'ok', 'study_hidden': hidden,
      });
      await db.insert('srs_cards', {'question_id': id, 'due_ms': 0, 'state': 0});
    }

    setUp(() async {
      db = await databaseFactoryFfi.openDatabase(inMemoryDatabasePath);
      await db.execute('''CREATE TABLE questions (id INTEGER PRIMARY KEY, kategoria TEXT, podkategoria TEXT,
        poziom TEXT, tematyka TEXT, nr_pytania INTEGER, typ_pytania TEXT DEFAULT 'testowe', pytanie TEXT,
        odp_a TEXT, odp_b TEXT, odp_c TEXT, odp_d TEXT, poprawna_odpowiedz TEXT, poprawna_odpowiedz_tekst TEXT,
        zrodlo_pliku TEXT, review_status TEXT, review_notes TEXT, study_hidden INTEGER DEFAULT 0, image_path TEXT)''');
      await db.execute('''CREATE TABLE srs_cards (question_id INTEGER PRIMARY KEY, repetitions INTEGER DEFAULT 0,
        interval_days INTEGER DEFAULT 0, ease_factor REAL DEFAULT 2.5, due_ms INTEGER NOT NULL, lapses INTEGER DEFAULT 0,
        state INTEGER NOT NULL DEFAULT 0, step INTEGER NOT NULL DEFAULT 0, stability REAL, difficulty REAL,
        last_review_ms INTEGER)''');
      await AppDatabase.migrateStudyStats(db);
      repo = QuestionRepository(db);
      for (var i = 1; i <= 10; i++) {
        await q(i, StudyCategory.master.dbValue!);
      }
      for (var i = 11; i <= 14; i++) {
        await q(i, StudyCategory.angielski.dbValue!);
      }
      await q(15, StudyCategory.angielski.dbValue!, hidden: 1); // „Błąd” - nie do testu
    });
    tearDown(() => db.close());

    const cats = [StudyCategory.master, StudyCategory.angielski, StudyCategory.poklad];
    const pcts = [50, 20, 30];

    test('bez powtórzeń z poprzednich testów: wykluczone pytania nie wracają (Normalny i Trudny)', () async {
      final ex = await repo.duplicateKeysForIds([1, 2, 3, 4, 5, 6, 7, 8]);
      final r = await repo.pickTestQuestions(cats, [2, 2, 0], pcts, exclude: ex);
      expect(r.length, 4);
      expect(r.every((e) => e.id > 8), isTrue); // Master: tylko 9 i 10; Angielski: 11–14
      final h = await repo.pickHardTestQuestions(6, exclude: ex);
      expect(h.every((e) => e.id > 8), isTrue);
      expect(h.length, 6); // 9,10 + 11..14 (ukryte 15 poza pulą)
      // bez wykluczenia pula jest pełna
      expect((await repo.pickTestQuestions(cats, [8, 0, 0], pcts)).length, 8);
    });

    test('historia testów: wykluczane są pytania tylko z 2 ostatnich zakończonych testów', () async {
      SharedPreferences.setMockInitialValues({});
      TestResult t(int day, List<int> ids) => TestResult(
            timestamp: DateTime(2026, 10, day),
            total: ids.length,
            answered: ids.length,
            correct: ids.length,
            passMark: 1,
            perCategory: const {},
            questionIds: ids,
          );
      await TestHistory.add(t(1, [1, 2]));
      await TestHistory.add(t(2, [3, 4]));
      await TestHistory.add(t(3, [5, 6]));
      expect(await TestHistory.recentQuestionIds(testNoRepeatDepth), {3, 4, 5, 6}); // test 1 już może wrócić
      expect(testNoRepeatDepth, 2);
    });

    test('losuje z właściwych pul, bez ukrytych i bez powtórzeń', () async {
      final r = await repo.pickTestQuestions(cats, [6, 3, 0], pcts);
      expect(r.length, 9);
      expect(r.map((e) => e.id).toSet().length, 9);
      expect(r.where((e) => e.kategoria == StudyCategory.master.dbValue).length, 6);
      expect(r.any((e) => e.id == 15), isFalse); // ukryte „Błąd”
    });

    test('baza mniejsza niż test: bierze wszystko (bez ukrytych)', () async {
      final r = await repo.pickTestQuestions(cats, [53, 21, 31], pcts);
      expect(r.length, 14); // 10 Master + 4 Angielski (5. ukryte), Pokład pusty
      expect(r.map((e) => e.id).toSet().length, 14);
    });

    test('ta sama treść w kilku wierszach (inne ID, inny poziom, inne kategorie) trafia do testu tylko raz', () async {
      // 6 kopii jednego pytania w Angielskim + kopia w Pokładzie + 2 różne pytania
      for (var i = 100; i < 106; i++) {
        await db.insert('questions', {
          'id': i, 'kategoria': StudyCategory.angielski.dbValue, 'poziom': i % 2 == 0 ? 'operacyjny' : null,
          'tematyka': 't', 'pytanie': 'The observer’s horizon is:', 'odp_a': 'x', 'odp_b': 'y',
          'odp_c': 'z', 'poprawna_odpowiedz': 'C', 'zrodlo_pliku': 'x', 'review_status': 'ok', 'study_hidden': 0,
        });
        await db.insert('srs_cards', {'question_id': i, 'due_ms': 0, 'state': 0});
      }
      await db.insert('questions', {
        'id': 200, 'kategoria': StudyCategory.poklad.dbValue, 'tematyka': 't', 'pytanie': 'the observers horizon is',
        'odp_a': 'x', 'odp_b': 'y', 'odp_c': 'z', 'poprawna_odpowiedz': 'C', 'zrodlo_pliku': 'x',
        'review_status': 'ok', 'study_hidden': 0,
      });
      await db.insert('srs_cards', {'question_id': 200, 'due_ms': 0, 'state': 0});
      for (var run = 0; run < 20; run++) {
        final r = await repo.pickTestQuestions(cats, [10, 10, 10], pcts);
        final horizon = r.where((e) => e.pytanie.toLowerCase().contains('horizon')).length;
        expect(horizon, 1, reason: 'powtórzone pytanie w teście (przebieg $run)');
        final keys = <String>{};
        for (final q in r) {
          for (final k in QuestionRepository.duplicateKeys(q)) {
            expect(keys.add(k), isTrue, reason: 'duplikat ${q.id}');
          }
        }
        expect(r.length, 10 + 4 + 1); // 10 Master + 4 unikalne Angielski (3 + horizon... ) = bez powtórzeń
      }
    });

    test('błędna odpowiedź w teście => karta w powtórce po 1 min, seria zerowana', () async {
      final scheduler = FsrsScheduler();
      final now = DateTime(2026, 10, 8, 12);
      final card = await repo.loadSrs(1) ?? FsrsCard(questionId: 1);
      final updated = scheduler.review(card, Rating.again, now);
      await repo.saveSrs(updated);
      await repo.recordAnswer(
          questionId: 1, correct: false, rating: 1, lapses: updated.lapses, now: now);
      final back = (await repo.loadSrs(1))!;
      expect(back.state, CardState.relearning);
      expect(back.due, now.add(const Duration(minutes: 1)));
      // po minucie karta jest „do powtórki teraz” w swoim dziale
      final due = await repo.fetchNextCard(StudyCategory.master);
      expect(due, isNotNull);
    });
  });

  test('historia testów: wynik zaliczony/niezaliczony', () {
    final r = TestResult(
      timestamp: DateTime(2026, 10, 8),
      total: 105,
      answered: 105,
      correct: 72,
      passMark: 70,
      perCategory: {'Master': [40, 53]},
    );
    expect(r.passed, isTrue);
    final back = TestResult.fromJson(r.toJson().map((k, v) => MapEntry(k, v)));
    expect(back.correct, 72);
    expect(back.perCategory['Master'], [40, 53]);
  });
}
