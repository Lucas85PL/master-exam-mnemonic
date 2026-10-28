import 'package:sqflite/sqflite.dart';

import '../domain/category_filter.dart';
import '../domain/fsrs.dart';
import '../domain/hardest.dart';
import '../domain/slideshow.dart';
import 'ai_disputed.dart';
import 'cmke_diff.dart';
import 'duplicate_groups.dart';
import 'question_categories.dart';
import '../domain/study_plan.dart';
import '../domain/test_plan.dart';

class QuestionRow {
  QuestionRow({
    required this.id,
    required this.pytanie,
    required this.poprawnaOdpowiedz,
    required this.odpA,
    required this.odpB,
    required this.odpC,
    required this.odpD,
    this.kategoria,
    this.reviewStatus,
    this.studyHidden = false,
    this.imagePath,
    this.hard = false,
    this.isNewCard = false,
    this.dupGroup,
    this.original,
    this.letterMap,
  });

  final int id;
  final String pytanie;
  final String poprawnaOdpowiedz;
  final String? odpA;
  final String? odpB;
  final String? odpC;
  final String? odpD;
  final String? kategoria;
  final String? reviewStatus;
  final bool studyHidden;

  /// Nazwa pliku w `assets/question_images/` (np. flaga w pytaniu o Kod Sygnałowy).
  final String? imagePath;

  /// Pytanie często błędnie zaznaczane (flaga „trudne”) / nigdy wcześniej niewidziane.
  final bool hard;
  final bool isNewCard;

  /// Grupa powtórzeń (null = pytanie występuje raz).
  final String? dupGroup;

  /// Przy losowej kolejności odpowiedzi: pytanie w oryginalnej kolejności (do wyjaśnień AI i ich pamięci podręcznej)
  /// oraz mapa litera oryginalna → litera wyświetlana. Dla pytania w oryginalnej kolejności: null.
  final QuestionRow? original;
  final Map<String, String>? letterMap;

  /// Litera wyświetlana → litera oryginalna (bez zmian, gdy kolejność nie była mieszana).
  String? originalLetterOf(String? shown) {
    if (shown == null || letterMap == null) return shown;
    for (final e in letterMap!.entries) {
      if (e.value == shown) return e.key;
    }
    return shown;
  }

  /// TYMCZASOWO: brak konsensusu agentów AI z kluczem w bazie (treść pytania na pomarańczowym tle).
  bool get aiDisputed => AiDisputed.ids.contains(id);

  /// Poprawna odpowiedź w bazie różni się od klucza w arkuszach CMKE (PDF).
  bool get cmkeDiff => CmkeDiff.letters.containsKey(id);

  /// Litera odpowiedzi z arkusza CMKE w układzie wyświetlanym (uwzględnia losową kolejność odpowiedzi).
  String? get cmkeShownLetter {
    final orig = CmkeDiff.letters[id];
    if (orig == null) return null;
    return letterMap?[orig] ?? orig;
  }

  /// Treść poprawnej odpowiedzi (do wykrywania powtórzonych pytań).
  String get correctText {
    final t = switch (poprawnaOdpowiedz) {
      'A' => odpA,
      'B' => odpB,
      'C' => odpC,
      'D' => odpD,
      _ => null,
    };
    return t ?? '';
  }

  List<MapEntry<String, String>> get visibleOptions {
    final out = <MapEntry<String, String>>[];
    for (final e in [
      ('A', odpA),
      ('B', odpB),
      ('C', odpC),
      ('D', odpD),
    ]) {
      final t = e.$2?.trim() ?? '';
      if (t.isNotEmpty) out.add(MapEntry(e.$1, t));
    }
    return out;
  }
}

class QuestionListItem {
  QuestionListItem({
    required this.id,
    required this.pytanie,
    required this.kategoria,
    required this.studyHidden,
    this.reviewStatus,
    this.kategorie = const [],
  });

  final int id;
  final String pytanie;
  final String kategoria;

  /// Wszystkie działy pytania (z `question_categories`); pusta lista = tylko dział główny [kategoria].
  final List<String> kategorie;

  /// Etykiety działów (Master / Angielski / Pokład), dział główny zawsze uwzględniony.
  String get kategorieLabel {
    final set = {kategoria, ...kategorie};
    return [for (final k in QuestionCategories.order) if (set.contains(k)) QuestionCategories.labelOf(k)].join(' + ');
  }
  final bool studyHidden;
  final String? reviewStatus;

  String get studyLabel => studyHidden ? 'Błąd' : 'OK';
}

class AnswerOutcome {
  const AnswerOutcome({required this.streakDays, required this.hard, required this.today});

  final int streakDays;
  final bool hard;
  final int today;
}

class QuestionRepository {
  QuestionRepository(this._db);

  final Database _db;

