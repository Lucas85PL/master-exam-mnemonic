import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:memonic_app/data/database.dart';
import 'package:memonic_app/features/test/test_screen.dart';
import 'package:memonic_app/providers/app_providers.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

void main() {
  sqfliteFfiInit();

  testWidgets('TEST: przejście przez pytania, wynik i trafienie błędów do powtórek', (tester) async {
    SharedPreferences.setMockInitialValues({'test_total': 6, 'test_pass': 4, 'shuffle_answers': false});
    late Database db;
    await tester.runAsync(() async {
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
      final cats = ['Kapitan żeglugi wielkiej', 'Kapitan żeglugi wielkiej', 'Kapitan żeglugi wielkiej',
        'Angielski', 'Dział pokładowy', 'Dział pokładowy'];
      for (var i = 0; i < 6; i++) {
        await db.insert('questions', {
          'id': i + 1, 'kategoria': cats[i], 'tematyka': 't', 'pytanie': 'Pytanie ${i + 1}',
          'odp_a': 'aaa', 'odp_b': 'bbb', 'odp_c': 'ccc', 'poprawna_odpowiedz': 'A',
          'zrodlo_pliku': 'x', 'review_status': 'ok', 'study_hidden': 0,
        });
        await db.insert('srs_cards', {'question_id': i + 1, 'due_ms': 0, 'state': 0});
      }
    });

    await tester.pumpWidget(ProviderScope(
      overrides: [databaseProvider.overrideWith((ref) async => db)],
      child: const MaterialApp(home: TestScreen()),
    ));
    await tester.runAsync(() => Future<void>.delayed(const Duration(milliseconds: 300)));
    await tester.pump();
    await tester.pump();

    expect(find.textContaining('TEST  1 / 6'), findsOneWidget);

    // 4 poprawne (A) + 1 błędna (B) + 1 „Nie wiem”
    final plan = ['A', 'A', 'A', 'A', 'B', null];
    // zapis do bazy (ffi, osobny izolat) kończy się poza zegarem testu - czekamy na realny czas, aż ekran przejdzie dalej
    Future<void> waitUntil(bool Function() done) async {
      for (var k = 0; k < 60 && !done(); k++) {
        await tester.runAsync(() => Future<void>.delayed(const Duration(milliseconds: 100)));
        await tester.pump();
      }
    }

    for (var i = 0; i < plan.length; i++) {
      if (plan[i] == null) {
        await tester.tap(find.text('Nie wiem'));
      } else {
        await tester.tap(find.textContaining('${plan[i]}) '));
        await tester.pump();
        await tester.tap(find.text(i == plan.length - 1 ? 'Zakończ test' : 'Dalej'));
      }
      final next = i == plan.length - 1
          ? () => find.textContaining('TEST ZALICZONY').evaluate().isNotEmpty || find.textContaining('NIEZALICZONY').evaluate().isNotEmpty
          : () => find.textContaining('TEST  ${i + 2} / 6').evaluate().isNotEmpty;
      await waitUntil(next);
    }

    expect(find.text('TEST ZALICZONY'), findsOneWidget); // 4 poprawne >= próg 4
    expect(find.textContaining('4 / 6'), findsWidgets);
    expect(find.textContaining('2 błędnych pytań trafiło do powtórek'), findsOneWidget);

    await tester.runAsync(() async {
      final rows = await db.query('srs_cards', where: 'state = 3'); // relearning = w powtórce
      expect(rows.length, 2);
      final log = await db.query('review_log');
      expect(log.length, 2); // do dziennika trafiają tylko błędy testu
      await db.close();
    });
  });
}
