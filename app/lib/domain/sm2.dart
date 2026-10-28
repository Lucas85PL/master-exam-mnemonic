/// Klasyczny algorytm SM-2 (SuperMemo 2, 1987).
///
/// Jakość z odpowiedzi MC: poprawna = 5, błędna = 2 (poniżej progu 3).
class Sm2Card {
  Sm2Card({
    required this.questionId,
    this.repetitions = 0,
    this.intervalDays = 0,
    this.easeFactor = 2.5,
    DateTime? due,
    this.lapses = 0,
  }) : due = due ?? DateTime.now();

  final int questionId;
  int repetitions;
  int intervalDays;
  double easeFactor;
  DateTime due;
  int lapses;

  /// Karta nigdy nie oceniana w sesji (pula „nowe”).
  bool get isNew => repetitions == 0 && intervalDays == 0;

  Sm2Card copyWith({
    int? repetitions,
    int? intervalDays,
    double? easeFactor,
    DateTime? due,
    int? lapses,
  }) {
    return Sm2Card(
      questionId: questionId,
      repetitions: repetitions ?? this.repetitions,
      intervalDays: intervalDays ?? this.intervalDays,
      easeFactor: easeFactor ?? this.easeFactor,
      due: due ?? this.due,
      lapses: lapses ?? this.lapses,
    );
  }
}

const double sm2MinimumEase = 1.3;

int qualityFromCorrect(bool correct) => correct ? 5 : 2;

/// Aktualizuje kartę według SM-2 po ocenie [quality] (0–5).
Sm2Card scheduleReview(Sm2Card card, int quality) {
  assert(quality >= 0 && quality <= 5);

  var repetitions = card.repetitions;
  var interval = card.intervalDays;
  var ef = card.easeFactor;
  var lapses = card.lapses;

  if (quality < 3) {
    repetitions = 0;
    interval = 1;
    lapses += 1;
  } else {
    if (repetitions == 0) {
      interval = 1;
    } else if (repetitions == 1) {
      interval = 6;
    } else {
      interval = (interval * ef).round().clamp(1, 36500);
    }
    repetitions += 1;
  }

  ef += 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02);
  if (ef < sm2MinimumEase) ef = sm2MinimumEase;

  final due = DateTime.now().add(Duration(days: interval));

  return Sm2Card(
    questionId: card.questionId,
    repetitions: repetitions,
    intervalDays: interval,
    easeFactor: ef,
    due: due,
    lapses: lapses,
  );
}

/// Zachowanie z study_screen (poprawna / błędna).
Sm2Card scheduleFromMcAnswer(Sm2Card card, bool correct) {
  return scheduleReview(card, qualityFromCorrect(correct));
}
