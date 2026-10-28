import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:memonic_app/data/database.dart';
import 'package:memonic_app/data/question_repository.dart';
import 'package:memonic_app/domain/category_filter.dart';
import 'package:memonic_app/domain/fsrs.dart';
import 'package:memonic_app/features/study/study_screen.dart';
import 'package:memonic_app/providers/app_providers.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

const _questionsSql = '''CREATE TABLE questions (id INTEGER PRIMARY KEY, kategoria TEXT, podkategoria TEXT,
  poziom TEXT, tematyka TEXT, nr_pytania INTEGER, typ_pytania TEXT DEFAULT 'testowe', pytanie TEXT,
  odp_a TEXT, odp_b TEXT, odp_c TEXT, odp_d TEXT, poprawna_odpowiedz TEXT, poprawna_odpowiedz_tekst TEXT,
  zrodlo_pliku TEXT, review_status TEXT, review_notes TEXT, study_hidden INTEGER DEFAULT 0, image_path TEXT)''';
const _srsSql = '''CREATE TABLE srs_cards (question_id INTEGER PRIMARY KEY, repetitions INTEGER DEFAULT 0,
  interval_days INTEGER DEFAULT 0, ease_factor REAL DEFAULT 2.5, due_ms INTEGER NOT NULL, lapses INTEGER DEFAULT 0,
  state INTEGER NOT NULL DEFAULT 0, step INTEGER NOT NULL DEFAULT 0, stability REAL, difficulty REAL,
  last_review_ms INTEGER)''';

void main() {
  sqfliteFfiInit();
  final s = FsrsScheduler();
  final t0 = DateTime(2026, 10, 9, 15, 0);

  group('odłożenie pytania (snooze)', () {
    test('po poprawnej odpowiedzi: powtórka za wybraną liczbę dni od 4:00, stabilność >= liczba dni', () {
      final good = s.review(FsrsCard(questionId: 1), Rating.good, t0); // FSRS: za 2 dni
      expect(good.intervalDays, 2);
      for (final days in [3, 6, 12]) {
        final c = s.snooze(good, days, t0);
        expect(c.state, CardState.review);
        expect(c.intervalDays, days);
        expect(c.due, DateTime(2026, 10, 9 + days, 4));
        expect(c.stability! >= days, isTrue);
        expect(c.reps, good.reps); // nie zmienia liczby ocen
      }
    });

    test('po błędnej odpowiedzi nadpisuje kroki powtórek (1/10 min) i przenosi kartę do powtórek na dni', () {
      final bad = s.review(FsrsCard(questionId: 1), Rating.again, t0);
      expect(bad.state, CardState.relearning);
      final c = s.snooze(bad, 6, t0);
      expect(c.state, CardState.review);
      expect(c.step, 0);
      expect(c.due, DateTime(2026, 10, 15, 4));
      expect(c.lapses, bad.lapses); // błąd został w historii
    });

    test('odłożona karta nie wraca do kolejki przed terminem', () async {
      final db = await databaseFactoryFfi.openDatabase(inMemoryDatabasePath);
      await db.execute(_questionsSql);
      await db.execute(_srsSql);
      await AppDatabase.migrateStudyStats(db);
      await db.insert('questions', {
        'id': 1, 'kategoria': 'Dział pokładowy', 'tematyka': 't', 'pytanie': 'P', 'odp_a': 'a', 'odp_b': 'b',
        'odp_c': 'c', 'poprawna_odpowiedz': 'A', 'zrodlo_pliku': 'x', 'review_status': 'ok', 'study_hidden': 0,
      });
      await db.insert('srs_cards', {'question_id': 1, 'due_ms': 0, 'state': 0});
      final repo = QuestionRepository(db);
      final now = DateTime.now();
      final bad = s.review((await repo.loadSrs(1))!, Rating.again, now);
      await repo.saveSrs(bad);
      await repo.saveSrs(s.snooze(bad, 3, now));
      expect(await repo.fetchNextCard(StudyCategory.all), isNull);
      expect(await repo.countDue(StudyCategory.all), 0);
      await db.close();
    });
  });

  testWidgets('NAUKA: po odpowiedzi pojawia się zielony przycisk z klepsydrą; 3 opcje; wybór odkłada pytanie',
      (tester) async {
    SharedPreferences.setMockInitialValues({});
    late Database db;
    await tester.runAsync(() async {
      db = await databaseFactoryFfi.openDatabase(inMemoryDatabasePath);
      await db.execute(_questionsSql);
      await db.execute(_srsSql);
      await AppDatabase.migrateStudyStats(db);
      await db.insert('questions', {
        'id': 1, 'kategoria': 'Dział pokładowy', 'tematyka': 't', 'pytanie': 'Pytanie testowe',
        'odp_a': 'aaa', 'odp_b': 'bbb', 'odp_c': 'ccc', 'poprawna_odpowiedz': 'A',
        'zrodlo_pliku': 'x', 'review_status': 'ok', 'study_hidden': 0,
      });
      await db.insert('srs_cards', {'question_id': 1, 'due_ms': 0, 'state': 0});
    });

    await tester.pumpWidget(ProviderScope(
      overrides: [databaseProvider.overrideWith((ref) async => db)],
      child: const MaterialApp(home: StudyScreen()),
    ));
    Future<void> settle() async {
      await tester.runAsync(() => Future<void>.delayed(const Duration(milliseconds: 600)));
      await tester.pump();
      await tester.pump();
    }

    await settle();
    // przed odpowiedzią przycisku nie ma
    expect(find.byIcon(Icons.hourglass_bottom), findsNothing);

    await tester.tap(find.text('aaa'));
    await settle();
    final btn = find.byIcon(Icons.hourglass_bottom);
    expect(btn, findsOneWidget);
    final box = tester.getSize(find.ancestor(of: btn, matching: find.byType(FilledButton)).first);
    expect(box.width, box.height); // kwadratowy

    await tester.tap(btn);
    await tester.pumpAndSettle();
    expect(find.text('Odłóż na 3 dni'), findsOneWidget);
    expect(find.text('Odłóż na 6 dni'), findsOneWidget);
    expect(find.text('Odłóż na 12 dni'), findsOneWidget);

    await tester.tap(find.text('Odłóż na 6 dni'));
    await tester.pump();
    await tester.runAsync(() => Future<void>.delayed(const Duration(milliseconds: 600)));
    await tester.pump();

    await tester.runAsync(() async {
      final c = (await db.query('srs_cards', where: 'question_id = 1')).first;
      expect(c['state'], 2);
      expect(c['interval_days'], 6);
      final due = DateTime.fromMillisecondsSinceEpoch(c['due_ms'] as int);
      final diffDays = due.difference(DateTime.now()).inHours / 24;
      expect(diffDays > 5 && diffDays <= 6.2, isTrue, reason: 'termin za ~6 dni, jest $diffDays');
      await db.close();
    });
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));
    expect(find.textContaining('Odłożone na 6 dni'), findsWidgets);
    await tester.pumpAndSettle(const Duration(seconds: 3));
  });
}
