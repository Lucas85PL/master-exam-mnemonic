import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:memonic_app/data/ai_disputed.dart';
import 'package:memonic_app/data/database.dart';
import 'package:memonic_app/data/question_repository.dart';
import 'package:memonic_app/features/study/study_screen.dart';
import 'package:memonic_app/providers/app_providers.dart';
import 'package:memonic_app/widgets/uncertain_banner.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

void main() {
  sqfliteFfiInit();

  testWidgets('NAUKA: niepewne pytanie ma czerwoną, pogrubioną wzmiankę; po wyłączeniu „Niepewne” znika', (tester) async {
    SharedPreferences.setMockInitialValues({});
    late Database db;
    await tester.runAsync(() async {
      db = await databaseFactoryFfi.openDatabase(inMemoryDatabasePath);
      await db.execute('''CREATE TABLE questions (id INTEGER PRIMARY KEY, kategoria TEXT, podkategoria TEXT,
        poziom TEXT, tematyka TEXT, nr_pytania INTEGER, typ_pytania TEXT DEFAULT 'testowe', pytanie TEXT,
        odp_a TEXT, odp_b TEXT, odp_c TEXT, odp_d TEXT, poprawna_odpowiedz TEXT, poprawna_odpowiedz_tekst TEXT,
        zrodlo_pliku TEXT, review_status TEXT, review_notes TEXT, study_hidden INTEGER DEFAULT 0, image_path TEXT,
        ai_verified TEXT)''');
      await db.execute('''CREATE TABLE srs_cards (question_id INTEGER PRIMARY KEY, repetitions INTEGER DEFAULT 0,
        interval_days INTEGER DEFAULT 0, ease_factor REAL DEFAULT 2.5, due_ms INTEGER NOT NULL, lapses INTEGER DEFAULT 0,
        state INTEGER NOT NULL DEFAULT 0, step INTEGER NOT NULL DEFAULT 0, stability REAL, difficulty REAL,
        last_review_ms INTEGER)''');
      await AppDatabase.migrateStudyStats(db);
      await AiDisputed.load(db);
      await db.insert('questions', {
        'id': 1, 'kategoria': 'Dział pokładowy', 'tematyka': 't', 'pytanie': 'Pytanie niepewne', 'odp_a': 'aaa', 'odp_b': 'bbb',
        'odp_c': 'ccc', 'poprawna_odpowiedz': 'A', 'zrodlo_pliku': 'x', 'review_status': 'ok', 'study_hidden': 0,
      });
      await db.insert('srs_cards', {'question_id': 1, 'due_ms': 0, 'state': 0});
      await QuestionRepository(db).setUncertain(1, true);
    });

    await tester.pumpWidget(ProviderScope(
      overrides: [databaseProvider.overrideWith((ref) async => db)],
      child: const MaterialApp(home: StudyScreen()),
    ));
    await tester.runAsync(() => Future<void>.delayed(const Duration(milliseconds: 600)));
    await tester.pump();
    await tester.pump();

    final banner = find.byKey(const ValueKey('uncertain-banner'));
    expect(banner, findsOneWidget);
    final text = tester.widget<Text>(banner);
    expect(text.data, 'Odpowiedź niepewna! (Jeśli znasz odp. to edytuj pytanie w Bazie Pytań w apce.)');
    expect(text.style!.fontWeight, FontWeight.bold);
    expect(text.style!.color, const Color(0xFFC62828));

    // wyłączenie „Niepewne” w Bazie Pytań => znacznik znika z pamięci, więc wzmianka nie pojawia się przy kolejnym wyświetleniu
    await tester.runAsync(() => QuestionRepository(db).setUncertain(1, false));
    expect(AiDisputed.ids.contains(1), isFalse);
    await tester.pumpWidget(const SizedBox());
    await tester.pumpWidget(ProviderScope(
      overrides: [databaseProvider.overrideWith((ref) async => db)],
      child: const MaterialApp(home: StudyScreen()),
    ));
    await tester.runAsync(() => Future<void>.delayed(const Duration(milliseconds: 600)));
    await tester.pump();
    await tester.pump();
    expect(find.text('Pytanie niepewne'), findsOneWidget);
    expect(find.byType(UncertainBanner), findsNothing);
  });
}
