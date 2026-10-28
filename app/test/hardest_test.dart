import 'dart:math';

import 'package:flutter_test/flutter_test.dart';
import 'package:memonic_app/domain/hardest.dart';

void main() {
  const min = 60 * 1000;

  test('sesje: przerwa >= 30 min dzieli odpowiedzi, wynik od najnowszej', () {
    final a = <(int, bool, bool)>[
      (0, true, false), (1 * min, false, true), (5 * min, true, true), // sesja 1: 2/3, znane 1/2
      (100 * min, true, false), (101 * min, true, false), // sesja 2: 2/2, bez znanych
    ];
    final s = splitSessions(a);
    expect(s.length, 2);
    expect(s[0].answers, 2);
    expect(s[0].percent, 100);
    expect(s[1].answers, 3);
    expect(s[1].correct, 2);
    expect(s[1].percent, closeTo(66.7, 0.1));
    expect((s[1].knownAnswers, s[1].knownCorrect), (2, 1));
    expect(s[1].knownPercent, 50);
    expect(s[0].knownAnswers, 0);
    expect(splitSessions([]), isEmpty);
  });

  test('ranking: wygładzony wskaźnik błędów, remis rozstrzyga liczba odpowiedzi', () {
    final r = rankByDifficulty(const [
      QuestionErrorStat(id: 1, attempts: 10, wrong: 5),
      QuestionErrorStat(id: 2, attempts: 3, wrong: 3),
      QuestionErrorStat(id: 3, attempts: 1, wrong: 1),
    ]);
    expect(r.map((e) => e.id), [2, 3, 1]); // 4/5 > 2/3 > 6/12
  });

  test('losowanie: rozmiar, brak powtórzeń, szerszy zakres przy większej liczbie', () {
    final ranked = List.generate(1000, (i) => i);
    double avgRank(int n) {
      var sum = 0.0;
      const runs = 30;
      for (var k = 0; k < runs; k++) {
        final p = pickByNormalRank(ranked, n, Random(k));
        expect(p.length, n);
        expect(p.toSet().length, n);
        sum += p.reduce((a, b) => a + b) / n;
      }
      return sum / runs;
    }

    final a50 = avgRank(50), a200 = avgRank(200);
    expect(a50, lessThan(a200)); // 200 sięga głębiej w ranking niż 50
    expect(a50, lessThan(100)); // 50: głównie czołówka rankingu
    expect(pickByNormalRank([1, 2, 3], 10, Random(1)).toSet(), {1, 2, 3}); // mała pula: wszystko
  });

  test('orderDrill: od najtrudniejszych = ranking trudności; losowo = te same pytania, dowolna kolejność', () {
    final picked = [
      const QuestionErrorStat(id: 1, attempts: 10, wrong: 1),
      const QuestionErrorStat(id: 2, attempts: 1, wrong: 1),
      const QuestionErrorStat(id: 3, attempts: 10, wrong: 9),
    ];
    expect(orderDrill(picked, hardestFirst: true).map((s) => s.id), [3, 2, 1]);
    final rnd = orderDrill(picked, hardestFirst: false, random: Random(5));
    expect(rnd.map((s) => s.id).toSet(), {1, 2, 3});
    expect(rnd.length, 3);
  });
}
