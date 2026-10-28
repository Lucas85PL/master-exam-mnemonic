import 'dart:math' as math;

/// FSRS-6 (Free Spaced Repetition Scheduler) dopasowany do pytań testowych.
///
/// Wzory i domyślne parametry: oficjalna implementacja open-spaced-repetition/py-fsrs.
/// Dopasowanie do pytań wielokrotnego wyboru:
/// * poprawna odpowiedź = Good (wolna poprawna = Hard), błędna / „Nie wiem” = Again,
/// * karta po błędzie przechodzi przez krótkie kroki powtórek w tej samej sesji
///   (domyślnie 1 min i 10 min), a dopiero potem dostaje interwał w dniach,
/// * karty „na dni” stają się dostępne od rana (godzina zmiany dnia), a nie co do godziny.
enum Rating {
  again(1),
  hard(2),
  good(3),
  easy(4);

  const Rating(this.value);
  final int value;
}

enum CardState {
  newCard(0),
  learning(1),
  review(2),
  relearning(3);

  const CardState(this.value);
  final int value;

  static CardState fromValue(int v) =>
      CardState.values.firstWhere((s) => s.value == v, orElse: () => CardState.newCard);
}

const fsrsDefaultWeights = <double>[
  0.212, 1.2931, 2.3065, 8.2956, 6.4133, 0.8334, 3.0194, 0.001, 1.8722,
  0.1666, 0.796, 1.4835, 0.0614, 0.2629, 1.6483, 0.6014, 1.8729, 0.5425,
  0.0912, 0.0658, 0.1542,
];

class FsrsCard {
  FsrsCard({
    required this.questionId,
    this.state = CardState.newCard,
    this.step = 0,
    this.stability,
    this.difficulty,
    DateTime? due,
    this.lastReview,
    this.reps = 0,
    this.lapses = 0,
    this.intervalDays = 0,
  }) : due = due ?? DateTime.now();

  final int questionId;
  CardState state;
  int step;
  double? stability;
  double? difficulty;
  DateTime due;
  DateTime? lastReview;

  /// Liczba wszystkich ocen karty.
  int reps;
  int lapses;

  /// Ostatnio zaplanowany interwał (dni) — do wyświetlania.
  int intervalDays;

  bool get isNew => state == CardState.newCard;

  FsrsCard copy() => FsrsCard(
        questionId: questionId,
        state: state,
        step: step,
        stability: stability,
        difficulty: difficulty,
        due: due,
        lastReview: lastReview,
        reps: reps,
        lapses: lapses,
        intervalDays: intervalDays,
      );
}

class FsrsScheduler {
  FsrsScheduler({
    this.desiredRetention = 0.9,
    List<double>? weights,
    this.relearningSteps = const [Duration(minutes: 1), Duration(minutes: 10)],
    this.rolloverHour = 4,
    this.maximumInterval = 36500,
  }) : w = weights ?? fsrsDefaultWeights {
    assert(w.length == 21);
  }

  final double desiredRetention;
  final List<double> w;
  final List<Duration> relearningSteps;

  /// Godzina, od której zaczyna się „nowy dzień” nauki (karty na dziś są dostępne od niej).
  final int rolloverHour;
  final int maximumInterval;

  double get decay => -w[20];
  double get factor => math.pow(0.9, 1 / decay).toDouble() - 1;

  double retrievability(double stability, double elapsedDays) =>
      math.pow(1 + factor * elapsedDays / stability, decay).toDouble();

  double initialStability(Rating r) => math.max(w[r.value - 1], 0.001);

  double initialDifficulty(Rating r, {bool clamp = true}) {
    final d = w[4] - math.exp(w[5] * (r.value - 1)) + 1;
    return clamp ? d.clamp(1.0, 10.0) : d;
  }

  double nextDifficulty(double d, Rating r) {
    final arg1 = initialDifficulty(Rating.easy, clamp: false);
    final delta = -(w[6] * (r.value - 3));
    final arg2 = d + (10 - d) * delta / 9;
    return (w[7] * arg1 + (1 - w[7]) * arg2).clamp(1.0, 10.0);
  }

  double shortTermStability(double s, Rating r) {
    var inc = math.exp(w[17] * (r.value - 3 + w[18])) * math.pow(s, -w[19]);
    if (r.value >= 2) inc = math.max(inc, 1.0);
    return math.max(s * inc, 0.001);
  }

  double nextRecallStability(double d, double s, double rr, Rating r) {
    final hard = r == Rating.hard ? w[15] : 1.0;
    final easy = r == Rating.easy ? w[16] : 1.0;
    return s *
        (1 +
            math.exp(w[8]) *
                (11 - d) *
                math.pow(s, -w[9]) *
                (math.exp((1 - rr) * w[10]) - 1) *
                hard *
                easy);
  }

  double nextForgetStability(double d, double s, double rr) {
    final long = w[11] *
        math.pow(d, -w[12]) *
        (math.pow(s + 1, w[13]) - 1) *
        math.exp((1 - rr) * w[14]);
    final short = s / math.exp(w[17] * w[18]);
    return math.min(long, short);
  }

  /// Interwał (w dniach, >= 1) dla zadanej stabilności i oczekiwanej retencji.
  int nextIntervalDays(double stability) {
    final days = stability / factor * (math.pow(desiredRetention, 1 / decay) - 1);
    return days.round().clamp(1, maximumInterval);
  }

