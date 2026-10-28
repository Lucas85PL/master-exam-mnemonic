import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:memonic_app/widgets/answer_keyboard.dart';

void main() {
  testWidgets('cyfry wybierają kolejny wiersz, spacja = dalej', (tester) async {
    final digits = <int>[];
    var spaces = 0;
    await tester.pumpWidget(MaterialApp(
      home: AnswerKeyboard(
        onDigit: digits.add,
        onSpace: () => spaces++,
        child: const Scaffold(body: Text('pytanie')),
      ),
    ));
    await tester.sendKeyEvent(LogicalKeyboardKey.digit1);
    await tester.sendKeyEvent(LogicalKeyboardKey.numpad3);
    await tester.sendKeyEvent(LogicalKeyboardKey.digit9);
    await tester.sendKeyEvent(LogicalKeyboardKey.space);
    await tester.sendKeyEvent(LogicalKeyboardKey.keyA);
    expect(digits, [0, 2, 8]);
    expect(spaces, 1);
  });
}
