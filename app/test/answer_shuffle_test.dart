import 'dart:math';

import 'package:flutter_test/flutter_test.dart';
import 'package:memonic_app/data/question_repository.dart';
import 'package:memonic_app/domain/answer_shuffle.dart';

QuestionRow q({String a = 'aaa aaa', String b = 'bbb bbb', String c = 'ccc ccc', String? d, String key = 'B'}) => QuestionRow(
      id: 1, pytanie: 'Pytanie', poprawnaOdpowiedz: key, odpA: a, odpB: b, odpC: c, odpD: d);

void main() {
  test('mieszanie zachowuje poprawną treść i mapę liter', () {
    for (var seed = 0; seed < 50; seed++) {
      final base = q(d: 'ddd ddd', key: 'C');
      final s = shuffleAnswers(base, Random(seed));
      expect(s.correctText, base.correctText); // pod nową literą jest ta sama treść
      expect(s.original, same(base));
      expect(s.visibleOptions.map((e) => e.key), ['A', 'B', 'C', 'D']); // wiersze nadal A, B, C, D
      expect({for (final e in s.visibleOptions) e.value}, {'aaa aaa', 'bbb bbb', 'ccc ccc', 'ddd ddd'});
      expect(s.originalLetterOf(s.poprawnaOdpowiedz), 'C');
    }
  });

  test('litera poprawnej odpowiedzi faktycznie się zmienia', () {
    final letters = {for (var seed = 0; seed < 60; seed++) shuffleAnswers(q(), Random(seed)).poprawnaOdpowiedz};
    expect(letters.length, 3);
  });

  test('pytania z odniesieniami do innych odpowiedzi nie są mieszane', () {
    for (final c in ['wszystkie powyższe', 'żadna z powyższych', 'A i B', 'obie odpowiedzi', 'a) i b)']) {
      final base = q(c: c);
      expect(canShuffleAnswers(base), isFalse, reason: c);
      expect(identical(shuffleAnswers(base, Random(1)), base), isTrue);
    }
  });

  test('wyjaśnienie dostaje litery widoczne na ekranie', () {
    final base = q(key: 'A');
    // A→C, B→A, C→B
    final s = shuffleAnswers(base, Random(3));
    final map = s.letterMap!;
    final text = remapExplanationLetters('Prawidłowa odpowiedź to A. Wariant B jest błędny, odpowiedź C też.', map);
    expect(text, 'Prawidłowa odpowiedź to ${map['A']}. Wariant ${map['B']} jest błędny, odpowiedź ${map['C']} też.');
    expect(remapExplanationLetters('Tekst bez liter', null), 'Tekst bez liter');
  });
}
