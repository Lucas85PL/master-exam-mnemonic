import 'dart:math' as math;

/// Liczba kolejnych dni nauki z poprawną odpowiedzią, po której pytanie uznajemy za „znane”.
const knownStreakDays = 3;

/// Na ile dni przed egzaminem materiał ma być już „znany” (bufor na powtórkę).
const examBufferDays = 3;

/// Po tylu błędach w ostatnich 10 odpowiedziach pytanie jest „trudne”.
const hardWrongOfLast10 = 3;

/// Maksymalny odstęp (dni) dla pytania „trudnego” — wraca częściej niż zwykłe.
const hardMaxIntervalDays = 3;

/// Numer dnia nauki (dni od 1970-01-01, czasu lokalnego); nowy dzień zaczyna się o [rolloverHour] (domyślnie 4:00).
int studyDayOf(DateTime t, {int rolloverHour = 4}) {
  final s = t.subtract(Duration(hours: rolloverHour));
  return DateTime.utc(s.year, s.month, s.day).millisecondsSinceEpoch ~/ 86400000;
}

/// Numer dnia nauki dla daty kalendarzowej (np. termin egzaminu).
int studyDayOfDate(DateTime d) => DateTime.utc(d.year, d.month, d.day).millisecondsSinceEpoch ~/ 86400000;

class StreakState {
  const StreakState(this.days, this.lastGoodDay);

  /// Ile kolejnych DNI NAUKI pytanie dostało poprawną odpowiedź (wiele odpowiedzi tego samego dnia liczy się raz).
  final int days;
  final int? lastGoodDay;
}

/// Aktualizacja serii po odpowiedzi: poprawna w nowym dniu nauki +1, w tym samym dniu bez zmian, błąd zeruje.
StreakState nextStreak(StreakState s, {required bool correct, required int today}) {
  if (!correct) return StreakState(0, s.lastGoodDay);
  if (s.lastGoodDay == today) return s;
  return StreakState(math.min(s.days + 1, 99), today);
}

bool isKnown(int streakDays) => streakDays >= knownStreakDays;

/// Co ile pytań wstawić nowe (nigdy niewidziane) — dynamicznie wg skuteczności w ostatnich odpowiedziach sesji.
/// Dobra passa → co 3, słaba → co 8, brak danych → co 5.
int newCardGap(List<bool> recent) {
  final r = recent.length > 10 ? recent.sublist(recent.length - 10) : recent;
  if (r.length < 3) return 5;
  final acc = r.where((x) => x).length / r.length;
  if (acc >= 0.9) return 3;
  if (acc >= 0.8) return 4;
  if (acc >= 0.7) return 5;
  if (acc >= 0.6) return 6;
  if (acc >= 0.5) return 7;
  return 8;
}

/// Pytanie „trudne”: często błędnie zaznaczane (≥3 błędy w ostatnich 10 odpowiedziach)
/// albo wiele błędów w powtórkach (≥3 lapsów), a wciąż bez serii dni.
bool computeHard({required int wrongOfLast10, required int lapses, required int streakDays}) {
  return wrongOfLast10 >= hardWrongOfLast10 || (lapses >= 3 && !isKnown(streakDays));
}

/// Skraca interwał FSRS tak, by pytanie wróciło przed końcem przygotowań do egzaminu
/// (inaczej FSRS rozsuwa powtórki np. na 11 i 46 dni i seria 3 dni nie zdąży się zamknąć).
/// [streakAfter] — seria po tej odpowiedzi; [targetDay] — dzień, do którego materiał ma być znany.
int capIntervalForExam({
  required int intervalDays,
  required int streakAfter,
  required int today,
  required int? targetDay,
}) {
  if (targetDay == null) return intervalDays;
  final remainingDays = targetDay - today;
  final needed = knownStreakDays - streakAfter;
  if (needed <= 0) return math.min(intervalDays, math.max(1, remainingDays ~/ 2)); // znane: utrzymanie do egzaminu
  final cap = math.max(1, remainingDays ~/ (needed + 1));
  return math.min(intervalDays, cap);
}

/// Najkrótszy możliwy czas (dni) na zdobycie [remainingUnits] jednostek serii przez jedno pytanie: seria rośnie najwyżej
/// raz na dzień nauki, a kolejne powtórki dzieli co najmniej ~2 dni (pierwsza powtórka FSRS po poprawnej odpowiedzi).
int minDaysForUnits(int maxRemainingUnitsPerQuestion) =>
    maxRemainingUnitsPerQuestion <= 1 ? 1 : (maxRemainingUnitsPerQuestion - 1) * 2 + 1;

/// Okno, z którego liczone jest aktualne tempo nauki (dni).
const paceWindowDays = 14;

/// Założenie startowe: tyle odpowiedzi przypada średnio na 1 „jednostkę serii” (jedno pytanie × 1 dzień poprawnej serii) —
/// uwzględnia błędy i powtórki tego samego dnia. Waga założenia maleje w miarę zbierania własnych danych.
const priorAnswersPerUnit = 1.4;
const priorWeightUnits = 10;

/// Tempo nauki z dziennika odpowiedzi (okno ostatnich [paceWindowDays] dni, wybrany dział).
class PaceStats {
  const PaceStats({this.answers = 0, this.netUnits = 0, this.mastered = 0, this.windowDays = 1, this.unitsToday = 0});

  /// Odpowiedzi w oknie (tylko z zapisaną serią).
  final int answers;

  /// Przyrost serii netto w oknie (Σ seria po − seria przed; błędy zerujące serię zmniejszają wynik).
  final int netUnits;

  /// Ile pytań w oknie osiągnęło status „znane” (seria ≥ 3).
  final int mastered;

