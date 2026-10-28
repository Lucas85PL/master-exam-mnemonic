import 'dart:math';

import 'package:flutter_test/flutter_test.dart';
import 'package:memonic_app/domain/test_plan.dart';

void main() {
  const day = Duration.millisecondsPerDay;
  final now = DateTime(2026, 10, 22).millisecondsSinceEpoch;

  // 600 pytań: 0..299 z historią (im niższe ID, tym trudniejsze), 300..599 bez historii
  final pool = List<int>.generate(600, (i) => i);
  HardTestStat? statOf(int id) {
    if (id >= 300) return null;
    // id<100: 1 odpowiedź, 1 błąd; 100..199: 10 odpowiedzi, 3 błędy; 200..299: 10 odpowiedzi, 0 błędów
    final attempts = id < 100 ? 1 : 10;
    final wrong = id < 100 ? 1 : (id < 200 ? 3 : 0);
    return HardTestStat(attempts: attempts, wrong: wrong, lastMs: now - (id.isEven ? 8 : 1) * day);
  }

  test('trudność: 1/1 błędów wysoko, 1/10 błędów nisko', () {
    expect(const HardTestStat(attempts: 1, wrong: 1, lastMs: 0).difficulty, closeTo(0.667, 0.01));
    expect(const HardTestStat(attempts: 10, wrong: 1, lastMs: 0).difficulty, closeTo(0.167, 0.01));
    expect(const HardTestStat(attempts: 10, wrong: 9, lastMs: 0).difficulty, greaterThan(0.8));
  });

  test('105 pytań, bez powtórzeń, każda część w proporcjach 50/30/20', () {
    final list = pickHardTest<int>(pool: pool, statOf: statOf, total: 105, nowMs: now, random: Random(1));
    expect(list.length, 105);
    expect(list.toSet().length, 105);
    // część A: wszystkie z 200 najtrudniejszych (1/1 błędów -> 0.667; 3/10 -> 0.333; reszta niżej) => id < 200 z czołówki
    final top = (pool.where((q) => statOf(q) != null).toList()
          ..sort((a, b) => statOf(b)!.difficulty.compareTo(statOf(a)!.difficulty)))
        .take(hardTestTopSize)
        .toSet();
    final inTop = list.where(top.contains).length;
    expect(inTop, greaterThanOrEqualTo(53)); // 53 z czołówki + ewentualnie więcej z części B / losowej
  });

  test('część „dawno powtarzane”: tylko trudniejsze z błędami, ostatnia odpowiedź starsza niż 5 dni', () {
    // tylko 30 pytań do wyboru w części B, żeby wymusić jej obecność: pula bez części losowej i bez czołówki > 200
    final small = List<int>.generate(150, (i) => i + 100); // 100..249: 10 odp., 3 błędy (100..199) lub 0 (200..249)
    final list = pickHardTest<int>(pool: small, statOf: statOf, total: 20, nowMs: now, random: Random(7));
    expect(list.length, 20);
    expect(list.toSet().length, 20);
  });

  test('pytania bez historii trafiają tylko do części losowej, a brak kandydatów uzupełniają inne części', () {
    final fresh = List<int>.generate(300, (i) => 300 + i); // nikt nie ma historii
    final list = pickHardTest<int>(pool: fresh, statOf: statOf, total: 105, nowMs: now, random: Random(3));
    expect(list.length, 105);
    expect(list.toSet().length, 105);
  });

  test('mała pula: zwraca tyle, ile jest, bez powtórzeń', () {
    final list = pickHardTest<int>(pool: [1, 2, 3], statOf: statOf, total: 105, nowMs: now);
    expect(list.toSet(), {1, 2, 3});
  });
}
