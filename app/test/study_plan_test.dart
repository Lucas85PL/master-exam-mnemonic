import 'package:flutter_test/flutter_test.dart';
import 'package:memonic_app/data/database.dart';
import 'package:memonic_app/data/question_repository.dart';
import 'package:memonic_app/domain/category_filter.dart';
import 'package:memonic_app/domain/study_plan.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

void main() {
  sqfliteFfiInit();

  group('dzień nauki i seria', () {
    test('dzień nauki zmienia się o 4:00', () {
      final late = studyDayOf(DateTime(2026, 10, 6, 3, 59));
      final early = studyDayOf(DateTime(2026, 10, 6, 4, 0));
      expect(early, late + 1);
      expect(studyDayOf(DateTime(2026, 10, 6, 23, 0)), early);
    });

    test('seria rośnie raz na dzień, błąd zeruje, znane od 3 dni', () {
      var st = const StreakState(0, null);
      st = nextStreak(st, correct: true, today: 100);
      st = nextStreak(st, correct: true, today: 100); // ten sam dzień - bez zmian
      expect(st.days, 1);
      st = nextStreak(st, correct: true, today: 102);
      expect(isKnown(st.days), isFalse);
      st = nextStreak(st, correct: true, today: 113);
      expect(isKnown(st.days), isTrue);
      st = nextStreak(st, correct: false, today: 120);
      expect(st.days, 0);
    });
  });

  group('wstrzykiwanie nowych pytań', () {
    test('brak danych = co 5, dobra passa = co 3, słaba = co 8', () {
      expect(newCardGap([]), 5);
      expect(newCardGap([true, true]), 5);
      expect(newCardGap(List.filled(10, true)), 3);
      expect(newCardGap([true, true, true, true, true, true, true, true, true, false]), 3);
      expect(newCardGap([true, true, true, true, false, false, true, true, false, true]), 5);
      expect(newCardGap([false, false, false, true, false, false, true, false, false, false]), 8);
    });

    test('liczy się tylko ostatnie 10 odpowiedzi', () {
      final old = List.filled(20, false);
      expect(newCardGap([...old, ...List.filled(10, true)]), 3);
    });
  });

  group('trudne pytania', () {
    test('≥3 błędy w ostatnich 10 albo ≥3 lapsy bez serii', () {
      expect(computeHard(wrongOfLast10: 3, lapses: 0, streakDays: 0), isTrue);
      expect(computeHard(wrongOfLast10: 2, lapses: 0, streakDays: 0), isFalse);
      expect(computeHard(wrongOfLast10: 0, lapses: 3, streakDays: 1), isTrue);
      expect(computeHard(wrongOfLast10: 0, lapses: 3, streakDays: 3), isFalse);
    });
  });

  group('plan do egzaminu', () {
    test('bez terminu: tylko postęp', () {
      final p = DailyPlan.compute(
          total: 100, known: 25, remainingReviews: 200, doneToday: 0, today: 100, examDay: null);
      expect(p.hasExam, isFalse);
      expect(p.progress, 0.25);
    });

    test('bez własnych danych: koszt startowy 1,4 odpowiedzi na jednostkę serii', () {
      // egzamin za 33 dni => termin docelowy za 30 dni => 31 dni nauki włącznie z dzisiejszym
      final p = DailyPlan.compute(
          total: 1000, known: 0, remainingReviews: 3000, doneToday: 0, today: 100, examDay: 133);
      expect(p.daysLeft, 31);
      expect(p.costPerUnit, closeTo(1.4, 1e-9));
      expect(p.perDay, (1.4 * 3000 / 31).ceil());
      expect(p.goalToday, p.perDay);
      expect(p.hasOwnData, isFalse);
      expect(p.projectedDays, isNull); // brak przyrostu - brak prognozy
      expect(p.tooLate, isFalse);
    });

    test('cel dzienny zależy od Twojego tempa: skuteczniejsza nauka = mniej odpowiedzi dziennie', () {
      // A: 200 odpowiedzi dało 150 jednostek serii (sprawnie), B: 200 odpowiedzi dało 40 (dużo błędów)
      PaceStats pace(int units) => PaceStats(answers: 200, netUnits: units, mastered: units ~/ 3, windowDays: 10);
      final a = DailyPlan.compute(
          total: 500, known: 0, remainingReviews: 900, doneToday: 0, today: 100, examDay: 133, pace: pace(150));
      final b = DailyPlan.compute(
          total: 500, known: 0, remainingReviews: 900, doneToday: 0, today: 100, examDay: 133, pace: pace(40));
      expect(a.costPerUnit, closeTo((200 + 14) / (150 + 10), 1e-9));
      expect(b.costPerUnit, closeTo((200 + 14) / (40 + 10), 1e-9));
      expect(a.goalToday, lessThan(b.goalToday));
      expect(a.hasOwnData, isTrue);
    });

    test('prognoza: kiedy opanujesz materiał przy obecnym przyroście i czy zdążysz do terminu', () {
      const pace = PaceStats(answers: 200, netUnits: 100, mastered: 33, windowDays: 10); // 10 jednostek/dzień
      final ok = DailyPlan.compute(
          total: 200, known: 0, remainingReviews: 300, doneToday: 0, today: 100, examDay: 133, pace: pace);
      expect(ok.unitsPerDay, closeTo(10, 1e-9));
      expect(ok.masteredPerDay, closeTo(3.3, 1e-9));
      expect(ok.projectedDays, 30);
      expect(ok.onTrack, isTrue); // 30 dni <= 31 dni do terminu docelowego
      final late = DailyPlan.compute(
          total: 200, known: 0, remainingReviews: 300, doneToday: 0, today: 100, examDay: 120, pace: pace);
      expect(late.daysLeft, 18);
      expect(late.onTrack, isFalse);
    });

    test('prognoza nie jest krótsza niż minimum wynikające z odstępów serii (nawet przy ogromnym tempie)', () {
      const fast = PaceStats(answers: 600, netUnits: 600, mastered: 200, windowDays: 2); // 300 jednostek/dzień
      final p = DailyPlan.compute(
          total: 100, known: 0, remainingReviews: 300, doneToday: 0, today: 100, examDay: 133,
          pace: fast, minDaysToFinish: minDaysForUnits(3));
      expect(minDaysForUnits(3), 5);
      expect(minDaysForUnits(2), 3);
      expect(minDaysForUnits(1), 1);
      expect(p.projectedDays, 5); // 300 / 300 = 1 dzień, ale seria 0 -> 3 wymaga ok. 5 dni
    });

    test('ujemny przyrost (dużo błędów) nie psuje celu: wraca do założenia startowego', () {
      const pace = PaceStats(answers: 60, netUnits: -20, mastered: 0, windowDays: 5);
      final p = DailyPlan.compute(
          total: 100, known: 0, remainingReviews: 300, doneToday: 0, today: 100, examDay: 133, pace: pace);
      expect(p.costPerUnit, closeTo((60 + 14) / 10, 1e-9));
      expect(p.projectedDays, isNull);
      expect(p.goalToday, greaterThan(0));
    });

    test('cel na dziś jest stabilny w ciągu dnia (przyrost dzisiejszy wraca do pracy początkowej)', () {
      final before = DailyPlan.compute(
          total: 100, known: 0, remainingReviews: 300, doneToday: 0, today: 10, examDay: 43);
      // po 40 odpowiedziach, które dały 40 jednostek serii, pozostała praca spadła o 40, a cel dnia się nie zmienia
      final after = DailyPlan.compute(
          total: 100, known: 0, remainingReviews: 260, doneToday: 40, today: 10, examDay: 43,
          pace: const PaceStats(unitsToday: 40));
      expect(after.goalToday, before.goalToday);
    });

    test('za mało czasu', () {
      final p = DailyPlan.compute(
          total: 10, known: 0, remainingReviews: 30, doneToday: 0, today: 100, examDay: 102);
      expect(p.tooLate, isTrue);
      expect(p.perDay, greaterThan(0));
    });
  });

  group('interwał a egzamin', () {
    test('bez egzaminu interwał FSRS bez zmian', () {
      expect(capIntervalForExam(intervalDays: 46, streakAfter: 2, today: 10, targetDay: null), 46);
    });

    test('skraca interwał, by seria 3 dni zdążyła się zamknąć przed terminem', () {
      // 12 dni do terminu, seria 1 => brakuje 2 odpowiedzi => co najwyżej 12 ~/ 3 = 4 dni
      expect(capIntervalForExam(intervalDays: 11, streakAfter: 1, today: 100, targetDay: 112), 4);
      expect(capIntervalForExam(intervalDays: 2, streakAfter: 1, today: 100, targetDay: 112), 2);
    });

    test('po terminie interwał to minimum 1 dzień', () {
      expect(capIntervalForExam(intervalDays: 11, streakAfter: 0, today: 100, targetDay: 99), 1);
    });
  });

  group('repozytorium: seria, trudne, kolejka z nowymi', () {
    late Database db;
    late QuestionRepository repo;
    final now = DateTime(2026, 10, 6, 12);

    Future<void> card(int id, int state, int dueMs, {int hard = 0}) async {
      await db.insert('questions', {
        'id': id, 'kategoria': 'Dział pokładowy', 'tematyka': 't', 'pytanie': 'P$id',
        'odp_a': 'a', 'odp_b': 'b', 'odp_c': 'c', 'poprawna_odpowiedz': 'A',
        'zrodlo_pliku': 'x', 'review_status': 'ok', 'study_hidden': 0,
      });
      await db.insert('srs_cards', {'question_id': id, 'due_ms': dueMs, 'state': state, 'hard': hard});
    }

    const srsSql = '''CREATE TABLE srs_cards (question_id INTEGER PRIMARY KEY, repetitions INTEGER DEFAULT 0,
        interval_days INTEGER DEFAULT 0, ease_factor REAL DEFAULT 2.5, due_ms INTEGER NOT NULL, lapses INTEGER DEFAULT 0,
        state INTEGER NOT NULL DEFAULT 0, step INTEGER NOT NULL DEFAULT 0, stability REAL, difficulty REAL,
        last_review_ms INTEGER)''';

    setUp(() async {
      db = await databaseFactoryFfi.openDatabase(inMemoryDatabasePath);
      await db.execute('''CREATE TABLE questions (id INTEGER PRIMARY KEY, kategoria TEXT, podkategoria TEXT,
        poziom TEXT, tematyka TEXT, nr_pytania INTEGER, typ_pytania TEXT DEFAULT 'testowe', pytanie TEXT,
        odp_a TEXT, odp_b TEXT, odp_c TEXT, odp_d TEXT, poprawna_odpowiedz TEXT, poprawna_odpowiedz_tekst TEXT,
        zrodlo_pliku TEXT, review_status TEXT, review_notes TEXT, study_hidden INTEGER DEFAULT 0)''');
      await db.execute(srsSql);
      await AppDatabase.migrateStudyStats(db);
      repo = QuestionRepository(db);
    });
    tearDown(() => db.close());

    test('migracja jest idempotentna i szacuje serię istniejących kart', () async {
      await db.execute('DROP TABLE review_log');
      await db.execute('DROP TABLE srs_cards');
      await db.execute(srsSql);
      await db.insert('srs_cards',
          {'question_id': 1, 'due_ms': 0, 'state': 2, 'repetitions': 5, 'lapses': 1, 'last_review_ms': 86400000 * 20});
      await db.insert('srs_cards', {'question_id': 2, 'due_ms': 0, 'state': 0});
      await AppDatabase.migrateStudyStats(db);
      await AppDatabase.migrateStudyStats(db);
      final rows = await db.query('srs_cards', orderBy: 'question_id');
      expect(rows[0]['streak_days'], 3);
      expect(rows[1]['streak_days'], 0);
    });

    test('3 poprawne odpowiedzi w 3 różne dni = znane; błąd zeruje serię', () async {
      await card(1, 2, 0);
      for (var d = 0; d < 3; d++) {
        final t = now.add(Duration(days: d * 2));
        final o = await repo.recordAnswer(questionId: 1, correct: true, rating: 3, lapses: 0, now: t);
        expect(o.streakDays, d + 1);
      }
      expect(await repo.countKnown(StudyCategory.all), 1);
      expect(await repo.countRemainingReviews(StudyCategory.all), 0);
      await repo.recordAnswer(
          questionId: 1, correct: false, rating: 1, lapses: 1, now: now.add(const Duration(days: 9)));
      expect(await repo.countKnown(StudyCategory.all), 0);
      expect(await repo.countRemainingReviews(StudyCategory.all), 3);
    });

    test('kilka poprawnych odpowiedzi tego samego dnia to jedna seria', () async {
      await card(1, 2, 0);
      for (var i = 0; i < 4; i++) {
        await repo.recordAnswer(
            questionId: 1, correct: true, rating: 3, lapses: 0, now: now.add(Duration(minutes: i)));
      }
      final s = (await db.query('srs_cards')).first;
      expect(s['streak_days'], 1);
      expect(await repo.countAnswersOnDay(studyDayOf(now)), 4);
    });

    test('tempo nauki z dziennika: odpowiedzi, przyrost serii netto i opanowane pytania — osobno dla działów', () async {
      await card(1, 2, 0);
      await card(2, 2, 0);
      await db.update('questions', {'kategoria': StudyCategory.master.dbValue}, where: 'id = 2');
      final today = studyDayOf(now);
      // pytanie 1 (Pokład): 3 poprawne odpowiedzi w 3 dni => znane; pytanie 2 (Master): poprawna, potem błąd
      for (var d = 0; d < 3; d++) {
        await repo.recordAnswer(
            questionId: 1, correct: true, rating: 3, lapses: 0, now: now.add(Duration(days: d - 2)));
      }
      await repo.recordAnswer(questionId: 2, correct: true, rating: 3, lapses: 0, now: now.add(const Duration(days: -2)));
      await repo.recordAnswer(questionId: 2, correct: false, rating: 1, lapses: 1, now: now.add(const Duration(days: -1)));
      final all = await repo.paceStats(StudyCategory.all, today);
      expect(all.answers, 5);
      expect(all.netUnits, 3 + 0); // 3 (pyt. 1) + (+1 −1) (pyt. 2)
      expect(all.mastered, 1);
      expect(all.windowDays, 3);
      final poklad = await repo.paceStats(StudyCategory.poklad, today);
      expect(poklad.answers, 3);
      expect(poklad.mastered, 1);
      final master = await repo.paceStats(StudyCategory.master, today);
      expect(master.answers, 2);
      expect(master.netUnits, 0);
      expect(master.mastered, 0);
      expect(await repo.countAnswersOnDay(today, category: StudyCategory.poklad), 1);
      expect(await repo.countAnswersOnDay(today, category: StudyCategory.master), 0);
    });

    test('pytanie błędnie zaznaczane 3 razy staje się „trudne”', () async {
      await card(1, 2, 0);
      for (var i = 0; i < 3; i++) {
        final o = await repo.recordAnswer(
            questionId: 1, correct: false, rating: 1, lapses: 0, now: now.add(Duration(minutes: i)));
        expect(o.hard, i == 2);
      }
      expect(await repo.countHard(StudyCategory.all), 1);
    });

    test('preferNew wstawia nowe pytanie przed zaległymi; zaległe: najpierw trudne', () async {
      await card(1, 2, now.millisecondsSinceEpoch - 1000);
      await card(2, 2, now.millisecondsSinceEpoch - 1000, hard: 1);
      await card(3, 0, now.millisecondsSinceEpoch);
      final all = StudyCategory.all;
      final injected = repo.rowFromMap((await repo.fetchNextCard(all, preferNew: true))!);
      expect(injected.id, 3);
      expect(injected.isNewCard, isTrue);
      for (var i = 0; i < 5; i++) {
        expect((await repo.fetchNextCard(all))!['id'], 2); // trudne przed zwykłymi
      }
    });

    test('preferNew bez nowych pytań wraca do zwykłej kolejki', () async {
      await card(1, 2, now.millisecondsSinceEpoch - 1000);
      expect((await repo.fetchNextCard(StudyCategory.all, preferNew: true))!['id'], 1);
    });
  });
}