  String _studyWhere(StudyCategory category) {
    final parts = <String>[
      "review_status = 'ok'",
      'study_hidden = 0',
    ];
    if (category.values.isNotEmpty) {
      parts.add(QuestionCategories.matchSql(category.values)); // dział główny lub dodatkowy
    }
    return parts.join(' AND ');
  }

  /// Parametry filtra działów: wartości działów są wpisane wprost w SQL, więc nie ma parametrów.
  List<Object?> _studyArgs(StudyCategory category) => const [];

  /// Fragment SQL filtra działów dla zapytań o dziennik odpowiedzi (alias `q`), bez filtra: pusty tekst.
  String _catSql(StudyCategory category) =>
      category.values.isEmpty ? '' : 'AND ${QuestionCategories.matchSql(category.values, idCol: 'q.id', katCol: 'q.kategoria')}';

  /// Pula nauki jako **unikalne pytania**: kopie o tej samej treści (grupa `dup_group`) liczą się raz.
  /// Karty grupy mają zsynchronizowany stan, więc agregaty (MIN/MAX) dają ten sam wynik co pojedyncza kopia.
  String _grouped(StudyCategory category) => """
      SELECT COALESCE(q.dup_group, 'i' || q.id) AS g, MIN(s.state) AS state, MIN(s.due_ms) AS due_ms,
             MIN(s.streak_days) AS streak_days, MAX(s.hard) AS hard
      FROM questions q INNER JOIN srs_cards s ON s.question_id = q.id
      WHERE ${_studyWhere(category)}
      GROUP BY g
      """;

  Future<int> _countGrouped(StudyCategory category, String where, [List<Object?> args = const []]) async {
    final rows = await _db.rawQuery(
      'SELECT COUNT(*) AS c FROM (${_grouped(category)}) WHERE $where',
      [..._studyArgs(category), ...args],
    );
    return (rows.first['c'] as int?) ?? 0;
  }

  /// Karty „do powtórki teraz”: w trakcie powtórek po błędzie (1/10 min) oraz zaległe na dni.
  Future<int> countDue(StudyCategory category) =>
      _countGrouped(category, 'state IN (1, 2, 3) AND due_ms <= ?', [DateTime.now().millisecondsSinceEpoch]);

  /// Karty zaplanowane na najbliższe ~24 h (np. pytania z błędem na jutro rano).
  Future<int> countUpcoming(StudyCategory category) {
    final now = DateTime.now().millisecondsSinceEpoch;
    return _countGrouped(category, 'state IN (1, 2, 3) AND due_ms > ? AND due_ms <= ?', [now, now + 24 * 3600 * 1000]);
  }

  Future<int> countNew(StudyCategory category) => _countGrouped(category, 'state = 0');

  Future<int> countStudyPool(StudyCategory category) => _countGrouped(category, '1 = 1');

  Future<Map<String, dynamic>?> _fetchOne(String where, List<Object?> extraArgs,
      StudyCategory category, int? excludeId, String orderBy,
      {Set<int> doneIds = const {}}) async {
    final args = <Object?>[..._studyArgs(category), ...extraArgs];
    var exclude = '';
    if (excludeId != null) {
      exclude = ' AND q.id != ?';
      args.add(excludeId);
    }
    if (doneIds.isNotEmpty) {
      // identyfikatory to liczby całkowite z aplikacji - bezpieczne do wklejenia (bez limitu zmiennych SQLite)
      exclude += ' AND q.id NOT IN (${doneIds.join(',')})';
    }
    final rows = await _db.rawQuery(
      '''
      SELECT q.*, s.hard AS hard, s.state AS state FROM questions q
      INNER JOIN srs_cards s ON s.question_id = q.id
      WHERE ${_studyWhere(category)} AND $where$exclude
      ORDER BY $orderBy
      LIMIT 1
      ''',
      args,
    );
    return rows.isEmpty ? null : rows.first;
  }

