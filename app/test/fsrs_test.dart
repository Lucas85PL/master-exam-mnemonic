import 'package:flutter_test/flutter_test.dart';
import 'package:memonic_app/data/database.dart';
import 'package:memonic_app/data/question_repository.dart';
import 'package:memonic_app/domain/category_filter.dart';
import 'package:memonic_app/domain/fsrs.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

void main() {
  sqfliteFfiInit();
  final s = FsrsScheduler();
  final t0 = DateTime(2026, 10, 5, 20, 0);

  group('wzory FSRS-6', () {
    test('retrievability: 100% teraz i 90% po czasie równym stabilności', () {
      expect(s.retrievability(5, 0), closeTo(1.0, 1e-9));
      expect(s.retrievability(5, 5), closeTo(0.9, 1e-6));
    });

    test('nowa karta: Good daje stabilność w2 i interwał 2 dni', () {
      final c = s.review(FsrsCard(questionId: 1), Rating.good, t0);
      expect(c.state, CardState.review);
      expect(c.stability, closeTo(2.3065, 1e-9));
      expect(c.intervalDays, 2);
      expect(c.due, DateTime(2026, 10, 7, 4)); // od rana, nie co do godziny
    });

    test('Again < Hard < Good < Easy dla stabilności po poprawnym powtórzeniu', () {
      final base = s.review(FsrsCard(questionId: 1), Rating.good, t0);
      final later = t0.add(const Duration(days: 3));
      final st = {
        for (final r in [Rating.hard, Rating.good, Rating.easy])
          r: s.review(base, r, later).stability!,
      };
      expect(st[Rating.hard]!, lessThan(st[Rating.good]!));
      expect(st[Rating.good]!, lessThan(st[Rating.easy]!));
      expect(st[Rating.good]!, greaterThan(base.stability!));
    });

    test('błąd w powtórce obniża stabilność i zwiększa liczbę błędów', () {
      final base = s.review(FsrsCard(questionId: 1), Rating.good, t0);
      final later = t0.add(const Duration(days: 3));
      final f = s.review(base, Rating.again, later);
      expect(f.stability!, lessThan(base.stability!));
      expect(f.lapses, 1);
      expect(f.state, CardState.relearning);
    });

    test('wyższa retencja = krótszy interwał', () {
      final hi = FsrsScheduler(desiredRetention: 0.95).nextIntervalDays(10);
      final lo = FsrsScheduler(desiredRetention: 0.80).nextIntervalDays(10);
      expect(hi, lessThan(lo));
      expect(s.nextIntervalDays(10), 10); // retencja 0.9 => interwał = stabilność
    });
  });

  group('błąd => powtórka w tej samej sesji', () {
    test('nowa karta + błąd: wraca po 1 min, potem po 10 min, potem jutro rano', () {
      var c = s.review(FsrsCard(questionId: 1), Rating.again, t0);
      expect(c.state, CardState.relearning);
      expect(c.due, t0.add(const Duration(minutes: 1)));

      final t1 = t0.add(const Duration(minutes: 1));
      c = s.review(c, Rating.good, t1);
      expect(c.state, CardState.relearning);
      expect(c.due, t1.add(const Duration(minutes: 10)));

      final t2 = t1.add(const Duration(minutes: 10));
      c = s.review(c, Rating.good, t2);
      expect(c.state, CardState.review);
      expect(c.intervalDays, 1);
      expect(c.due, DateTime(2026, 10, 6, 4));
    });

    test('kolejny błąd w powtórce cofa do pierwszego kroku', () {
      var c = s.review(FsrsCard(questionId: 1), Rating.again, t0);
      final t1 = t0.add(const Duration(minutes: 1));
      c = s.review(c, Rating.good, t1);
      c = s.review(c, Rating.again, t1.add(const Duration(minutes: 10)));
      expect(c.step, 0);
      expect(c.state, CardState.relearning);
    });
  });

  test('dueInDays: noc przed godziną zmiany dnia liczy się do poprzedniego dnia', () {
    expect(s.dueInDays(DateTime(2026, 10, 6, 2, 0), 1), DateTime(2026, 10, 6, 4));
    expect(s.dueInDays(DateTime(2026, 10, 6, 9, 0), 1), DateTime(2026, 10, 7, 4));
  });

  test('dueLabel', () {
    final n = DateTime(2026, 1, 1, 12);
    expect(FsrsScheduler.dueLabel(n.add(const Duration(minutes: 10)), n), 'za 10 min');
    expect(FsrsScheduler.dueLabel(n.add(const Duration(hours: 16)), n), 'za 16 godz.');
    expect(FsrsScheduler.dueLabel(n.add(const Duration(days: 1)), n), 'jutro');
    expect(FsrsScheduler.dueLabel(n.add(const Duration(days: 4)), n), 'za 4 dni');
  });

  group('migracja SM-2 -> FSRS', () {
    test('nowa karta pozostaje nowa', () {
      final m = Sm2Migration.convert(
          repetitions: 0, intervalDays: 0, easeFactor: 2.5, dueMs: 0, lapses: 0);
      expect(m['state'], 0);
    });

    test('karta po błędzie "na jutro 20:00" staje się dostępna od 4:00 tego dnia', () {
      final due = DateTime(2026, 10, 6, 20, 0).millisecondsSinceEpoch;
      final m = Sm2Migration.convert(
          repetitions: 0 + 1, intervalDays: 1, easeFactor: 2.3, dueMs: due, lapses: 1);
      expect(m['state'], 2);
      expect(m['stability'], 1.0);
      expect(DateTime.fromMillisecondsSinceEpoch(m['due_ms'] as int), DateTime(2026, 10, 6, 4));
    });

    test('migracja bazy dodaje kolumny i przenosi karty', () async {
      final db = await databaseFactoryFfi.openDatabase(inMemoryDatabasePath);
      await db.execute('''CREATE TABLE srs_cards (question_id INTEGER PRIMARY KEY,
        repetitions INTEGER NOT NULL DEFAULT 0, interval_days INTEGER NOT NULL DEFAULT 0,
        ease_factor REAL NOT NULL DEFAULT 2.5, due_ms INTEGER NOT NULL, lapses INTEGER NOT NULL DEFAULT 0)''');
      final due = DateTime(2026, 10, 6, 20).millisecondsSinceEpoch;
      await db.insert('srs_cards', {'question_id': 1, 'due_ms': due});
      await db.insert('srs_cards', {
        'question_id': 2, 'repetitions': 2, 'interval_days': 6, 'ease_factor': 2.6, 'due_ms': due,
      });
      await AppDatabase.migrateSrsToFsrs(db);
      await AppDatabase.migrateSrsToFsrs(db); // idempotentna
      final r = await db.query('srs_cards', orderBy: 'question_id');
      expect(r[0]['state'], 0);
      expect(r[1]['state'], 2);
      expect(r[1]['stability'], 6.0);
      await db.close();
    });
  });

  group('kolejka pytań', () {
    late Database db;
    late QuestionRepository repo;
    final now = DateTime.now().millisecondsSinceEpoch;

    Future<void> card(int id, int state, int dueMs) async {
      await db.insert('questions', {
        'id': id, 'kategoria': 'Dział pokładowy', 'tematyka': 't', 'pytanie': 'P$id',
        'odp_a': 'a', 'odp_b': 'b', 'odp_c': 'c', 'poprawna_odpowiedz': 'A',
        'zrodlo_pliku': 'x', 'review_status': 'ok', 'study_hidden': 0,
      });
      await db.insert('srs_cards', {'question_id': id, 'due_ms': dueMs, 'state': state});
    }

    setUp(() async {
      db = await databaseFactoryFfi.openDatabase(inMemoryDatabasePath);
      await db.execute('''CREATE TABLE questions (id INTEGER PRIMARY KEY, kategoria TEXT, podkategoria TEXT,
        poziom TEXT, tematyka TEXT, nr_pytania INTEGER, typ_pytania TEXT DEFAULT 'testowe', pytanie TEXT,
        odp_a TEXT, odp_b TEXT, odp_c TEXT, odp_d TEXT, poprawna_odpowiedz TEXT, poprawna_odpowiedz_tekst TEXT,
        zrodlo_pliku TEXT, review_status TEXT, review_notes TEXT, study_hidden INTEGER DEFAULT 0)''');
      await db.execute('''CREATE TABLE srs_cards (question_id INTEGER PRIMARY KEY, repetitions INTEGER DEFAULT 0,
        interval_days INTEGER DEFAULT 0, ease_factor REAL DEFAULT 2.5, due_ms INTEGER NOT NULL, lapses INTEGER DEFAULT 0,
        state INTEGER NOT NULL DEFAULT 0, step INTEGER NOT NULL DEFAULT 0, stability REAL, difficulty REAL,
        last_review_ms INTEGER)''');
      await AppDatabase.migrateStudyStats(db);
      repo = QuestionRepository(db);
    });
    tearDown(() => db.close());

    test('najpierw powtórki po błędzie, potem zaległe, potem nowe', () async {
      await card(1, 0, now); // nowa
      await card(2, 2, now - 1000); // zaległa na dni
      await card(3, 3, now - 500); // po błędzie, czas minął
      final all = StudyCategory.all;
      expect((await repo.fetchNextCard(all))!['id'], 3);
      await db.update('srs_cards', {'due_ms': now + 3600000}, where: 'question_id = 3');
      expect((await repo.fetchNextCard(all))!['id'], 2);
      await db.update('srs_cards', {'due_ms': now + 86400000}, where: 'question_id = 2');
      expect((await repo.fetchNextCard(all))!['id'], 1);
    });

    test('tryb "same nowe" daje tylko karty, które nie pojawiły się ani razu', () async {
      await card(1, 2, now - 1000); // zaległa
      await card(2, 3, now - 500); // po błędzie
      final all = StudyCategory.all;
      expect(await repo.fetchNextCard(all, onlyNew: true), isNull);
      await card(3, 0, now);
      await card(4, 0, now);
      final ids = {(await repo.fetchNextCard(all, onlyNew: true))!['id'], (await repo.fetchNextCard(all, onlyNew: true, excludeId: 3))!['id']};
      expect(ids.every((i) => i == 3 || i == 4), true);
      expect((await repo.fetchNextCard(all, onlyNew: true, excludeId: 3))!['id'], 4);
    });

    test('pytania z błędem na jutro są widoczne jako zaplanowane, a nie "do powtórki teraz"', () async {
      await card(1, 2, now + 12 * 3600000);
      await card(2, 2, now - 1000);
      final all = StudyCategory.all;
      expect(await repo.countDue(all), 1);
      expect(await repo.countUpcoming(all), 1);
    });

    test('nie powtarza tej samej karty dwa razy z rzędu, gdy są inne', () async {
      await card(1, 3, now - 1000);
      await card(2, 2, now - 1000);
      expect((await repo.fetchNextCard(StudyCategory.all, excludeId: 1))!['id'], 2);
    });

    test('gdy zostaje tylko karta po błędzie (jeszcze nie w terminie), nie kończy sesji', () async {
      await card(1, 3, now + 5 * 60000);
      expect((await repo.fetchNextCard(StudyCategory.all))!['id'], 1);
      expect((await repo.fetchNextCard(StudyCategory.all, excludeId: 1))!['id'], 1);
    });

    test('tryb "powtórz zaplanowane" daje karty z terminem w ciągu 24 h, najbliższe najpierw', () async {
      await card(1, 2, now + 20 * 3600000);
      await card(2, 2, now + 5 * 3600000);
      await card(3, 2, now + 72 * 3600000); // za daleko
      await card(4, 0, now); // nowa - nie bierze udziału
      final all = StudyCategory.all;
      expect((await repo.fetchNextCard(all, ahead: true))!['id'], 2);
      expect((await repo.fetchNextCard(all, ahead: true, excludeId: 2))!['id'], 1);
      await db.update('srs_cards', {'due_ms': now + 72 * 3600000}, where: 'question_id IN (1,2)');
      expect(await repo.fetchNextCard(all, ahead: true), isNull);
    });

    test('tryb "powtórz zaplanowane" kończy się: zaliczone karty nie wracają w sesji (regresja: pętla na 2 pytaniach)', () async {
      // karty "na jutro rano" (w oknie 24 h); po poprawnej odpowiedzi nadal są w oknie
      for (var i = 1; i <= 25; i++) {
        await card(i, 2, now + (3 + i) * 600000);
      }
      final all = StudyCategory.all;
      final done = <int>{};
      int? last;
      var steps = 0;
      while (true) {
        final row = await repo.fetchNextCard(all, ahead: true, excludeId: last, doneIds: done);
        if (row == null) break;
        final id = row['id'] as int;
        expect(done.contains(id), isFalse, reason: 'karta $id wróciła w tej samej sesji');
        done.add(id); // poprawna odpowiedź => karta zaliczona
        last = id;
        expect(++steps, lessThanOrEqualTo(25), reason: 'pętla bez końca');
      }
      expect(done.length, 25);
    });

    test('saveSrs/loadSrs zachowuje stan FSRS', () async {
      await card(1, 0, now);
      final c = FsrsScheduler().review(FsrsCard(questionId: 1), Rating.again, DateTime.now());
      await repo.saveSrs(c);
      final l = (await repo.loadSrs(1))!;
      expect(l.state, CardState.relearning);
      expect(l.stability, closeTo(c.stability!, 1e-9));
    });
  });
}
