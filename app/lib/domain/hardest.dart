import 'dart:math';

/// Przerwa między odpowiedziami, po której zaczyna się nowa sesja (min.).
const sessionGapMinutes = 30;

/// Dostępne wielkości listy najtrudniejszych pytań (Statystyki) i powtórki (najtrudniejsze).
const hardestListSizes = [100, 200, 300];
const drillSizes = [50, 100, 150, 200];

/// Statystyka jednego pytania (powtórzone kopie są scalone w jedno).
class QuestionErrorStat {
  const QuestionErrorStat({
    required this.id,
    required this.attempts,
    required this.wrong,
    this.pytanie = '',
    this.correctText = '',
  });

  final int id;
  final int attempts;
  final int wrong;
  final String pytanie;

  /// Treść poprawnej odpowiedzi (bez litery A/B/C).
  final String correctText;

  double get errorRate => attempts == 0 ? 0 : wrong / attempts;

  /// Wygładzony wskaźnik trudności: 1/1 błędów jest „trudniejsze” niż 0/1, ale mniej pewne niż 8/10.
  double get difficulty => (wrong + 1) / (attempts + 2);
}

/// Sortuje od najtrudniejszych (największy wygładzony odsetek błędów; remis: więcej odpowiedzi, potem ID).
List<QuestionErrorStat> rankByDifficulty(Iterable<QuestionErrorStat> stats) {
  final out = stats.toList();
  out.sort((a, b) {
    final c = b.difficulty.compareTo(a.difficulty);
    if (c != 0) return c;
    final n = b.attempts.compareTo(a.attempts);
    return n != 0 ? n : a.id.compareTo(b.id);
  });
  return out;
}

/// Wybiera [count] pytań z listy [ranked] (od najtrudniejszych) bez powtórzeń. Prawdopodobieństwo wyboru maleje
/// jak połowa rozkładu normalnego względem pozycji w rankingu (σ = [count]): najtrudniejsze są niemal pewne, a im dalej
/// w rankingu, tym rzadziej. Zwiększenie [count] poszerza więc zakres losowania. Wynik w losowej kolejności.
List<T> pickByNormalRank<T>(List<T> ranked, int count, Random rnd) {
  if (ranked.length <= count) return List<T>.of(ranked)..shuffle(rnd);
  final sigma = count.toDouble();
  final keyed = <(double, T)>[];
  for (var r = 0; r < ranked.length; r++) {
    final w = max(exp(-(r * r) / (2 * sigma * sigma)), 1e-300);
    // losowanie ważone bez zwracania (Efraimidis–Spirakis) w skali logarytmicznej
    final u = max(rnd.nextDouble(), 1e-12);
    keyed.add((log(u) / w, ranked[r]));
  }
  keyed.sort((a, b) => b.$1.compareTo(a.$1));
  return [for (final k in keyed.take(count)) k.$2]..shuffle(rnd);
}

/// Kolejność pytań w „Powtórce trudnych” już wybranych do powtórki: od najtrudniejszych (jak w rankingu) albo losowo.
List<QuestionErrorStat> orderDrill(List<QuestionErrorStat> picked, {required bool hardestFirst, Random? random}) =>
    hardestFirst ? rankByDifficulty(picked) : (List.of(picked)..shuffle(random ?? Random()));

/// Wynik jednej sesji nauki (odpowiedzi rozdzielone przerwą ≥ [sessionGapMinutes]).
class SessionStat {
  const SessionStat({
    required this.start,
    required this.end,
    required this.answers,
    required this.correct,
    this.knownAnswers = 0,
    this.knownCorrect = 0,
  });

  final DateTime start;
  final DateTime end;
  final int answers;
  final int correct;

  /// Tylko odpowiedzi na pytania „znane”: te, które pojawiły się już wcześniej (drugie i kolejne pojawienie się pytania).
  final int knownAnswers;
  final int knownCorrect;

  double get percent => answers == 0 ? 0 : 100 * correct / answers;
  double get knownPercent => knownAnswers == 0 ? 0 : 100 * knownCorrect / knownAnswers;
}

/// Dzieli odpowiedzi (czas w ms, poprawna?, czy pytanie było już wcześniej pokazane) na sesje. Wynik: od najnowszej.
List<SessionStat> splitSessions(List<(int, bool, bool)> answers, {int gapMinutes = sessionGapMinutes}) {
  final sorted = [...answers]..sort((a, b) => a.$1.compareTo(b.$1));
  final out = <SessionStat>[];
  int? start, last;
  var n = 0, ok = 0, kn = 0, kok = 0;
  void close() {
    if (start != null) {
      out.add(SessionStat(
        start: DateTime.fromMillisecondsSinceEpoch(start),
        end: DateTime.fromMillisecondsSinceEpoch(last!),
        answers: n,
        correct: ok,
        knownAnswers: kn,
        knownCorrect: kok,
      ));
    }
  }

  for (final a in sorted) {
    if (last != null && a.$1 - last >= gapMinutes * 60 * 1000) {
      close();
      start = null;
      n = 0;
      ok = 0;
      kn = 0;
      kok = 0;
    }
    start ??= a.$1;
    last = a.$1;
    n++;
    if (a.$2) ok++;
    if (a.$3) {
      kn++;
      if (a.$2) kok++;
    }
  }
  close();
  return out.reversed.toList();
}
