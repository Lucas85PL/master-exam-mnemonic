import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:memonic_app/data/database.dart';
import 'package:memonic_app/data/question_repository.dart';
import 'package:memonic_app/domain/category_filter.dart';
import 'package:memonic_app/features/home/home_screen.dart';
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

Future<Database> _db() async {
  final db = await databaseFactoryFfi.openDatabase(inMemoryDatabasePath);
  await db.execute(_questionsSql);
  await db.execute(_srsSql);
  await AppDatabase.migrateStudyStats(db);
  var id = 1;
  for (final (kat, n) in [('Kapitan żeglugi wielkiej', 2), ('Angielski', 3), ('Dział pokładowy', 4)]) {
    for (var i = 0; i < n; i++, id++) {
      await db.insert('questions', {
        'id': id, 'kategoria': kat, 'tematyka': 't', 'pytanie': 'Pytanie $id', 'odp_a': 'a$id', 'odp_b': 'b$id', 'odp_c': 'c$id',
        'poprawna_odpowiedz': 'A', 'zrodlo_pliku': 'x', 'review_status': 'ok', 'study_hidden': 0,
      });
      await db.insert('srs_cards', {'question_id': id, 'due_ms': 0, 'state': 0});
    }
  }
  return db;
}

void main() {
  sqfliteFfiInit();

  test('fromSelected: złożony filtr z zaznaczonych działów, pusty zbiór = wszystkie', () {
    final mp = StudyCategory.fromSelected({'Kapitan żeglugi wielkiej', 'Dział pokładowy'});
    expect(mp.values, ['Kapitan żeglugi wielkiej', 'Dział pokładowy']); // kolejność jak w selectable
    expect(mp.label, 'Master + Pokład');
    expect(StudyCategory.fromSelected({}).isAll, isTrue);
    expect(StudyCategory.fromSelected({'Angielski'}).dbValue, 'Angielski');
    expect(StudyCategory.fromSelected({'Angielski', 'Kapitan żeglugi wielkiej'}).dbValue, isNull);
  });

  test('repozytorium: pula, nowe i zaległe liczone tylko dla zaznaczonych działów', () async {
    final db = await _db();
    final repo = QuestionRepository(db);
    final mp = StudyCategory.fromSelected({'Kapitan żeglugi wielkiej', 'Dział pokładowy'});
    expect(await repo.countStudyPool(mp), 6); // 2 + 4
    expect(await repo.countStudyPool(StudyCategory.fromSelected({'Angielski'})), 3);
    expect(await repo.countStudyPool(StudyCategory.all), 9);
    expect(await repo.countNew(mp), 6);
    for (var i = 0; i < 20; i++) {
      final row = await repo.fetchNextCard(mp);
      expect(['Kapitan żeglugi wielkiej', 'Dział pokładowy'], contains(row!['kategoria']));
    }
    expect(await repo.countAnswersOnDay(1, category: mp), 0);
    await db.close();
  });

  testWidgets('EKRAN GŁÓWNY: trzy pola wyboru w jednej linii; statystyki dla zaznaczonych; ostatniego nie da się odznaczyć', (tester) async {
    SharedPreferences.setMockInitialValues({});
    late Database db;
    await tester.runAsync(() async => db = await _db());
    await tester.pumpWidget(ProviderScope(
      overrides: [databaseProvider.overrideWith((ref) async => db)],
      child: const MaterialApp(home: HomeScreen()),
    ));
    Future<void> settle() async {
      for (var i = 0; i < 30; i++) {
        await tester.runAsync(() => Future<void>.delayed(const Duration(milliseconds: 150)));
        await tester.pump();
        if (i > 1 && find.byType(CircularProgressIndicator).evaluate().isEmpty) break;
      }
      await tester.pump();
    }

    await settle();
    expect(find.byType(DropdownButtonFormField<StudyCategory>), findsNothing); // dropdown usunięty
    expect(find.byType(Checkbox), findsNWidgets(3));
    for (final l in ['Master', 'Angielski', 'Pokład']) {
      expect(find.text(l), findsOneWidget);
    }
    expect(find.text('All'), findsNothing);
    // w jednej linii: te same współrzędne y
    final ys = [for (final l in ['Master', 'Angielski', 'Pokład']) tester.getCenter(find.text(l)).dy];
    expect((ys[0] - ys[1]).abs() < 2 && (ys[1] - ys[2]).abs() < 2, isTrue);
    expect(find.text('Pula (OK): 9'), findsOneWidget); // domyślnie wszystkie trzy zaznaczone

    await tester.tap(find.byKey(const ValueKey('cat-Angielski')));
    await settle();
    expect(find.text('Pula (OK): 6'), findsOneWidget); // bez Angielskiego: 2 + 4

    await tester.tap(find.byKey(const ValueKey('cat-Pokład')));
    await settle();
    expect(find.text('Pula (OK): 2'), findsOneWidget); // tylko Master

    await tester.tap(find.byKey(const ValueKey('cat-Master'))); // ostatni zaznaczony — nie da się odznaczyć
    await settle();
    expect(find.text('Pula (OK): 2'), findsOneWidget);
    expect(find.text('Zostaw zaznaczony co najmniej jeden dział'), findsOneWidget);
    await tester.runAsync(() => db.close());
  });
}