  /// Kolejność: (1) karty w krótkich powtórkach po błędzie, których czas minął,
  /// (2) zaległe na dni (losowo), (3) nowe (losowo),
  /// (4) gdy nic więcej nie ma — najbliższa karta po błędzie (aby sesja nie kończyła się „pustą” kolejką).
  /// [excludeId] — nie pokazuj tej samej karty dwa razy z rzędu.
  ///
  /// Tryb [onlyNew]: tylko nowe karty (state = 0), bez powtórek.
  ///
  /// Tryb [ahead] („Powtórz zaplanowane”): karty z terminem w ciągu najbliższych 24 h (np. błędy na jutro).
  /// Karta powtórzona wcześniej niż za dobę zachowuje termin „jutro rano” (FSRS: krótki odstęp = bez zmiany interwału),
  /// więc zostałaby w oknie 24 h na zawsze. Dlatego aplikacja przekazuje w [doneIds] karty już zaliczone
  /// w tej sesji, a kolejka kończy się, gdy zostaną wyczerpane.
  Future<Map<String, dynamic>?> fetchNextCard(
    StudyCategory category, {
    int? excludeId,
    bool ahead = false,
    bool preferNew = false,
    bool onlyNew = false,
    Set<int> doneIds = const {},
  }) async {
    final now = DateTime.now().millisecondsSinceEpoch;
    // tryb „Same nowe”: wyłącznie karty, które nie pojawiły się ani razu
    if (onlyNew) return _fetchOne('s.state = 0', [], category, excludeId, 'RANDOM()');
    if (ahead) {
      return _fetchOne('s.state IN (1, 2, 3) AND s.due_ms <= ?',
          [now + 24 * 3600 * 1000], category, excludeId, 's.due_ms ASC',
          doneIds: doneIds);
    }
    final relearn = await _fetchOne(
        's.state IN (1, 3) AND s.due_ms <= ?', [now], category, excludeId, 's.due_ms ASC');
    if (relearn != null) return relearn;
    if (preferNew) {
      // „wstrzyknięcie” nowego pytania co kilka odpowiedzi (patrz newCardGap)
      final injected = await _fetchOne('s.state = 0', [], category, excludeId, 'RANDOM()');
      if (injected != null) return injected;
    }
    final due = await _fetchOne('s.state = 2 AND s.due_ms <= ?', [now], category, excludeId,
        's.hard DESC, RANDOM()'); // zaległe: najpierw trudne
    if (due != null) return due;
    final fresh = await _fetchOne('s.state = 0', [], category, excludeId, 'RANDOM()');
    if (fresh != null) return fresh;
    final soon = await _fetchOne('s.state IN (1, 3) AND s.due_ms <= ?',
        [now + 30 * 60 * 1000], category, excludeId, 's.due_ms ASC');
    if (soon != null) return soon;
    // jedyna pozostała karta może być tą samą co przed chwilą
    if (excludeId != null) return fetchNextCard(category);
    return null;
  }

  QuestionRow rowFromMap(Map<String, dynamic> m) {
    return QuestionRow(
      id: m['id'] as int,
      pytanie: m['pytanie'] as String? ?? '',
      poprawnaOdpowiedz: (m['poprawna_odpowiedz'] as String? ?? '').toUpperCase(),
      odpA: m['odp_a'] as String?,
      odpB: m['odp_b'] as String?,
      odpC: m['odp_c'] as String?,
      odpD: m['odp_d'] as String?,
      kategoria: m['kategoria'] as String?,
      reviewStatus: m['review_status'] as String?,
      studyHidden: (m['study_hidden'] as int? ?? 0) == 1,
      imagePath: m['image_path'] as String?,
      hard: (m['hard'] as int? ?? 0) == 1,
      isNewCard: (m['state'] as int? ?? 1) == 0,
      dupGroup: m['dup_group'] as String?,
    );
  }

  Future<FsrsCard?> loadSrs(int questionId) async {
    final rows = await _db.query(
      'srs_cards',
      where: 'question_id = ?',
      whereArgs: [questionId],
      limit: 1,
    );
    if (rows.isEmpty) return null;
    final r = rows.first;
    final last = r['last_review_ms'] as int?;
    return FsrsCard(
      questionId: questionId,
      state: CardState.fromValue(r['state'] as int? ?? 0),
      step: r['step'] as int? ?? 0,
      stability: (r['stability'] as num?)?.toDouble(),
      difficulty: (r['difficulty'] as num?)?.toDouble(),
      due: DateTime.fromMillisecondsSinceEpoch(r['due_ms'] as int),
      lastReview: last == null ? null : DateTime.fromMillisecondsSinceEpoch(last),
      reps: r['repetitions'] as int? ?? 0,
      lapses: r['lapses'] as int? ?? 0,
      intervalDays: r['interval_days'] as int? ?? 0,
    );
  }

  /// Zapis karty (od razu po odpowiedzi — postęp nie zależy od zamknięcia programu).
  Future<void> saveSrs(FsrsCard card) async {
    final values = {
      'repetitions': card.reps,
      'interval_days': card.intervalDays,
      'ease_factor': card.difficulty ?? 2.5,
      'due_ms': card.due.millisecondsSinceEpoch,
      'lapses': card.lapses,
      'state': card.state.value,
      'step': card.step,
      'stability': card.stability,
      'difficulty': card.difficulty,
      'last_review_ms': card.lastReview?.millisecondsSinceEpoch,
    };
    final n = await _db.update('srs_cards', values,
        where: 'question_id = ?', whereArgs: [card.questionId]);
    if (n == 0) {
      await _db.insert('srs_cards', {'question_id': card.questionId, ...values});
    }
    await DuplicateGroups.syncFrom(_db, card.questionId); // kopie tego pytania dostają ten sam harmonogram
  }


