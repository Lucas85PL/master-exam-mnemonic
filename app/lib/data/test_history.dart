import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

/// Wynik pojedynczego TESTU (przechowywany lokalnie w SharedPreferences, ostatnie 200).
class TestResult {
  const TestResult({
    required this.timestamp,
    required this.total,
    required this.answered,
    required this.correct,
    required this.passMark,
    required this.perCategory,
    this.hard = false,
    this.questionIds = const [],
    this.wrongIds = const [],
    this.recordsWrong = false,
  });

  final DateTime timestamp;
  final int total;
  final int answered;
  final int correct;
  final int passMark;

  /// {'Master': [poprawne, pytań], ...}
  final Map<String, List<int>> perCategory;

  /// Test w wersji „Trudny” (inne losowanie pytań).
  final bool hard;

  /// ID pytań wylosowanych do tego testu (pusty w starych wpisach sprzed reguły „bez powtórzeń”).
  final List<int> questionIds;

  /// ID pytań, na które odpowiedziano błędnie lub „Nie wiem” (Slideshow „Błędne z ostatnich testów”).
  final List<int> wrongIds;

  /// Czy wpis zapisano z listą błędów (stare wpisy jej nie mają — wtedy pusty [wrongIds] nie oznacza testu bez błędów).
  final bool recordsWrong;

  bool get passed => correct >= passMark;

  Map<String, Object?> toJson() => {
        'ts': timestamp.millisecondsSinceEpoch,
        'total': total,
        'answered': answered,
        'correct': correct,
        'pass': passMark,
        'cats': perCategory,
        if (hard) 'hard': true,
        if (questionIds.isNotEmpty) 'qids': questionIds,
        if (recordsWrong) 'wids': wrongIds,
      };

  static TestResult fromJson(Map<String, dynamic> m) => TestResult(
        timestamp: DateTime.fromMillisecondsSinceEpoch(m['ts'] as int),
        total: m['total'] as int,
        answered: m['answered'] as int,
        correct: m['correct'] as int,
        passMark: m['pass'] as int,
        perCategory: {
          for (final e in (m['cats'] as Map<String, dynamic>).entries)
            e.key: (e.value as List).map((x) => x as int).toList(),
        },
        hard: m['hard'] == true,
        questionIds: [for (final x in (m['qids'] as List? ?? const [])) x as int],
        wrongIds: [for (final x in (m['wids'] as List? ?? const [])) x as int],
        recordsWrong: m['wids'] != null,
      );
}

class TestHistory {
  static const _key = 'test_history';

  static Future<List<TestResult>> load() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_key);
    if (raw == null) return [];
    try {
      return (jsonDecode(raw) as List)
          .map((e) => TestResult.fromJson(e as Map<String, dynamic>))
          .toList();
    } catch (_) {
      return [];
    }
  }

  /// ID pytań z [tests] ostatnich zakończonych testów (do wykluczenia z kolejnego losowania).
  static Future<Set<int>> recentQuestionIds(int tests) async {
    final all = await load();
    return {for (final t in all.take(tests)) ...t.questionIds};
  }

  /// Błędnie odpowiedziane pytania z [tests] ostatnich zakończonych testów (unikalne ID) oraz liczba tych testów, które mają
  /// zapisaną listę błędów (starsze wpisy jej nie mają).
  static Future<({Set<int> ids, int testsWithData})> recentWrong(int tests) async {
    final used = (await load()).take(tests).where((t) => t.recordsWrong).toList();
    return (ids: {for (final t in used) ...t.wrongIds}, testsWithData: used.length);
  }

  static Future<void> add(TestResult r) async {
    final all = await load();
    all.insert(0, r);
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_key, jsonEncode(all.take(200).map((e) => e.toJson()).toList()));
  }
}
