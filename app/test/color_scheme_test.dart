import 'package:flutter_test/flutter_test.dart';
import 'package:memonic_app/theme/answer_highlight_colors.dart';

void main() {
  test('answer highlights differ between light and dark', () {
    expect(
      AnswerHighlightColors.light.correctBackground,
      isNot(AnswerHighlightColors.dark.correctBackground),
    );
    expect(
      AnswerHighlightColors.light.wrongBackground,
      isNot(AnswerHighlightColors.dark.wrongBackground),
    );
  });
}
