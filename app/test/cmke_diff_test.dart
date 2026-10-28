import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:memonic_app/data/cmke_diff.dart';
import 'package:memonic_app/data/database.dart';
import 'package:memonic_app/data/question_repository.dart';
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

  test('CmkeDiff.load wczytuje litery, a cmkeShownLetter uwzględnia losową kolejność odpowiedzi', () async {
    final db = await databaseFactoryFfi.openDatabase(inMemoryDatabasePath);
    await db.execute('CREATE TABLE cmke_diff (question_id INTEGER PRIMARY KEY, cmke_letter TEXT NOT NULL)');
    await db.insert('cmke_diff', {'question_id': 7, 'cmke_letter': 'c'});
    await CmkeDiff.load(db);
    expect(CmkeDiff.letters, {7: 'C'});
    final q = QuestionRow(id: 7, pytanie: 'p', poprawnaOdpowiedz: 'A', odpA: 'a', odpB: 'b', odpC: 'c', odpD: null);
    expect(q.cmkeDiff, isTrue);
    expect(q.cmkeShownLetter, 'C');
    final shuffled = QuestionRow(
        id: 7, pytanie: 'p', poprawnaOdpowiedz: 'B', odpA: 'c', odpB: 'a', odpC: 'b', odpD: null, letterMap: {'A': 'B', 'B': 'C', 'C': 'A'});
    expect(shuffled.cmkeShownLetter, 'A'); // oryginalne C wyświetlane jako A
    expect(QuestionRow(id: 8, pytanie: 'p', poprawnaOdpowiedz: 'A', odpA: 'a', odpB: 'b', odpC: 'c', odpD: null).cmkeDiff, isFalse);
    await db.close();
    CmkeDiff.letters = {};
  });

  testWidgets('NAUKA: żółte tło i ostrzeżenie; po odpowiedzi pomarańczowa etykieta „Odp. wg. CMKE” przy odpowiedzi z arkusza',
      (tester) async {
    SharedPreferences.setMockInitialValues({'shuffle_answers': false});
    late Database db;
    await tester.runAsync(() async {
      db = await databaseFactoryFfi.openDatabase(inMemoryDatabasePath);
      await db.execute(_questionsSql);
      await db.execute(_srsSql);
      await AppDatabase.migrateStudyStats(db);
      await db.execute('CREATE TABLE cmke_diff (question_id INTEGER PRIMARY KEY, cmke_letter TEXT NOT NULL)');
      await db.insert('cmke_diff', {'question_id': 1, 'cmke_letter': 'C'});
      await CmkeDiff.load(db);
      await db.insert('questions', {
        'id': 1, 'kategoria': 'Dział pokładowy', 'tematyka': 't', 'pytanie': 'Pytanie z różnicą',
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
    expect(find.text(CmkeDiff.banner), findsOneWidget);
    final card = tester.widget<Card>(find.ancestor(of: find.text('Pytanie z różnicą'), matching: find.byType(Card)).first);
    expect(card.color, CmkeDiff.background);
    expect(find.text(CmkeDiff.tag), findsNothing); // przed odpowiedzią etykiety nie ma

    await tester.tap(find.text('bbb')); // błędna odpowiedź
    await settle();
    expect(find.text(CmkeDiff.tag), findsOneWidget);
    // etykieta jest w wierszu odpowiedzi C (z arkusza)
    final row = find.ancestor(of: find.text(CmkeDiff.tag), matching: find.byType(Row)).first;
    expect(find.descendant(of: row, matching: find.text('ccc')), findsOneWidget);

    await tester.runAsync(() async {
      await db.close();
      CmkeDiff.letters = {};
    });
    await tester.pumpAndSettle(const Duration(seconds: 3));
  });
}
