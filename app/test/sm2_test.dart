import 'package:flutter_test/flutter_test.dart';
import 'package:memonic_app/domain/sm2.dart';

void main() {
  test('quality 5 on new card sets interval 1 and repetitions 1', () {
    final card = scheduleReview(Sm2Card(questionId: 1), 5);
    expect(card.repetitions, 1);
    expect(card.intervalDays, 1);
    expect(card.isNew, isFalse);
  });

  test('second success uses interval 6', () {
    var card = Sm2Card(questionId: 1, repetitions: 1, intervalDays: 1);
    card = scheduleReview(card, 5);
    expect(card.repetitions, 2);
    expect(card.intervalDays, 6);
  });

  test('quality 2 resets repetitions and sets interval 1', () {
    var card = Sm2Card(
      questionId: 2,
      repetitions: 5,
      intervalDays: 10,
      easeFactor: 2.5,
    );
    card = scheduleReview(card, 2);
    expect(card.repetitions, 0);
    expect(card.intervalDays, 1);
    expect(card.lapses, 1);
    expect(
      card.due.isAfter(DateTime.now().subtract(const Duration(hours: 1))),
      isTrue,
    );
  });

  test('third success on review multiplies interval by EF', () {
    var card = Sm2Card(
      questionId: 3,
      repetitions: 2,
      intervalDays: 6,
      easeFactor: 2.5,
    );
    card = scheduleReview(card, 5);
    expect(card.repetitions, 3);
    expect(card.intervalDays, 15);
  });

  test('scheduleFromMcAnswer maps correct and wrong', () {
    final fresh = Sm2Card(questionId: 4);
    final good = scheduleFromMcAnswer(fresh, true);
    expect(good.repetitions, 1);

    final bad = scheduleFromMcAnswer(good, false);
    expect(bad.repetitions, 0);
    expect(bad.intervalDays, 1);
  });

  test('ease factor does not drop below 1.3', () {
    var card = Sm2Card(questionId: 5, repetitions: 2, intervalDays: 6);
    for (var i = 0; i < 10; i++) {
      card = scheduleReview(card, 2);
    }
    expect(card.easeFactor, greaterThanOrEqualTo(sm2MinimumEase));
  });
}