  /// Początek dostępności karty „za [days] dni” (godzina zmiany dnia).
  DateTime dueInDays(DateTime now, int days) {
    final shifted = now.subtract(Duration(hours: rolloverHour));
    return DateTime(shifted.year, shifted.month, shifted.day + days, rolloverHour);
  }

  /// Ocena karty. Zwraca NOWY obiekt; wejściowy nie jest zmieniany.
  FsrsCard review(FsrsCard card, Rating rating, DateTime now) {
    final c = card.copy();
    final elapsed = c.lastReview == null
        ? null
        : now.difference(c.lastReview!).inSeconds / 86400.0;

    if (c.stability == null || c.difficulty == null || c.isNew) {
      c.stability = initialStability(rating);
      c.difficulty = initialDifficulty(rating);
    } else if (elapsed != null && elapsed < 1) {
      c.stability = shortTermStability(c.stability!, rating);
      c.difficulty = nextDifficulty(c.difficulty!, rating);
    } else {
      final e = elapsed ?? c.stability!;
      final rr = retrievability(c.stability!, e);
      c.difficulty = nextDifficulty(c.difficulty!, rating);
      c.stability = rating == Rating.again
          ? nextForgetStability(card.difficulty!, card.stability!, rr)
          : nextRecallStability(card.difficulty!, card.stability!, rr, rating);
    }

    final wasReview = card.state == CardState.review;
    final inRelearning = card.state == CardState.relearning;

    if (inRelearning && rating != Rating.again && relearningSteps.isNotEmpty) {
      // kroki powtórek po błędzie
      if (rating == Rating.hard) {
        c.due = now.add(relearningSteps[math.min(c.step, relearningSteps.length - 1)]);
      } else if (c.step + 1 >= relearningSteps.length) {
        _graduate(c, now);
      } else {
        c.step += 1;
        c.due = now.add(relearningSteps[c.step]);
      }
    } else if (rating == Rating.again) {
      if (wasReview) c.lapses += 1;
      if (relearningSteps.isEmpty) {
        _graduate(c, now);
      } else {
        c.state = CardState.relearning;
        c.step = 0;
        c.intervalDays = 0;
        c.due = now.add(relearningSteps[0]);
      }
    } else {
      _graduate(c, now);
    }

    c.reps += 1;
    c.lastReview = now;
    return c;
  }

  /// Ręczne odłożenie pytania („znam je na pewno”): nadpisuje harmonogram — karta wraca dopiero po [days] dniach
  /// (od [rolloverHour] rano), niezależnie od oceny FSRS i ewentualnych kroków powtórek po błędzie.
  /// Stabilność nie spada poniżej [days], żeby kolejna powtórka (przy retencji 90%) przypadała na ten termin.
  FsrsCard snooze(FsrsCard card, int days, DateTime now) {
    final c = card.copy();
    c.state = CardState.review;
    c.step = 0;
    c.intervalDays = days;
    c.due = dueInDays(now, days);
    c.stability = math.max(c.stability ?? 0, days.toDouble());
    c.difficulty ??= initialDifficulty(Rating.good);
    c.lastReview ??= now;
    return c;
  }

  void _graduate(FsrsCard c, DateTime now) {
    c.state = CardState.review;
    c.step = 0;
    c.intervalDays = nextIntervalDays(c.stability!);
    c.due = dueInDays(now, c.intervalDays);
  }

  /// Etykieta „kiedy wróci” dla użytkownika.
  static String dueLabel(DateTime due, DateTime now) {
    final diff = due.difference(now);
    if (diff.inMinutes < 1) return 'za chwilę';
    if (diff.inMinutes < 60) return 'za ${diff.inMinutes} min';
    if (diff.inHours < 24) return 'za ${diff.inHours} godz.';
    final days = (diff.inHours / 24).round();
    return days == 1 ? 'jutro' : 'za $days dni';
  }
}

/// Przeniesienie karty z SM-2 do FSRS (migracja danych użytkownika).
class Sm2Migration {
  static const _msPerDay = 86400000;

  /// Zwraca pola nowej karty. [rolloverHour] — godzina zmiany dnia.
  static Map<String, Object?> convert({
    required int repetitions,
    required int intervalDays,
    required double easeFactor,
    required int dueMs,
    required int lapses,
    int rolloverHour = 4,
  }) {
    if (repetitions == 0 && intervalDays == 0) {
      return {'state': 0, 'step': 0, 'stability': null, 'difficulty': null, 'last_review_ms': null};
    }
    final interval = math.max(intervalDays, 1);
    // EF 2.5 ≈ trudność 5; mniejsze EF = trudniejsze pytanie.
    final difficulty = (5 + (2.5 - easeFactor) * (4 / 1.2)).clamp(1.0, 10.0);
    // Termin: od rana (godzina zmiany dnia) zaplanowanego dnia, nie co do godziny.
    final due = DateTime.fromMillisecondsSinceEpoch(dueMs);
    final shifted = due.subtract(Duration(hours: rolloverHour));
    final dayStart = DateTime(shifted.year, shifted.month, shifted.day, rolloverHour);
    final newDue = dayStart.isBefore(due) ? dayStart : due;
    return {
      'state': 2,
      'step': 0,
      'stability': interval.toDouble(),
      'difficulty': difficulty,
      'last_review_ms': dueMs - interval * _msPerDay,
      'due_ms': newDue.millisecondsSinceEpoch,
    };
  }
}