  /// Wszystkie pytania z puli nauki kategorii w losowej kolejności.
  Future<List<QuestionRow>> _shuffledPool(StudyCategory category) async {
    final rows = await _db.rawQuery(
      '''
      SELECT q.*, s.hard AS hard, s.state AS state FROM questions q
      INNER JOIN srs_cards s ON s.question_id = q.id
      WHERE ${_studyWhere(category)}
      ORDER BY RANDOM()
      ''',
      _studyArgs(category),
    );
    return rows.map(rowFromMap).toList();
  }

  static String _norm(Object? s) =>
      (s?.toString() ?? '').toLowerCase().replaceAll(RegExp(r'[^\p{L}\p{N}]+', unicode: true), '');

  /// Klucze „to samo pytanie”: (1) pełna treść + warianty + obrazek, (2) treść + poprawna odpowiedź + obrazek.
  /// W bazie to samo pytanie bywa w kilku wierszach (arkusze różnych poziomów, wersje po OCR), więc w teście
  /// nie wolno polegać na samym ID.
  static List<String> duplicateKeys(QuestionRow q) => [
        if (q.dupGroup != null) 'G|${q.dupGroup}',
        'F|${_norm(q.pytanie)}|${_norm(q.odpA)}|${_norm(q.odpB)}|${_norm(q.odpC)}|${_norm(q.odpD)}|${_norm(q.imagePath)}',
        'C|${_norm(q.pytanie)}|${_norm(q.correctText)}|${_norm(q.imagePath)}',
      ];

  /// Losuje pytania do TESTU: z każdej kategorii [wanted] sztuk, **bez powtórzeń** (także między kategoriami —
  /// duplikaty wykrywane po treści, nie po ID). Gdy po odrzuceniu duplikatów w puli brakuje pytań,
  /// braki są dobierane z pozostałych pul wg [pcts]. Wynik w losowej kolejności.
  Future<List<QuestionRow>> pickTestQuestions(
    List<StudyCategory> cats,
    List<int> wanted,
    List<int> pcts, {
    Set<String> exclude = const {},
  }) async {
    final seen = <String>{...exclude};
    final pools = <List<QuestionRow>>[];
    for (final c in cats) {
      final unique = <QuestionRow>[];
      for (final q in await _shuffledPool(c)) {
        final keys = duplicateKeys(q);
        if (keys.any(seen.contains)) continue;
        seen.addAll(keys);
        unique.add(q);
      }
      pools.add(unique);
    }
    final counts = redistributeTest(wanted, [for (final p in pools) p.length], pcts);
    final picked = <QuestionRow>[];
    for (var i = 0; i < pools.length; i++) {
      picked.addAll(pools[i].take(counts[i]));
    }
    picked.shuffle();
    return picked;
  }

  /// Klucze „to samo pytanie” (patrz [duplicateKeys]) dla pytań o podanych ID — także dla kopii z grupy powtórzeń.
  /// Służy do wykluczenia z nowego testu pytań z poprzednich testów.
  Future<Set<String>> duplicateKeysForIds(Iterable<int> ids) async {
    final out = <String>{};
    final list = ids.toList();
    for (var i = 0; i < list.length; i += 400) {
      final chunk = list.sublist(i, i + 400 > list.length ? list.length : i + 400);
      final rows = await _db.rawQuery(
        'SELECT q.* FROM questions q WHERE q.id IN (${List.filled(chunk.length, '?').join(',')})',
        chunk,
      );
      for (final r in rows) {
        out.addAll(duplicateKeys(rowFromMap(r)));
      }
    }
    return out;
  }

  /// Test „Trudny” (patrz [pickHardTest]): pula = wszystkie trzy działy, unikalne pytania, historia z dziennika odpowiedzi.
  Future<List<QuestionRow>> pickHardTestQuestions(int total, {int? nowMs, Set<String> exclude = const {}}) async {
    final seen = <String>{...exclude};
    final pool = <QuestionRow>[];
    for (final c in StudyCategory.selectable) {
      for (final q in await _shuffledPool(c)) {
        final keys = duplicateKeys(q);
        if (keys.any(seen.contains)) continue;
        seen.addAll(keys);
        pool.add(q);
      }
    }
    final rows = await _db.rawQuery('''
      SELECT COALESCE(q.dup_group, 'id' || q.id) AS gk, COUNT(*) AS n,
             SUM(CASE WHEN l.correct = 0 THEN 1 ELSE 0 END) AS wrong, MAX(l.ts_ms) AS last_ms
      FROM review_log l INNER JOIN questions q ON q.id = l.question_id GROUP BY gk
    ''');
    final stats = {
      for (final r in rows)
        r['gk'] as String: HardTestStat(
          attempts: (r['n'] as num).toInt(),
          wrong: (r['wrong'] as num?)?.toInt() ?? 0,
          lastMs: (r['last_ms'] as num).toInt(),
        ),
    };
    return pickHardTest<QuestionRow>(
      pool: pool,
      statOf: (q) => stats[q.dupGroup ?? 'id${q.id}'],
      total: total,
      nowMs: nowMs ?? DateTime.now().millisecondsSinceEpoch,
    );
  }

