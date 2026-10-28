import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:memonic_app/data/test_history.dart';
import 'package:memonic_app/domain/hardest.dart';
import 'package:memonic_app/features/stats/stats_screen.dart';

void main() {
  test('TestResult: flaga „trudny” zapisuje się i odczytuje; stare wpisy są normalne', () {
    final r = TestResult(
      timestamp: DateTime(2026, 10, 22, 12),
      total: 105,
      answered: 105,
      correct: 80,
      passMark: 70,
      perCategory: {'Master': [40, 53]},
      hard: true,
    );
    expect(TestResult.fromJson(r.toJson()).hard, isTrue);
    final old = Map<String, dynamic>.of(r.toJson())..remove('hard');
    expect(TestResult.fromJson(old).hard, isFalse);
  });

  testWidgets('Statystyki → Sesje: zakończone testy na liście, wersja trudna oznaczona, przerwane pominięte', (tester) async {
    TestResult t(int day, int correct, {bool hard = false, int answered = 105}) => TestResult(
          timestamp: DateTime(2026, 10, day, 10),
          total: 105,
          answered: answered,
          correct: correct,
          passMark: 70,
          perCategory: {'Master': [correct, 105]},
          hard: hard,
        );
    final tests = [t(21, 60, hard: true), t(20, 80)];
    final data = StatsData(
      answers: 10,
      correct: 8,
      knownAnswers: 0,
      knownCorrect: 0,
      sessions: [
        SessionStat(start: DateTime(2026, 10, 19, 9), end: DateTime(2026, 10, 19, 9, 20), answers: 10, correct: 8),
      ],
      ranked: const [],
      tests: tests,
    );
    await tester.pumpWidget(ProviderScope(
      overrides: [statsDataProvider.overrideWith((ref) async => data)],
      child: const MaterialApp(home: StatsScreen()),
    ));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Sesje'));
    await tester.pumpAndSettle();
    expect(find.textContaining('TEST ·'), findsNWidgets(2));
    expect(find.text('Wersja trudna'), findsOneWidget); // tylko test z 21.10
    expect(find.textContaining('· zaliczony'), findsOneWidget);
    expect(find.textContaining('niezaliczony'), findsOneWidget);
    expect(find.textContaining('Sesja 1'), findsOneWidget);
  });
}
