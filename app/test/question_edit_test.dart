import 'package:flutter_test/flutter_test.dart';
import 'package:memonic_app/data/ai_disputed.dart';
import 'package:memonic_app/data/database.dart';
import 'package:memonic_app/data/duplicate_groups.dart';
import 'package:memonic_app/data/question_categories.dart';
import 'package:memonic_app/data/question_repository.dart';
import 'package:memonic_app/domain/category_filter.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

void main() {
  sqfliteFfiInit();
  late Database db;
  late QuestionRepository repo;

  Future<void> q(int id, String text) async {
    await db.insert('questions', {
      'id': id, 'kategoria': 'Kapitan żeglugi wielkiej', 'tematyka': 't', 'pytanie': text, 'odp_a': 'tak', 'odp_b': 'nie',
      'odp_c': 'czasem', 'poprawna_odpowiedz': 'A', 'poprawna_odpowiedz_tekst': 'tak', 'zrodlo_pliku': 'x', 'review_status': 'ok',
    });
  }

  setUp(() async {
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
    await QuestionCategories.ensure(db);
    repo = QuestionRepository(db);
    await q(1, 'Pytanie o kapitana:');
    await q(2, 'Pytanie o kapitana:'); // kopia 1
    await q(3, 'Zupełnie inne pytanie');
    await DuplicateGroups.refresh(db);
  });
  tearDown(() => db.close());

  test('zmiana klucza aktualizuje tekst poprawnej odpowiedzi i znacznik ręcznej edycji', () async {
    await repo.updateQuestion(3, {'poprawna_odpowiedz': 'b'});
    final r = (await repo.getQuestionById(3))!;
    expect(r['poprawna_odpowiedz'], 'B');
    expect(r['poprawna_odpowiedz_tekst'], 'nie');
    expect(r['ai_verified'], startsWith('manual:app_edit:'));
    await repo.updateQuestion(3, {'odp_b': 'nigdy'});
    expect((await repo.getQuestionById(3))!['poprawna_odpowiedz_tekst'], 'nigdy');
  });

  test('działy: uzupełnienie wg dotychczasowej kategorii, wiele działów, pula dwóch działów, co najmniej jeden', () async {
    await db.insert('questions', {
      'id': 4, 'kategoria': 'Dział pokładowy', 'tematyka': 't', 'pytanie': 'Pytanie pokładowe', 'odp_a': 'a', 'odp_b': 'b',
      'poprawna_odpowiedz': 'A', 'zrodlo_pliku': 'x', 'review_status': 'ok',
    });
    await db.insert('srs_cards', {'question_id': 4, 'due_ms': 0, 'state': 0});
    await db.insert('srs_cards', {'question_id': 3, 'due_ms': 0, 'state': 0});
    await QuestionCategories.ensure(db);
    expect(await repo.categoriesOf(3), ['Kapitan żeglugi wielkiej']);
    expect(await repo.categoriesOf(4), ['Dział pokładowy']);
    expect(await repo.countStudyPool(StudyCategory.poklad), 1);
    expect(await repo.countStudyPool(StudyCategory.master), 1);

    await repo.setCategories(3, {'Kapitan żeglugi wielkiej', 'Dział pokładowy'}); // 3 trafia też do Pokładu
    expect(await repo.categoriesOf(3), ['Kapitan żeglugi wielkiej', 'Dział pokładowy']);
    expect(await repo.countStudyPool(StudyCategory.poklad), 2);
    expect(await repo.countStudyPool(StudyCategory.master), 1);
    expect(await repo.countStudyPool(StudyCategory.all), 2);
    expect((await repo.listAllQuestions(category: StudyCategory.poklad)).map((e) => e.id), [3, 4]);
    expect((await repo.listAllQuestions(category: StudyCategory.master)).firstWhere((e) => e.id == 3).kategorieLabel, 'Master + Pokład');

    await repo.setCategories(3, {'Dział pokładowy'}); // usunięcie działu głównego: główny zmienia się na wybrany
    expect((await repo.getQuestionById(3))!['kategoria'], 'Dział pokładowy');
    expect(await repo.countStudyPool(StudyCategory.master), 0);
    await repo.setCategories(3, {}); // pusty wybór jest ignorowany
    expect(await repo.categoriesOf(3), ['Dział pokładowy']);
  });

  test('„Niepewne” oznacza pytanie i jego kopie; wyłączenie zdejmuje oznaczenie', () async {
    expect(AiDisputed.ids, isEmpty);
    await repo.setUncertain(1, true);
    expect(AiDisputed.ids, {1, 2});
    expect((await db.query('ai_disputed')).length, 2);
    await repo.setUncertain(2, false);
    expect(AiDisputed.ids, isEmpty);
    expect(await db.query('ai_disputed'), isEmpty);
    await repo.setUncertain(3, true);
    expect(AiDisputed.ids, {3});
    expect((await repo.listAllQuestions(onlyUncertain: true)).map((e) => e.id), [3]); // filtr „Tylko niepewne”
    expect(await repo.countAllQuestions(onlyUncertain: true), 1);
    expect(await repo.countAllQuestions(), 3);
  });
}