  // ------------------------------------------------------------ Slideshow

  /// Pytania o podanych ID (tylko z puli nauki: ok i niewyłączone „Błąd”), w kolejności [ids].
  Future<List<QuestionRow>> questionsByIds(List<int> ids) async {
    final byId = <int, QuestionRow>{};
    for (var i = 0; i < ids.length; i += 400) {
      final chunk = ids.sublist(i, i + 400 > ids.length ? ids.length : i + 400);
      final rows = await _db.rawQuery(
        'SELECT q.*, s.hard AS hard, s.state AS state FROM questions q LEFT JOIN srs_cards s ON s.question_id = q.id '
        "WHERE q.id IN (${List.filled(chunk.length, '?').join(',')}) AND q.study_hidden = 0 AND q.review_status = 'ok'",
        chunk,
      );
      for (final r in rows) {
        byId[r['id'] as int] = rowFromMap(r);
      }
    }
    return [for (final id in ids) if (byId[id] != null) byId[id]!];
  }

  /// Reprezentanci (najmniejsze ID z grupy powtórzeń) pytań „trudnych”: z błędami i trudnością ≥ [slideshowMinDifficulty];
  /// od pytania, na które ostatnio błędnie odpowiedziano.
  Future<List<int>> slideshowHardIds() async {
    final rows = await _db.rawQuery('''
      SELECT MIN(q.id) AS rep, COUNT(*) AS n, SUM(CASE WHEN l.correct = 0 THEN 1 ELSE 0 END) AS w,
             MAX(CASE WHEN l.correct = 0 THEN l.ts_ms END) AS last_wrong
      FROM review_log l INNER JOIN questions q ON q.id = l.question_id
      WHERE q.study_hidden = 0 AND q.review_status = 'ok'
      GROUP BY COALESCE(q.dup_group, 'id' || q.id)
      HAVING w > 0 AND (w + 1.0) / (n + 2) >= $slideshowMinDifficulty
      ORDER BY last_wrong DESC
    ''');
    return [for (final r in rows) r['rep'] as int];
  }

  /// Reprezentanci pytań, na które odpowiadano, od najdawniej wyświetlonego.
  Future<List<int>> slideshowOldestIds() async {
    final rows = await _db.rawQuery('''
      SELECT MIN(q.id) AS rep, MAX(l.ts_ms) AS last_ms
      FROM review_log l INNER JOIN questions q ON q.id = l.question_id
      WHERE q.study_hidden = 0 AND q.review_status = 'ok'
      GROUP BY COALESCE(q.dup_group, 'id' || q.id)
      ORDER BY last_ms ASC
    ''');
    return [for (final r in rows) r['rep'] as int];
  }

  /// Slideshow: [testWrongIds] (błędy z ostatnich testów) + [hardN] ostatnich trudnych + [oldestN] najstarszych, bez powtórzeń.
  Future<List<QuestionRow>> buildSlideshow({
    required Set<int> testWrongIds,
    required int hardN,
    required int oldestN,
    bool excludeUncertain = false,
  }) async {
    // „bez niepewnych”: niepewne pytania odpadają przed doborem, więc każda pula uzupełnia się kolejnymi kandydatami
    List<QuestionRow> keep(List<QuestionRow> l) => excludeUncertain ? [for (final q in l) if (!q.aiDisputed) q] : l;
    final tests = keep(await questionsByIds(testWrongIds.toList()));
    final hard = hardN > 0 ? keep(await questionsByIds(await slideshowHardIds())) : <QuestionRow>[];
    final oldest = oldestN > 0 ? keep(await questionsByIds(await slideshowOldestIds())) : <QuestionRow>[];
    return pickSlideshow<QuestionRow>(
      fromTests: tests,
      hardRanked: hard,
      hardN: hardN,
      oldest: oldest,
      oldestN: oldestN,
      keysOf: duplicateKeys,
    );
  }

  // ------------------------------------------------------------ postęp i dziennik odpowiedzi

  /// „Znane” = seria ≥ 3 dni nauki z poprawną odpowiedzią (unikalne pytania).
  Future<int> countKnown(StudyCategory category) => _countGrouped(category, 'streak_days >= $knownStreakDays');

  /// Ile dni-odpowiedzi brakuje, by cała pula miała serię 3 dni (Σ max(0, 3 − seria) po unikalnych pytaniach).
  Future<int> countRemainingReviews(StudyCategory category) async {
    final rows = await _db.rawQuery(
      'SELECT COALESCE(SUM($knownStreakDays - streak_days), 0) AS c FROM (${_grouped(category)}) '
      'WHERE streak_days < $knownStreakDays',
      _studyArgs(category),
    );
    return (rows.first['c'] as num?)?.toInt() ?? 0;
  }

  Future<int> countHard(StudyCategory category) => _countGrouped(category, 'hard = 1');

