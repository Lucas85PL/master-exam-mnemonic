import 'dart:convert';

import 'package:crypto/crypto.dart';
import 'package:sqflite/sqflite.dart';

/// Powtórzone pytania: ta sama treść (pytanie + warianty A–D + obrazek) bywa w bazie w kilku wierszach
/// (inne ID, inny poziom/dział, kolejne wersje arkuszy). Takie wiersze tworzą **grupę** (`questions.dup_group`),
/// a ich harmonogram nauki jest zsynchronizowany: odpowiedź lub odłożenie jednego wiersza ustawia ten sam
/// stan karty (FSRS, seria, „trudne”) w pozostałych — pytanie nie wraca tego samego dnia pod innym ID,
/// a statystyki liczą unikalne pytania.
class DuplicateGroups {
  /// Kolumny karty SRS kopiowane między wierszami grupy.
  static const syncColumns = [
    'repetitions', 'interval_days', 'ease_factor', 'due_ms', 'lapses', 'state', 'step',
    'stability', 'difficulty', 'last_review_ms', 'streak_days', 'last_good_day', 'hard',
  ];

  static String _norm(Object? s) =>
      (s?.toString() ?? '').toLowerCase().replaceAll(RegExp(r'[^\p{L}\p{N}]+', unicode: true), '');

  /// Klucz treści pytania (bez ID, poziomu i działu).
  static String contentKey(Map<String, Object?> row) => [
        row['pytanie'], row['odp_a'], row['odp_b'], row['odp_c'], row['odp_d'], row['image_path'],
      ].map(_norm).join('|');

  /// Dodaje kolumnę `dup_group` (idempotentnie).
  static Future<void> ensureColumn(Database db) async {
    final cols = (await db.rawQuery('PRAGMA table_info(questions)')).map((c) => c['name'] as String).toSet();
    if (!cols.contains('dup_group')) {
      await db.execute('ALTER TABLE questions ADD COLUMN dup_group TEXT');
    }
    await db.execute('CREATE INDEX IF NOT EXISTS idx_questions_dup ON questions(dup_group)');
    // ręczne/AI-potwierdzone powiązania powtórzeń o nieidentycznym zapisie (np. błędy OCR): pytanie → pytanie kanoniczne
    await db.execute('''
      CREATE TABLE IF NOT EXISTS dup_links (
        question_id INTEGER PRIMARY KEY,
        canonical_id INTEGER NOT NULL,
        source TEXT
      )
    ''');
  }

  /// Przelicza grupy powtórzeń (po imporcie, edycji, dodaniu pytań). Zwraca liczbę zmienionych wierszy.
  static Future<int> refresh(Database db) async {
    await ensureColumn(db);
    final rows = await db.rawQuery(
        'SELECT id, pytanie, odp_a, odp_b, odp_c, odp_d, image_path, dup_group FROM questions');
    // union-find: wiersze o identycznej treści + powiązania z tabeli dup_links
    final parent = <int, int>{for (final r in rows) r['id'] as int: r['id'] as int};
    int find(int x) {
      while (parent[x] != x) {
        parent[x] = parent[parent[x]]!;
        x = parent[x]!;
      }
      return x;
    }

    void union(int a, int b) {
      if (!parent.containsKey(a) || !parent.containsKey(b)) return; // powiązanie z usuniętym pytaniem
      final ra = find(a), rb = find(b);
      if (ra != rb) parent[rb < ra ? ra : rb] = rb < ra ? rb : ra; // korzeń = najmniejsze ID
    }

    final byKey = <String, List<int>>{};
    for (final r in rows) {
      byKey.putIfAbsent(contentKey(r), () => []).add(r['id'] as int);
    }
    for (final ids in byKey.values) {
      for (final id in ids.skip(1)) {
        union(ids.first, id);
      }
    }
    for (final l in await db.query('dup_links')) {
      union(l['question_id'] as int, l['canonical_id'] as int);
    }
    final members = <int, List<int>>{};
    for (final id in parent.keys) {
      members.putIfAbsent(find(id), () => []).add(id);
    }
    final target = <int, String?>{};
    members.forEach((root, ids) {
      final g = ids.length > 1 ? md5.convert(utf8.encode('g$root')).toString().substring(0, 12) : null;
      for (final id in ids) {
        target[id] = g;
      }
    });
    final batch = db.batch();
    var changed = 0;
    for (final r in rows) {
      final id = r['id'] as int;
      if (r['dup_group'] != target[id]) {
        batch.update('questions', {'dup_group': target[id]}, where: 'id = ?', whereArgs: [id]);
        changed++;
      }
    }
    if (changed > 0) await batch.commit(noResult: true);
    return changed;
  }

  /// Ujednolica stan nauki w grupach: karta z najnowszą powtórką wyznacza harmonogram, seria = najwyższa w grupie,
  /// „trudne” i liczba błędów = maksimum. Zwraca liczbę zaktualizowanych kart.
  static Future<int> align(Database db) async {
    final rows = await db.rawQuery('''
      SELECT q.dup_group AS g, s.* FROM srs_cards s
      INNER JOIN questions q ON q.id = s.question_id
      WHERE q.dup_group IS NOT NULL
      ORDER BY q.dup_group
    ''');
    final groups = <String, List<Map<String, Object?>>>{};
    for (final r in rows) {
      groups.putIfAbsent(r['g'] as String, () => []).add(r);
    }
    final batch = db.batch();
    var updated = 0;
    for (final cards in groups.values) {
      final base = cards.reduce((a, b) =>
          ((b['last_review_ms'] as int?) ?? -1) > ((a['last_review_ms'] as int?) ?? -1) ? b : a);
      final bestStreak = cards.reduce((a, b) {
        final sa = (a['streak_days'] as int?) ?? 0, sb = (b['streak_days'] as int?) ?? 0;
        if (sb != sa) return sb > sa ? b : a;
        return ((b['last_good_day'] as int?) ?? -1) > ((a['last_good_day'] as int?) ?? -1) ? b : a;
      });
      final target = <String, Object?>{
        for (final c in syncColumns) c: base[c],
        'streak_days': bestStreak['streak_days'],
        'last_good_day': bestStreak['last_good_day'],
        'hard': cards.any((c) => (c['hard'] as int?) == 1) ? 1 : 0,
        'lapses': cards.map((c) => (c['lapses'] as int?) ?? 0).reduce((a, b) => a > b ? a : b),
      };
      for (final c in cards) {
        if (syncColumns.any((col) => c[col] != target[col])) {
          batch.update('srs_cards', target, where: 'question_id = ?', whereArgs: [c['question_id']]);
          updated++;
        }
      }
    }
    if (updated > 0) await batch.commit(noResult: true);
    return updated;
  }

  /// Kopiuje stan karty [questionId] do pozostałych wierszy jej grupy (wywoływane po każdym zapisie karty).
  static Future<void> syncFrom(Database db, int questionId) async {
    final g = await db.rawQuery('SELECT dup_group FROM questions WHERE id = ?', [questionId]);
    final group = g.isEmpty ? null : g.first['dup_group'] as String?;
    if (group == null) return;
    final card = await db.query('srs_cards', where: 'question_id = ?', whereArgs: [questionId], limit: 1);
    if (card.isEmpty) return;
    await db.update(
      'srs_cards',
      {for (final c in syncColumns) c: card.first[c]},
      where: 'question_id IN (SELECT id FROM questions WHERE dup_group = ? AND id != ?)',
      whereArgs: [group, questionId],
    );
  }
}
