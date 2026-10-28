import 'dart:math';

/// Ile ostatnich zakończonych testów (Normalnych i Trudnych) wyklucza pytania w nowym teście.
const testNoRepeatDepth = 2;

/// Konfiguracja i losowanie „TEST” (symulacja egzaminu).
class TestConfig {
  const TestConfig({
    this.total = 105,
    this.passMark = 70,
    this.masterPct = 50,
    this.englishPct = 20,
  });

  final int total;
  final int passMark;
  final int masterPct;
  final int englishPct;

  /// Pokład to reszta do 100%.
  int get pokladPct => 100 - masterPct - englishPct;

  TestConfig copyWith({int? total, int? passMark, int? masterPct, int? englishPct}) {
    final t = (total ?? this.total).clamp(5, 300);
    final m = (masterPct ?? this.masterPct).clamp(0, 100);
    final e = (englishPct ?? this.englishPct).clamp(0, 100 - m);
    return TestConfig(
      total: t,
      passMark: (passMark ?? this.passMark).clamp(1, t),
      masterPct: m,
      englishPct: e,
    );
  }

  bool isPassed(int correct) => correct >= passMark;
}

/// Dzieli [total] pytań wg procentów [pcts] (metoda największych reszt; remis wygrywa większy udział).
/// Suma wyniku zawsze równa się [total].
List<int> allocateTest(int total, List<int> pcts) {
  final sum = pcts.fold<int>(0, (a, b) => a + b);
  if (sum <= 0) return List.filled(pcts.length, 0);
  final exact = [for (final p in pcts) total * p / sum];
  final base = [for (final x in exact) x.floor()];
  var left = total - base.fold<int>(0, (a, b) => a + b);
  final order = List.generate(pcts.length, (i) => i)
    ..sort((a, b) {
      final fa = exact[a] - base[a];
      final fb = exact[b] - base[b];
      final c = fb.compareTo(fa);
      return c != 0 ? c : pcts[b].compareTo(pcts[a]);
    });
  for (final i in order) {
    if (left <= 0) break;
    base[i]++;
    left--;
  }
  return base;
}

/// Gdy w którejś puli jest mniej pytań niż trzeba, brakujące dobiera z pozostałych (wg procentów), o ile mają zapas.
List<int> redistributeTest(List<int> wanted, List<int> available, List<int> pcts) {
  final result = [for (var i = 0; i < wanted.length; i++) wanted[i].clamp(0, available[i])];
  var missing = wanted.fold<int>(0, (a, b) => a + b) - result.fold<int>(0, (a, b) => a + b);
  final order = List.generate(wanted.length, (i) => i)..sort((a, b) => pcts[b].compareTo(pcts[a]));
  while (missing > 0) {
    var progressed = false;
    for (final i in order) {
      if (missing == 0) break;
      if (result[i] < available[i]) {
        result[i]++;
        missing--;
        progressed = true;
      }
    }
    if (!progressed) break; // cała baza mniejsza niż test
  }
  return result;
}

/// Udziały trybu „Trudny”: 50% z najtrudniejszych, 30% dawno powtarzanych trudniejszych, 20% losowo.
const hardTestPcts = [50, 30, 20];

/// Z ilu najtrudniejszych pytań losujemy pierwszą część testu „Trudny”.
const hardTestTopSize = 200;

/// Pytanie „dawno niepowtarzane”, jeśli ostatnia odpowiedź była wcześniej niż tyle dni temu.
const hardTestStaleDays = 5;

/// Pytanie „trudniejsze” (druga część): ma błędy i wygładzoną trudność co najmniej taką.
const hardTestMinDifficulty = 0.4;

/// Historia odpowiedzi jednego pytania (kopie scalone w grupę powtórzeń) potrzebna do testu „Trudny”.
class HardTestStat {
  const HardTestStat({required this.attempts, required this.wrong, required this.lastMs});

  final int attempts;
  final int wrong;

  /// Czas ostatniej odpowiedzi (ms od epoki).
  final int lastMs;

  /// Jak w Statystykach: wygładzony odsetek błędów, 1/1 błędów jest „trudniejsze” niż 0/1.
  double get difficulty => (wrong + 1) / (attempts + 2);
}

/// Losuje [total] pytań do testu „Trudny” z [pool] (unikalne pytania, bez powtórzeń): 50% z [topSize] najtrudniejszych,
/// 30% pytań trudniejszych (z błędami), których ostatnia odpowiedź była dawniej niż [staleDays] dni temu, 20% zupełnie losowo.
/// Gdy jakiejś części brakuje kandydatów, ubytek jest uzupełniany najpierw kolejnymi najtrudniejszymi, potem losowymi.
/// Pytania bez historii nie są „trudne” (trafiają tylko do części losowej). [statOf] zwraca null dla pytań bez historii.
List<T> pickHardTest<T>({
  required List<T> pool,
  required HardTestStat? Function(T) statOf,
  required int total,
  required int nowMs,
  Random? random,
  int topSize = hardTestTopSize,
  int staleDays = hardTestStaleDays,
}) {
  final rnd = random ?? Random();
  final shuffled = List<T>.of(pool)..shuffle(rnd);
  final want = allocateTest(total, hardTestPcts);
  final picked = <T>[];
  final used = <T>{};

  void take(Iterable<T> candidates, int n) {
    final list = candidates.where((q) => !used.contains(q)).toList()..shuffle(rnd);
    for (final q in list.take(n)) {
      picked.add(q);
      used.add(q);
    }
  }

  // ranking trudności (remis: więcej odpowiedzi, potem losowo dzięki wstępnemu tasowaniu — sort jest stabilny)
  final ranked = shuffled.where((q) => statOf(q) != null).toList()
    ..sort((a, b) {
      final sa = statOf(a)!, sb = statOf(b)!;
      final c = sb.difficulty.compareTo(sa.difficulty);
      return c != 0 ? c : sb.attempts.compareTo(sa.attempts);
    });
  take(ranked.take(topSize), want[0]);

  final staleBefore = nowMs - staleDays * Duration.millisecondsPerDay;
  take(
    ranked.where((q) {
      final s = statOf(q)!;
      return s.wrong > 0 && s.difficulty >= hardTestMinDifficulty && s.lastMs < staleBefore;
    }),
    want[1],
  );
  take(shuffled, want[2]);
  if (picked.length < total) {
    take(ranked, total - picked.length); // ubytek: kolejne najtrudniejsze
    take(shuffled, total - picked.length); // potem losowe
  }
  return picked..shuffle(rnd);
}