  /// Największa liczba jednostek serii brakujących jednemu pytaniu z puli (0 = wszystko znane; 3 = jest pytanie z serią 0).
  Future<int> maxRemainingUnits(StudyCategory category) async {
    final rows = await _db.rawQuery(
      'SELECT COALESCE(MAX($knownStreakDays - streak_days), 0) AS m FROM (${_grouped(category)}) '
      'WHERE streak_days < $knownStreakDays',
      _studyArgs(category),
    );
    return (rows.first['m'] as num?)?.toInt() ?? 0;
  }

  /// Liczba odpowiedzi udzielonych w danym dniu nauki (w wybranym dziale).
  Future<int> countAnswersOnDay(int day, {StudyCategory category = StudyCategory.all}) async {
    final rows = await _db.rawQuery(
      """
      SELECT COUNT(*) AS c FROM review_log l INNER JOIN questions q ON q.id = l.question_id
      WHERE l.day = ? ${_catSql(category)}
      """,
      [day],
    );
    return (rows.first['c'] as int?) ?? 0;
  }

  /// Tempo nauki w wybranym dziale: odpowiedzi, przyrost serii netto i liczba opanowanych pytań w ostatnich
  /// [paceWindowDays] dniach (tylko wpisy z zapisaną serią), plus przyrost dzisiejszy.
  Future<PaceStats> paceStats(StudyCategory category, int today) async {
    final since = today - (paceWindowDays - 1);
    final catSql = _catSql(category);
    final rows = await _db.rawQuery(
      """
      SELECT COUNT(*) AS n,
             COALESCE(SUM(l.streak_after - l.streak_before), 0) AS units,
             COALESCE(SUM(CASE WHEN l.streak_after >= $knownStreakDays AND l.streak_before < $knownStreakDays THEN 1 ELSE 0 END), 0) AS mastered,
             COALESCE(SUM(CASE WHEN l.day = $today THEN l.streak_after - l.streak_before ELSE 0 END), 0) AS today_units,
             MIN(l.day) AS first_day
      FROM review_log l INNER JOIN questions q ON q.id = l.question_id
      WHERE l.streak_after IS NOT NULL AND l.streak_before IS NOT NULL AND l.day >= ? $catSql
      """,
      [since],
    );
    final r = rows.first;
    final first = r['first_day'] as int?;
    return PaceStats(
      answers: (r['n'] as int?) ?? 0,
      netUnits: (r['units'] as num?)?.toInt() ?? 0,
      mastered: (r['mastered'] as num?)?.toInt() ?? 0,
      windowDays: first == null ? 1 : (today - first + 1).clamp(1, paceWindowDays),
      unitsToday: (r['today_units'] as num?)?.toInt() ?? 0,
    );
  }

  /// Zapisuje odpowiedź w dzienniku, aktualizuje serię dni i flagę „trudne”.
  /// Wywołuj PO [saveSrs] (karta musi istnieć); [lapses] — liczba błędów karty po tej odpowiedzi.
  Future<AnswerOutcome> recordAnswer({
    required int questionId,
    required bool correct,
    required int rating,
    required int lapses,
    required DateTime now,
    int? seconds,
  }) async {
    final today = studyDayOf(now);
    final rows = await _db.query('srs_cards',
        columns: ['streak_days', 'last_good_day'], where: 'question_id = ?', whereArgs: [questionId], limit: 1);
    final cur = rows.isEmpty
        ? const StreakState(0, null)
        : StreakState((rows.first['streak_days'] as int?) ?? 0, rows.first['last_good_day'] as int?);
    final next = nextStreak(cur, correct: correct, today: today);
    await _db.insert('review_log', {
      'question_id': questionId,
      'ts_ms': now.millisecondsSinceEpoch,
      'day': today,
      'correct': correct ? 1 : 0,
      'rating': rating,
      'seconds': seconds,
      'streak_before': cur.days,
      'streak_after': next.days,
    });
    final last10 = await _db.rawQuery(
        'SELECT correct FROM review_log WHERE question_id = ? ORDER BY id DESC LIMIT 10', [questionId]);
    final wrong = last10.where((r) => (r['correct'] as int?) == 0).length;
    final hard = computeHard(wrongOfLast10: wrong, lapses: lapses, streakDays: next.days);
    await _db.update(
      'srs_cards',
      {'streak_days': next.days, 'last_good_day': next.lastGoodDay, 'hard': hard ? 1 : 0},
      where: 'question_id = ?',
      whereArgs: [questionId],
    );
    await DuplicateGroups.syncFrom(_db, questionId); // seria i „trudne” także w kopiach pytania
    return AnswerOutcome(streakDays: next.days, hard: hard, today: today);
  }

  // ------------------------------------------------------------ statystyki

