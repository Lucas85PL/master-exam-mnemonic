import 'package:flutter_test/flutter_test.dart';
import 'package:memonic_app/data/database.dart';
import 'package:memonic_app/data/duplicate_groups.dart';
import 'package:memonic_app/data/question_repository.dart';
import 'package:memonic_app/domain/category_filter.dart';
import 'package:memonic_app/domain/fsrs.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

void main() {
  sqfliteFfiInit();
  late Database db;
  late QuestionRepository repo;
  final s = FsrsScheduler();
  final now = DateTime(2026, 10, 9, 12);

  Future<void> q(int id, String kat, String text, {String a = 'x', String? image}) async {
    await db.insert('questions', {
      'id': id, 'kategoria': kat, 'tematyka': 't', 'pytanie': text, 'odp_a': a, 'odp_b': 'y', 'odp_c': 'z',
      'poprawna_odpowiedz': 'A', 'zrodlo_pliku': 'x', 'review_status': 'ok', 'study_hidden': 0, 'image_path': image,
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
    const master = 'Kapitan żeglugi wielkiej';
    const poklad = 'Dział pokładowy';
    await q(1, master, 'Określenie „statek o ograniczonej zdolności manewrowej” oznacza statek:');
    await q(2, master, 'Określenie "statek o ograniczonej zdolności manewrowej" oznacza statek:'); // inne cudzysłowy = ta sama treść
    await q(3, poklad, 'Określenie „statek o ograniczonej zdolności manewrowej” oznacza statek:'); // inny dział
    await q(4, master, 'Zupełnie inne pytanie');
    await q(5, poklad, 'Flaga oznacza:', image: 'a.png');
    await q(6, poklad, 'Flaga oznacza:', image: 'b.png'); // ten sam tekst, inny obrazek = inne pytanie
    await DuplicateGroups.refresh(db);
  });
  tearDown(() => db.close());

  Future<Map<int, Map<String, Object?>>> cards() async =>
      {for (final r in await db.query('srs_cards')) r['question_id'] as int: r};

  test('grupy: ta sama treść niezależnie od ID/działu/cudzysłowów; inny obrazek = inne pytanie', () async {
    final g = {for (final r in await db.query('questions')) r['id'] as int: r['dup_group']};
    expect(g[1], isNotNull);
    expect(g[1], g[2]);
    expect(g[1], g[3]);
    expect(g[4], isNull);
    expect(g[5], isNull);
    expect(g[6], isNull);
    expect(await DuplicateGroups.refresh(db), 0); // idempotentne
  });

  test('odpowiedź na jedną kopię ustawia ten sam harmonogram w pozostałych; kopia nie wraca do kolejki', () async {
    final card = FsrsCard(questionId: 1);
    final updated = s.review(card, Rating.good, now);
    await repo.saveSrs(updated);
    await repo.recordAnswer(questionId: 1, correct: true, rating: 3, lapses: 0, now: now);
    final c = await cards();
    for (final id in [2, 3]) {
      expect(c[id]!['state'], c[1]!['state']);
      expect(c[id]!['due_ms'], c[1]!['due_ms']);
      expect(c[id]!['streak_days'], 1);
      expect(c[id]!['last_good_day'], c[1]!['last_good_day']);
    }
    expect(c[4]!['state'], 0); // nie-duplikat bez zmian
    // kopie (2, 3) nie są już „nowe”; zostały tylko pytania 4, 5, 6
    expect(await repo.countNew(StudyCategory.all), 3);
  });

  test('statystyki liczą unikalne pytania: pula, nowe, znane, brakująca praca', () async {
    expect(await repo.countStudyPool(StudyCategory.all), 4); // {1,2,3}, 4, 5, 6
    expect(await repo.countStudyPool(StudyCategory.master), 2); // {1,2}, 4
    expect(await repo.countStudyPool(StudyCategory.poklad), 3); // 3, 5, 6
    expect(await repo.countRemainingReviews(StudyCategory.all), 12);
    for (var d = 0; d < 3; d++) {
      await repo.saveSrs(s.review(FsrsCard(questionId: 1), Rating.good, now.add(Duration(days: d * 2))));
      await repo.recordAnswer(
          questionId: 1, correct: true, rating: 3, lapses: 0, now: now.add(Duration(days: d * 2)));
    }
    expect(await repo.countKnown(StudyCategory.all), 1); // grupa {1,2,3} liczy się raz
    expect(await repo.countRemainingReviews(StudyCategory.all), 9);
  });

  test('wyrównanie istniejącego postępu: najnowsza powtórka wyznacza termin, seria = najwyższa, trudne = suma', () async {
    // kopia 1: seria 2, powtórzona wcześniej; kopia 2: seria 1, powtórzona później i oznaczona jako trudna
    await db.update('srs_cards',
        {'state': 2, 'due_ms': 1000, 'last_review_ms': 100, 'streak_days': 2, 'last_good_day': 50, 'repetitions': 3},
        where: 'question_id = 1');
    await db.update('srs_cards',
        {'state': 2, 'due_ms': 9000, 'last_review_ms': 900, 'streak_days': 1, 'last_good_day': 60, 'hard': 1, 'lapses': 2},
        where: 'question_id = 2');
    final n = await DuplicateGroups.align(db);
    expect(n, greaterThan(0));
    final c = await cards();
    for (final id in [1, 2, 3]) {
      expect(c[id]!['due_ms'], 9000);
      expect(c[id]!['streak_days'], 2);
      expect(c[id]!['last_good_day'], 50);
      expect(c[id]!['hard'], 1);
      expect(c[id]!['lapses'], 2);
    }
    expect(await DuplicateGroups.align(db), 0); // po wyrównaniu nic do zmiany
  });

  test('edycja treści odłącza pytanie od grupy', () async {
    await repo.updateQuestion(3, {'pytanie': 'Inna treść po edycji'});
    final g = {for (final r in await db.query('questions')) r['id'] as int: r['dup_group']};
    expect(g[3], isNull);
    expect(g[1], isNotNull);
    expect(g[1], g[2]);
  });

  test('powiązania dup_links łączą pytania o nieidentycznym zapisie (np. błąd OCR); usunięte pytanie jest ignorowane', () async {
    await q(7, 'Dział pokładowy', 'Pytanie z błędem OCR o statku', a: 'wariant jeden');
    await q(8, 'Kapitan żeglugi wielkiej', 'Pytanie z bledem 0CR o statku', a: 'wariant jedn');
    await DuplicateGroups.refresh(db);
    var g = {for (final r in await db.query('questions')) r['id'] as int: r['dup_group']};
    expect(g[7], isNull);
    expect(g[7] == g[8], isTrue); // oba NULL = brak grupy
    await db.insert('dup_links', {'question_id': 8, 'canonical_id': 7, 'source': 'test'});
    await db.insert('dup_links', {'question_id': 99, 'canonical_id': 7, 'source': 'test'}); // nieistniejące
    await DuplicateGroups.refresh(db);
    g = {for (final r in await db.query('questions')) r['id'] as int: r['dup_group']};
    expect(g[7], isNotNull);
    expect(g[7], g[8]);
    expect(g[7], isNot(g[1])); // inna grupa niż pytania 1-3
    // synchronizacja działa także dla powiązań
    await repo.saveSrs(s.review(FsrsCard(questionId: 8), Rating.good, now));
    final c = await cards();
    expect(c[7]!['state'], c[8]!['state']);
    expect(c[7]!['due_ms'], c[8]!['due_ms']);
  });

  test('TEST nie losuje dwóch pytań z jednej grupy powiązań', () async {
    await q(7, 'Dział pokładowy', 'Pytanie z błędem OCR o statku', a: 'wariant jeden');
    await q(8, 'Kapitan żeglugi wielkiej', 'Pytanie z bledem 0CR o statku', a: 'wariant jedn');
    await db.insert('dup_links', {'question_id': 8, 'canonical_id': 7, 'source': 'test'});
    await DuplicateGroups.refresh(db);
    for (var run = 0; run < 15; run++) {
      final picked = await repo.pickTestQuestions(
          [StudyCategory.master, StudyCategory.angielski, StudyCategory.poklad], [10, 0, 10], [50, 0, 50]);
      expect(picked.where((x) => x.id == 7 || x.id == 8).length, lessThanOrEqualTo(1), reason: 'przebieg $run');
      final groups = picked.map((x) => x.dupGroup).whereType<String>().toList();
      expect(groups.toSet().length, groups.length); // żadna grupa dwa razy
    }
  });
}