  /// Długość okna w dniach (≥ 1; krótsza, gdy dane są świeże).
  final int windowDays;

  /// Przyrost serii netto dzisiaj.
  final int unitsToday;
}

/// Podsumowanie postępu i dziennego celu do egzaminu — **na podstawie aktualnego tempa nauki**.
///
/// Model: pytanie jest „znane” po serii 3 dni nauki; do opanowania całej puli brakuje [remainingReviews] jednostek serii
/// (Σ(3 − seria)). Z dziennika odpowiedzi liczymy, ile odpowiedzi kosztuje jedna jednostka ([costPerUnit] — uwzględnia
/// Twoje błędy i powtórki), a cel dzienny = koszt × pozostała praca / dni do terminu (egzamin − [examBufferDays] dni).
/// Prognoza: przy dotychczasowym przyroście jednostek na dzień ([unitsPerDay]) materiał zostanie opanowany za [projectedDays] dni.
class DailyPlan {
  const DailyPlan({
    required this.total,
    required this.known,
    required this.remainingReviews,
    required this.daysLeft,
    required this.perDay,
    required this.doneToday,
    required this.goalToday,
    required this.hasExam,
    required this.tooLate,
    this.costPerUnit = priorAnswersPerUnit,
    this.answersPerDay = 0,
    this.unitsPerDay = 0,
    this.masteredPerDay = 0,
    this.projectedDays,
    this.windowDays = 1,
    this.hasOwnData = false,
  });

  final int total;
  final int known;

  /// Ile jednostek serii brakuje, by wszystkie pytania miały serię 3 dni.
  final int remainingReviews;

  /// Dni nauki do „terminu docelowego” (egzamin − bufor), włącznie z dzisiejszym; 0 = po terminie.
  final int daysLeft;

  /// Szacunek: ile odpowiedzi dziennie przerabiać w pozostałym czasie (= cel na dziś).
  final int perDay;
  final int doneToday;

  /// Cel na dziś (stały w ciągu dnia).
  final int goalToday;
  final bool hasExam;

  /// Zostało mniej dni niż trzeba na serię 3 dni nauki.
  final bool tooLate;

  /// Średni koszt (liczba odpowiedzi) jednej jednostki serii — z Twojego tempa, z domieszką założenia startowego.
  final double costPerUnit;

  /// Średnia liczba odpowiedzi na dzień w oknie ostatnich dni.
  final double answersPerDay;

  /// Przyrost serii (netto) na dzień w oknie; 3 jednostki = jedno opanowane pytanie.
  final double unitsPerDay;

  /// Ile pytań dziennie osiąga status „znane”.
  final double masteredPerDay;

  /// Za ile dni (przy dotychczasowym tempie przyrostu) materiał będzie opanowany; null = brak przyrostu / dane zbyt skąpe.
  final int? projectedDays;
  final int windowDays;

  /// true, gdy w dzienniku jest już dość własnych danych (a nie tylko założenie startowe).
  final bool hasOwnData;

  double get progress => total == 0 ? 0 : known / total;

  /// Przy dotychczasowym tempie zdążysz do terminu docelowego (null = nie da się ocenić).
  bool? get onTrack => !hasExam || projectedDays == null ? null : projectedDays! <= daysLeft;

  static DailyPlan compute({
    required int total,
    required int known,
    required int remainingReviews,
    required int doneToday,
    required int today,
    required int? examDay,
    PaceStats pace = const PaceStats(),
    int minDaysToFinish = 1,
  }) {
    final units = math.max(0, pace.netUnits);
    final cost = (pace.answers + priorWeightUnits * priorAnswersPerUnit) / (units + priorWeightUnits);
    final unitsPerDay = units / pace.windowDays;
    final answersPerDay = pace.answers / pace.windowDays;
    final masteredPerDay = pace.mastered / pace.windowDays;
    // seria liczy się raz na dzień nauki i powtórki są rozsunięte w czasie, więc nawet przy ogromnym tempie
    // opanowanie nie nastąpi szybciej niż [minDaysToFinish] (zależy od najmniej zaawansowanego pytania)
    final projected = remainingReviews == 0
        ? 0
        : (unitsPerDay >= 0.05 ? math.max((remainingReviews / unitsPerDay).ceil(), minDaysToFinish) : null);
    final own = pace.answers >= 40;
    if (examDay == null) {
      return DailyPlan(
        total: total, known: known, remainingReviews: remainingReviews, daysLeft: 0, perDay: 0,
        doneToday: doneToday, goalToday: 0, hasExam: false, tooLate: false, costPerUnit: cost,
        answersPerDay: answersPerDay, unitsPerDay: unitsPerDay, masteredPerDay: masteredPerDay,
        projectedDays: projected, windowDays: pace.windowDays, hasOwnData: own,
      );
    }
    final target = examDay - examBufferDays;
    final daysLeft = math.max(0, target - today + 1);
    // praca na początku dnia = pozostała + dzisiejszy przyrost — cel nie rośnie w trakcie nauki
    final startRemaining = remainingReviews + math.max(0, pace.unitsToday);
    final needed = (cost * startRemaining).ceil();
    final perDay = startRemaining == 0 ? 0 : (daysLeft == 0 ? needed : (needed / daysLeft).ceil());
    return DailyPlan(
      total: total, known: known, remainingReviews: remainingReviews, daysLeft: daysLeft, perDay: perDay,
      doneToday: doneToday, goalToday: perDay, hasExam: true,
      tooLate: remainingReviews > 0 && daysLeft < knownStreakDays,
      costPerUnit: cost, answersPerDay: answersPerDay, unitsPerDay: unitsPerDay, masteredPerDay: masteredPerDay,
      projectedDays: projected, windowDays: pace.windowDays, hasOwnData: own,
    );
  }
}