  /// Wszystkie odpowiedzi z dziennika: (czas ms, poprawna?, czy to powtórne pojawienie się pytania). Pytanie jest „znane”,
  /// gdy było już wcześniej pokazane (kopie tego samego pytania liczone razem) — pierwsze pojawienie się to pytanie nowe.
  Future<List<(int, bool, bool)>> allAnswers() async {
    final rows = await _db.rawQuery('''
      SELECT l.ts_ms AS ts, l.correct AS correct, COALESCE(q.dup_group, 'id' || l.question_id) AS gk
      FROM review_log l LEFT JOIN questions q ON q.id = l.question_id
      ORDER BY l.ts_ms, l.id
    ''');
    final seen = <String>{};
    return [
      for (final r in rows)
        ((r['ts'] as num).toInt(), (r['correct'] as int?) == 1, !seen.add(r['gk'] as String)),
    ];
  }

  /// Statystyka błędów per pytanie (kopie tego samego pytania scalone w grupę; pytania ukryte jako „Błąd” pominięte).
  /// Zwraca wszystkie pytania, na które kiedykolwiek odpowiedziano — kolejność dowolna.
  Future<List<QuestionErrorStat>> questionErrorStats() async {
    final rows = await _db.rawQuery('''
      SELECT g.rep AS id, g.attempts AS attempts, g.wrong AS wrong, q.pytanie AS pytanie,
             CASE UPPER(q.poprawna_odpowiedz) WHEN 'A' THEN q.odp_a WHEN 'B' THEN q.odp_b
                  WHEN 'C' THEN q.odp_c WHEN 'D' THEN q.odp_d END AS correct_text
      FROM (
        SELECT MIN(q.id) AS rep, COUNT(*) AS attempts,
               SUM(CASE WHEN l.correct = 0 THEN 1 ELSE 0 END) AS wrong
        FROM review_log l INNER JOIN questions q ON q.id = l.question_id
        WHERE q.study_hidden = 0 AND q.review_status = 'ok'
        GROUP BY COALESCE(q.dup_group, 'id' || q.id)
      ) g INNER JOIN questions q ON q.id = g.rep
    ''');
    return [
      for (final r in rows)
        QuestionErrorStat(
          id: r['id'] as int,
          attempts: (r['attempts'] as num).toInt(),
          wrong: (r['wrong'] as num?)?.toInt() ?? 0,
          pytanie: r['pytanie'] as String? ?? '',
          correctText: (r['correct_text'] as String? ?? '').trim(),
        ),
    ];
  }

  /// Karta pytania o danym ID (jak w kolejce nauki) albo null, gdy pytanie nie istnieje lub jest ukryte.
  Future<Map<String, dynamic>?> fetchCardById(int id) async {
    final rows = await _db.rawQuery(
      '''
      SELECT q.*, s.hard AS hard, s.state AS state FROM questions q
      INNER JOIN srs_cards s ON s.question_id = q.id
      WHERE q.id = ? AND q.review_status = 'ok' AND q.study_hidden = 0
      ''',
      [id],
    );
    return rows.isEmpty ? null : rows.first;
  }

  Future<void> hideQuestion(int questionId) async {
    await setStudyHidden(questionId, true);
  }

  Future<void> setStudyHidden(int questionId, bool hidden) async {
    await _db.update(
      'questions',
      {'study_hidden': hidden ? 1 : 0},
      where: 'id = ?',
      whereArgs: [questionId],
    );
  }

  Future<List<QuestionListItem>> listAllQuestions({
    StudyCategory? category,
    bool onlyStudyHidden = false,
    bool onlyUncertain = false,
    String? search,
    int limit = 100,
    int offset = 0,
  }) async {
    final where = <String>[];
    final args = <Object?>[];
    if (onlyStudyHidden) {
      where.add('study_hidden = 1');
    }
    if (onlyUncertain) {
      where.add('id IN (SELECT question_id FROM ai_disputed)');
    }
    if (category?.dbValue != null) {
      where.add(QuestionCategories.matchSql([category!.dbValue!]));
    }
    if (search != null && search.trim().isNotEmpty) {
      where.add('(pytanie LIKE ? OR CAST(id AS TEXT) LIKE ?)');
      final q = '%${search.trim()}%';
      args.addAll([q, q]);
    }
    final sql = '''
      SELECT id, pytanie, kategoria, study_hidden, review_status,
             (SELECT group_concat(kategoria, '|') FROM question_categories c WHERE c.question_id = questions.id) AS kategorie
      FROM questions
      ${where.isEmpty ? '' : 'WHERE ${where.join(' AND ')}'}
      ORDER BY id ASC
      LIMIT ? OFFSET ?
    ''';
    args.addAll([limit, offset]);
    final rows = await _db.rawQuery(sql, args);
    return rows
        .map(
          (r) => QuestionListItem(
            id: r['id'] as int,
            pytanie: r['pytanie'] as String? ?? '',
            kategoria: r['kategoria'] as String? ?? '',
            studyHidden: (r['study_hidden'] as int? ?? 0) == 1,
            reviewStatus: r['review_status'] as String?,
            kategorie: ((r['kategorie'] as String?) ?? '').split('|').where((e) => e.isNotEmpty).toList(),
          ),
        )
        .toList();
  }

