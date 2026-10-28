import 'dart:math';

import '../data/question_repository.dart';

/// Odpowiedzi w treści odwołujące się do innych odpowiedzi lub do pozycji („wszystkie powyższe”, „A i B”, „żadna z…”) —
/// takich pytań nie mieszamy, bo zmiana kolejności zmieniłaby ich sens.
final _positional = RegExp(
  r'powyższ|poniższ|wszystkie|żadn[aeyo]|\bobie\b|\boba\b|obydwa|oboje|wymienion|'
  r'\b[A-D]\s*(i|oraz|\+|,|lub|and|or|-|–)\s*[A-D]\b|\b[a-dA-D]\)|\bboth\b|all of|none of|above|below',
  caseSensitive: false,
);

/// Czy kolejność odpowiedzi tego pytania można bezpiecznie wymieszać.
bool canShuffleAnswers(QuestionRow q) {
  final opts = q.visibleOptions;
  if (opts.length < 2) return false;
  for (final o in opts) {
    if (o.value.length <= 2) return false; // same litery/liczby w wierszach
    if (_positional.hasMatch(o.value)) return false;
  }
  return true;
}

/// Zwraca kopię pytania z losowo ułożonymi treściami odpowiedzi pod A/B/C(/D). Wiersze nadal wyświetlają się jako A, B, C…,
/// a poprawna litera jest przeliczona. Pytania, których nie wolno mieszać, wracają bez zmian.
QuestionRow shuffleAnswers(QuestionRow q, Random rnd) {
  if (q.original != null || !canShuffleAnswers(q)) return q;
  final text = {'A': q.odpA, 'B': q.odpB, 'C': q.odpC, 'D': q.odpD};
  final slots = q.visibleOptions.map((e) => e.key).toList();
  final perm = [...slots]..shuffle(rnd); // perm[i] = litera oryginalna wyświetlana w wierszu slots[i]
  final map = <String, String>{for (var i = 0; i < slots.length; i++) perm[i]: slots[i]};
  String? at(String slot) {
    final i = slots.indexOf(slot);
    return i < 0 ? text[slot] : text[perm[i]];
  }

  return QuestionRow(
    id: q.id,
    pytanie: q.pytanie,
    poprawnaOdpowiedz: map[q.poprawnaOdpowiedz] ?? q.poprawnaOdpowiedz,
    odpA: at('A'),
    odpB: at('B'),
    odpC: at('C'),
    odpD: at('D'),
    kategoria: q.kategoria,
    reviewStatus: q.reviewStatus,
    studyHidden: q.studyHidden,
    imagePath: q.imagePath,
    hard: q.hard,
    isNewCard: q.isNewCard,
    dupGroup: q.dupGroup,
    original: q,
    letterMap: map,
  );
}

/// Wyjaśnienie powstało dla oryginalnej kolejności odpowiedzi — przepisuje w nim litery („Prawidłowa odpowiedź to C”,
/// „wariant B”) na litery widoczne na ekranie.
String remapExplanationLetters(String text, Map<String, String>? letterMap) {
  if (letterMap == null) return text;
  String m(String l) => letterMap[l] ?? l;
  var out = text.replaceFirstMapped(
    RegExp(r'^(\s*Prawidłowa odpowiedź to )([A-D])\b'),
    (x) => '${x[1]}${m(x[2]!)}',
  );
  out = out.replaceAllMapped(
    RegExp(r'(\b(?:[Ww]ariant\w*|[Oo]dpowiedź|[Oo]dpowiedzi|[Oo]dpowiedzią|[Oo]pcj\w+|[Pp]unkt\w*|[Oo]dp\.)\s+\(?)([A-D])\b'),
    (x) => '${x[1]}${m(x[2]!)}',
  );
  return out;
}
