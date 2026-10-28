import 'dart:math';

/// „Wszystkie” w liście wyboru testów (historia przechowuje ostatnie 200).
const slideshowAllTests = 1000;

/// Dostępne wartości list wyboru Slideshow; 0 = ta pula wyłączona.
const slideshowTestChoices = [0, 5, 10, 15, slideshowAllTests];
const slideshowCountChoices = [0, 10, 50, 100, 150, 200];

/// Pytanie „trudne” w Slideshow: ma błędy i wygładzoną trudność ((błędy+1)/(odpowiedzi+2)) co najmniej taką.
const slideshowMinDifficulty = 0.4;

/// Składa listę pytań do Slideshow z trzech pul, **bez powtórzeń** (wspólne klucze „to samo pytanie” z [keysOf] — także
/// kopie pod innym ID). Kolejność pul: błędy z testów ([fromTests], wszystkie), potem trudne ([hardRanked], od najświeższego
/// błędu, [hardN] sztuk), potem najstarsze ([oldest], od najdawniej widzianego, [oldestN] sztuk). Pytanie, które już jest w
/// wcześniejszej puli, jest pomijane i zastępowane kolejnym z listy, więc każda pula dostarcza tyle, ile wybrano (o ile ma kandydatów).
/// Wynik jest tasowany.
List<T> pickSlideshow<T>({
  required List<T> fromTests,
  required List<T> hardRanked,
  required int hardN,
  required List<T> oldest,
  required int oldestN,
  required Iterable<String> Function(T) keysOf,
  Random? random,
}) {
  final seen = <String>{};
  final out = <T>[];
  void add(Iterable<T> source, int? limit) {
    var taken = 0;
    for (final q in source) {
      if (limit != null && taken >= limit) break;
      final keys = keysOf(q).toList();
      if (keys.any(seen.contains)) continue;
      seen.addAll(keys);
      out.add(q);
      taken++;
    }
  }

  add(fromTests, null);
  add(hardRanked, hardN);
  add(oldest, oldestN);
  return out..shuffle(random ?? Random());
}