  Future<int> countAllQuestions({
    StudyCategory? category,
    bool onlyStudyHidden = false,
    bool onlyUncertain = false,
    String? search,
  }) async {
    final where = <String>[];
    final args = <Object?>[];
    if (onlyStudyHidden) {
      where.add('study_hidden = 1');
    }
    if (onlyUncertain) {
      where.add('id IN (SELECT question_id FROM ai_disputed)');
    }
    if (category?.dbValue != null) {
      where.add(QuestionCategories.matchSql([category!.dbValue!]));
    }
    if (search != null && search.trim().isNotEmpty) {
      where.add('(pytanie LIKE ? OR CAST(id AS TEXT) LIKE ?)');
      final q = '%${search.trim()}%';
      args.addAll([q, q]);
    }
    final rows = await _db.rawQuery(
      '''
      SELECT COUNT(*) AS c FROM questions
      ${where.isEmpty ? '' : 'WHERE ${where.join(' AND ')}'}
      ''',
      args,
    );
    return (rows.first['c'] as int?) ?? 0;
  }

  Future<Map<String, dynamic>?> getQuestionById(int id) async {
    final rows = await _db.query(
      'questions',
      where: 'id = ?',
      whereArgs: [id],
      limit: 1,
    );
    if (rows.isEmpty) return null;
    return rows.first;
  }

  /// Działy pytania (Master / Angielski / Pokład), uporządkowane; dział główny zawsze wchodzi w skład.
  Future<List<String>> categoriesOf(int id) async {
    final row = await getQuestionById(id);
    if (row == null) return const [];
    return QuestionCategories.of(_db, id, row['kategoria'] as String? ?? '');
  }

  /// Zapisuje działy pytania (co najmniej jeden). Dotyczy tylko tego wiersza — kopie w innych działach są osobnymi pytaniami.
  Future<void> setCategories(int id, Set<String> chosen) async {
    final row = await getQuestionById(id);
    if (row == null) return;
    await QuestionCategories.set(_db, id, row['kategoria'] as String? ?? '', chosen);
  }

  /// Znacznik „Niepewne” (pomarańczowe tło): ustawiany dla pytania i wszystkich jego kopii z grupy powtórzeń,
  /// bo to samo pytanie ma wtedy ten sam wygląd pod każdym ID.
  Future<void> setUncertain(int id, bool value) async {
    final rows = await _db.rawQuery(
      'SELECT id FROM questions WHERE id = ? OR (dup_group IS NOT NULL AND dup_group = (SELECT dup_group FROM questions WHERE id = ?))',
      [id, id],
    );
    final ids = [for (final r in rows) r['id'] as int];
    for (final i in ids) {
      if (value) {
        await _db.insert('ai_disputed', {'question_id': i}, conflictAlgorithm: ConflictAlgorithm.ignore);
        AiDisputed.ids.add(i);
      } else {
        await _db.delete('ai_disputed', where: 'question_id = ?', whereArgs: [i]);
        AiDisputed.ids.remove(i);
      }
    }
  }

  Future<void> updateQuestion(int id, Map<String, Object?> fields) async {
    final allowed = {
      'pytanie',
      'odp_a',
      'odp_b',
      'odp_c',
      'odp_d',
      'poprawna_odpowiedz',
      'kategoria',
      'podkategoria',
      'tematyka',
      'nr_pytania',
    };
    final map = <String, Object?>{};
    for (final e in fields.entries) {
      if (allowed.contains(e.key)) map[e.key] = e.value;
    }
    if (map.containsKey('poprawna_odpowiedz')) {
      map['poprawna_odpowiedz'] =
          (map['poprawna_odpowiedz'] as String? ?? '').toUpperCase();
    }
    if (map.isEmpty) return;
    if (map.containsKey('poprawna_odpowiedz') ||
        map.keys.any((k) => k.startsWith('odp_'))) {
      // tekst poprawnej odpowiedzi i ślad ręcznej edycji (jak w skryptach narzędziowych)
      final cur = await getQuestionById(id);
      if (cur != null) {
        final merged = {...cur, ...map};
        final letter = (merged['poprawna_odpowiedz'] as String? ?? '').toLowerCase();
        map['poprawna_odpowiedz_tekst'] = merged['odp_$letter'];
        final day = DateTime.now().toIso8601String().substring(0, 10);
        map['ai_verified'] = 'manual:app_edit:$day';
      }
    }
    await _db.update('questions', map, where: 'id = ?', whereArgs: [id]);
    await DuplicateGroups.refresh(_db); // zmiana treści może dołączyć/odłączyć pytanie od grupy powtórzeń
  }

  Future<Map<String, dynamic>?> getImportMeta() async {
    final rows = await _db.query('import_meta', limit: 1);
    if (rows.isEmpty) return null;
    return rows.first;
  }
}
