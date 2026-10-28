import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:memonic_app/data/database.dart';
import 'package:memonic_app/data/db_transfer_service.dart';
import 'package:sqflite/sqflite.dart' show Sqflite;
import 'package:sqflite_common_ffi/sqflite_ffi.dart';
import 'package:sqlite3/sqlite3.dart' as s3;

void main() {
  sqfliteFfiInit();
  late Directory dir;
  late Database db;
  late String srcPath;

  const targetSchema = [
    '''CREATE TABLE questions (
      id INTEGER PRIMARY KEY, kategoria TEXT NOT NULL, podkategoria TEXT, poziom TEXT,
      tematyka TEXT NOT NULL, nr_pytania INTEGER, typ_pytania TEXT NOT NULL DEFAULT 'testowe',
      pytanie TEXT NOT NULL, odp_a TEXT, odp_b TEXT, odp_c TEXT, odp_d TEXT,
      poprawna_odpowiedz TEXT, poprawna_odpowiedz_tekst TEXT, zrodlo_pliku TEXT NOT NULL,
      review_status TEXT, review_notes TEXT, study_hidden INTEGER NOT NULL DEFAULT 0,
      ai_verified TEXT, image_path TEXT)''',
    '''CREATE TABLE srs_cards (question_id INTEGER PRIMARY KEY, repetitions INTEGER NOT NULL DEFAULT 0,
      interval_days INTEGER NOT NULL DEFAULT 0, ease_factor REAL NOT NULL DEFAULT 2.5,
      due_ms INTEGER NOT NULL, lapses INTEGER NOT NULL DEFAULT 0)''',
  ];

  Future<void> addQ(Database d, int id, String q,
      {String status = 'ok', int hidden = 0, String answer = 'A'}) async {
    await d.insert('questions', {
      'id': id, 'kategoria': 'Dział pokładowy', 'poziom': 'operacyjny', 'tematyka': 't',
      'pytanie': q, 'odp_a': 'aa $q', 'odp_b': 'bb', 'odp_c': 'cc',
      'poprawna_odpowiedz': answer, 'zrodlo_pliku': 'x.pdf',
      'review_status': status, 'study_hidden': hidden,
    });
    await d.insert('srs_cards', {'question_id': id, 'due_ms': 0});
  }

  void writeSource(List<List<Object?>> rows, {bool withHidden = true}) {
    final f = File(srcPath);
    if (f.existsSync()) f.deleteSync();
    final s = s3.sqlite3.open(srcPath);
    s.execute('''CREATE TABLE questions (
      id INTEGER PRIMARY KEY, kategoria TEXT, poziom TEXT, tematyka TEXT, pytanie TEXT,
      odp_a TEXT, odp_b TEXT, odp_c TEXT, odp_d TEXT, poprawna_odpowiedz TEXT,
      zrodlo_pliku TEXT, review_status TEXT${withHidden ? ', study_hidden INTEGER' : ''})''');
    for (final r in rows) {
      s.execute(
        'INSERT INTO questions (id,kategoria,poziom,tematyka,pytanie,odp_a,odp_b,odp_c,poprawna_odpowiedz,zrodlo_pliku,review_status'
        '${withHidden ? ',study_hidden' : ''}) VALUES (?,?,?,?,?,?,?,?,?,?,?${withHidden ? ',?' : ''})',
        [r[0], 'Dział pokładowy', 'operacyjny', 't', r[1], 'aa ${r[1]}', 'bb', 'cc', (r.length > 4 ? r[4] : 'A'), 'x.pdf', r[2],
          if (withHidden) r[3]],
      );
    }
    s.dispose();
  }

  setUp(() async {
    dir = await Directory.systemTemp.createTemp('dbt');
    srcPath = '${dir.path}/src.db';
    db = await databaseFactoryFfi.openDatabase('${dir.path}/t.db');
    for (final sql in targetSchema) {
      await db.execute(sql);
    }
  });
  tearDown(() async {
    await db.close();
    try {
      await dir.delete(recursive: true);
    } catch (_) {}
  });

  test('B: aktualizuje tylko statusy, nie dodaje pytań', () async {
    await addQ(db, 1, 'Pytanie jeden', status: 'ok');
    await addQ(db, 2, 'Pytanie dwa', status: 'ok');
    // id=1 -> error + Błąd, id=2 bez zmian, id=99 nieobecne
    writeSource([
      [1, 'Pytanie jeden', 'error', 1],
      [2, 'Pytanie dwa', 'ok', 0],
      [99, 'Zupelnie nowe', 'ok', 0],
    ]);
    final r = await DbTransferService(db).importStatuses(srcPath);
    expect(r.updated, 1);
    expect(r.unchanged, 1);
    expect(r.notFound, 1);
    expect(Sqflite.firstIntValue(await db.rawQuery('SELECT COUNT(*) FROM questions')), 2);
    final q1 = (await db.query('questions', where: 'id=1')).first;
    expect(q1['review_status'], 'error');
    expect(q1['study_hidden'], 1);
  });

  test('B: dopasowuje po treści, gdy id są inne', () async {
    await addQ(db, 5, 'Pytanie piec', status: 'ok');
    writeSource([[700, 'Pytanie piec', 'error', 0]]);
    final r = await DbTransferService(db).importStatuses(srcPath);
    expect(r.updated, 1);
    expect((await db.query('questions', where: 'id=5')).first['review_status'], 'error');
  });

  test('C: dodaje tylko nieobecne pytania, ze statusami i kartą SRS', () async {
    await addQ(db, 1, 'Pytanie jeden');
    writeSource([
      [1, 'Pytanie jeden', 'ok', 0],
      [50, 'Nowe pytanie', 'error', 1],
      [51, 'Nowe ok', 'ok', 0, 'B'],
    ]);
    final r = await DbTransferService(db).importMissing(srcPath);
    expect(r.added, 2);
    expect(r.skipped, 1);
    final rows = await db.query('questions', orderBy: 'id');
    expect(rows.length, 3);
    final nowe = rows.firstWhere((x) => x['pytanie'] == 'Nowe pytanie');
    expect(nowe['id'], 2); // kolejny wolny id
    expect(nowe['review_status'], 'error');
    expect(nowe['study_hidden'], 1);
    expect(Sqflite.firstIntValue(await db.rawQuery('SELECT COUNT(*) FROM srs_cards')), 3);
    // ponowny import nie duplikuje
    final r2 = await DbTransferService(db).importMissing(srcPath);
    expect(r2.added, 0);
  });

  test('D: aktualizuje treść/klucz, dodaje nowe z ID, zachowuje postęp i „Błąd”', () async {
    await addQ(db, 1, 'Pytanie jeden', answer: 'A', hidden: 1);
    await addQ(db, 2, 'Pytanie dwa');
    await addQ(db, 3, 'Tylko u mnie');
    await db.update('srs_cards', {'repetitions': 5, 'interval_days': 12}, where: 'question_id = 1');
    await db.execute('CREATE TABLE explanation_cache (question_id INTEGER NOT NULL, content_hash TEXT NOT NULL, '
        'explanation TEXT NOT NULL, model TEXT NOT NULL, created_at_ms INTEGER NOT NULL, PRIMARY KEY (question_id, content_hash))');
    writeSource([
      [1, 'Pytanie jeden', 'ok', 0, 'B'], // zmieniony klucz; lokalnie oznaczone „Błąd” — zostaje
      [2, 'Pytanie dwa', 'ok', 0, 'A'], // bez zmian
      [50, 'Nowe pytanie', 'ok', 0, 'C'],
    ]);
    final s = s3.sqlite3.open(srcPath);
    s.execute('CREATE TABLE explanation_cache (question_id INTEGER NOT NULL, content_hash TEXT NOT NULL, '
        'explanation TEXT NOT NULL, model TEXT NOT NULL, created_at_ms INTEGER NOT NULL, PRIMARY KEY (question_id, content_hash))');
    s.execute("INSERT INTO explanation_cache VALUES (1, 'h1', 'Prawidłowa odpowiedź to B. ...', 'm', 1)");
    s.execute("INSERT INTO explanation_cache VALUES (999, 'h9', 'obce', 'm', 1)");
    s.execute('CREATE TABLE ai_disputed (question_id INTEGER PRIMARY KEY)');
    s.execute('INSERT INTO ai_disputed VALUES (50)');
    s.dispose();

    final r = await DbTransferService(db).updateKeepProgress(srcPath);
    expect(r.added, 1);
    expect(r.updated, 1);
    expect(r.keyChanged, 1);
    expect(r.unchanged, 1);
    expect(r.notInSource, 1); // id 3 zostaje, nic nie jest usuwane
    final q1 = (await db.query('questions', where: 'id=1')).first;
    expect(q1['poprawna_odpowiedz'], 'B');
    expect(q1['study_hidden'], 1); // oznaczenie użytkownika zachowane
    final card = (await db.query('srs_cards', where: 'question_id=1')).first;
    expect(card['repetitions'], 5); // postęp nauki zachowany
    expect(card['interval_days'], 12);
    final q50 = (await db.query('questions', where: 'id=50')).first; // nowe pytanie z własnym ID
    expect(q50['poprawna_odpowiedz'], 'C');
    expect(Sqflite.firstIntValue(await db.rawQuery('SELECT COUNT(*) FROM srs_cards')), 4);
    expect(Sqflite.firstIntValue(await db.rawQuery('SELECT COUNT(*) FROM questions')), 4);
    // wyjaśnienia: tylko dla pytań istniejących w bazie
    expect(Sqflite.firstIntValue(await db.rawQuery('SELECT COUNT(*) FROM explanation_cache')), 1);
    expect(Sqflite.firstIntValue(await db.rawQuery('SELECT COUNT(*) FROM ai_disputed WHERE question_id = 50')), 1);
    // ponowny import nic nie zmienia
    final r2 = await DbTransferService(db).updateKeepProgress(srcPath);
    expect(r2.added + r2.updated, 0);
  });

  test('D: plik z inną numeracją ID jest odrzucany (nie nadpisuje cudzych pytań)', () async {
    for (var i = 1; i <= 6; i++) {
      await addQ(db, i, 'Zupelnie inna tresc numer $i abc');
    }
    writeSource([for (var i = 1; i <= 6; i++) [i, 'Calkiem odmienne zagadnienie ${i * 7919} xyz', 'ok', 0, 'B']]);
    await expectLater(DbTransferService(db).updateKeepProgress(srcPath), throwsA(isA<ImportSourceException>()));
    expect((await db.query('questions', where: 'id=1')).first['poprawna_odpowiedz'], 'A');
  });

  test('inspectSource odrzuca plik bez tabeli questions', () {
    final s = s3.sqlite3.open(srcPath);
    s.execute('CREATE TABLE inna (x INTEGER)');
    s.dispose();
    expect(() => DbTransferService.inspectSource(srcPath), throwsA(isA<ImportSourceException>()));
  });

  test('A: normalizeFile uzupełnia schemat obcej bazy (user_version 3, SRS)', () {
    writeSource([[1, 'P1', 'ok', null], [2, 'P2', 'ok', null]], withHidden: false);
    DbTransferService.normalizeFile(srcPath);
    final s = s3.sqlite3.open(srcPath);
    expect(s.select('PRAGMA user_version').first.values.first, 3);
    expect(s.select('SELECT COUNT(*) c FROM srs_cards').first['c'], 2);
    final cols = s.select('PRAGMA table_info(questions)').map((r) => r['name']).toSet();
    expect(cols, containsAll(['study_hidden', 'ai_verified']));
    s.dispose();
  });

  test('C: pytania o identycznej treści, różniące się obrazkiem, to różne pytania', () async {
    final f = File(srcPath);
    final s = s3.sqlite3.open(srcPath);
    s.execute('''CREATE TABLE questions (
      id INTEGER PRIMARY KEY, kategoria TEXT, poziom TEXT, tematyka TEXT, pytanie TEXT,
      odp_a TEXT, odp_b TEXT, odp_c TEXT, odp_d TEXT, poprawna_odpowiedz TEXT,
      zrodlo_pliku TEXT, review_status TEXT, image_path TEXT)''');
    for (final (i, img) in [(1, 'a.png'), (2, 'b.png')]) {
      s.execute(
        'INSERT INTO questions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
        [i, 'Dział pokładowy', 'operacyjny', 't', 'Flaga oznacza:', 'x', 'y', 'z', null, 'A', 'x.pdf', 'ok', img],
      );
    }
    s.dispose();
    expect(f.existsSync(), isTrue);
    final r = await DbTransferService(db).importMissing(srcPath);
    expect(r.added, 2);
    final rows = await db.query('questions', orderBy: 'id');
    expect(rows.map((x) => x['image_path']), ['a.png', 'b.png']);
    expect((await DbTransferService(db).importMissing(srcPath)).added, 0);
  });

  test('migrateImagePath dodaje kolumnę i jest idempotentna', () async {
    final d = await databaseFactoryFfi.openDatabase('${dir.path}/old.db');
    await d.execute('CREATE TABLE questions (id INTEGER PRIMARY KEY, pytanie TEXT)');
    await AppDatabase.migrateImagePath(d);
    await AppDatabase.migrateImagePath(d);
    final cols = (await d.rawQuery('PRAGMA table_info(questions)')).map((c) => c['name']);
    expect(cols.where((c) => c == 'image_path').length, 1);
    await d.close();
  });
}
