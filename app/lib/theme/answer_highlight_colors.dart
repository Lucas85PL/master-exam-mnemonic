import 'package:flutter/material.dart';

/// Kolory podświetlenia odpowiedzi po wyborze (zielony / czerwony, czytelne w day i dark).
class AnswerHighlightColors {
  const AnswerHighlightColors({
    required this.correctBackground,
    required this.correctForeground,
    required this.wrongBackground,
    required this.wrongForeground,
    required this.feedbackCorrect,
    required this.feedbackWrong,
  });

  final Color correctBackground;
  final Color correctForeground;
  final Color wrongBackground;
  final Color wrongForeground;
  final Color feedbackCorrect;
  final Color feedbackWrong;

  static AnswerHighlightColors forBrightness(Brightness brightness) {
    return brightness == Brightness.dark ? dark : light;
  }

  static AnswerHighlightColors of(BuildContext context) {
    return forBrightness(Theme.of(context).brightness);
  }

  /// Jasny motyw: jasne tła, ciemny tekst.
  static const light = AnswerHighlightColors(
    correctBackground: Color(0xFFC8E6C9),
    correctForeground: Color(0xFF1B5E20),
    wrongBackground: Color(0xFFFFCDD2),
    wrongForeground: Color(0xFFB71C1C),
    feedbackCorrect: Color(0xFF2E7D32),
    feedbackWrong: Color(0xFFC62828),
  );

  /// Ciemny motyw: ciemne tła, jasny tekst.
  static const dark = AnswerHighlightColors(
    correctBackground: Color(0xFF2E7D32),
    correctForeground: Color(0xFFE8F5E9),
    wrongBackground: Color(0xFF7F1D1D),
    wrongForeground: Color(0xFFFFEBEE),
    feedbackCorrect: Color(0xFFA5D6A7),
    feedbackWrong: Color(0xFFEF9A9A),
  );
}
