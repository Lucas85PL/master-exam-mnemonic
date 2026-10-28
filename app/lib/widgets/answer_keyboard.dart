import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// Skróty klawiaturowe ekranów pytań: cyfry 1–9 (także z klawiatury numerycznej) wybierają kolejny wiersz odpowiedzi,
/// spacja = „Dalej”. Nasłuch jest globalny (nie zależy od tego, który element ma fokus) i działa tylko, gdy ekran
/// jest na wierzchu (nie przy otwartym oknie dialogowym, menu czy panelu).
class AnswerKeyboard extends StatefulWidget {
  const AnswerKeyboard({super.key, required this.onDigit, required this.onSpace, required this.child});

  /// Wywoływane z indeksem odpowiedzi (0 = pierwszy wiersz).
  final void Function(int index) onDigit;
  final VoidCallback onSpace;
  final Widget child;

  static final digits = <LogicalKeyboardKey, int>{
    LogicalKeyboardKey.digit1: 0, LogicalKeyboardKey.numpad1: 0,
    LogicalKeyboardKey.digit2: 1, LogicalKeyboardKey.numpad2: 1,
    LogicalKeyboardKey.digit3: 2, LogicalKeyboardKey.numpad3: 2,
    LogicalKeyboardKey.digit4: 3, LogicalKeyboardKey.numpad4: 3,
    LogicalKeyboardKey.digit5: 4, LogicalKeyboardKey.numpad5: 4,
    LogicalKeyboardKey.digit6: 5, LogicalKeyboardKey.numpad6: 5,
    LogicalKeyboardKey.digit7: 6, LogicalKeyboardKey.numpad7: 6,
    LogicalKeyboardKey.digit8: 7, LogicalKeyboardKey.numpad8: 7,
    LogicalKeyboardKey.digit9: 8, LogicalKeyboardKey.numpad9: 8,
  };

  @override
  State<AnswerKeyboard> createState() => _AnswerKeyboardState();
}

class _AnswerKeyboardState extends State<AnswerKeyboard> {
  @override
  void initState() {
    super.initState();
    HardwareKeyboard.instance.addHandler(_onKey);
  }

  @override
  void dispose() {
    HardwareKeyboard.instance.removeHandler(_onKey);
    super.dispose();
  }

  bool _onKey(KeyEvent event) {
    if (event is! KeyDownEvent || !mounted) return false;
    // tylko gdy ten ekran jest na wierzchu (bez okien dialogowych i paneli)
    if (ModalRoute.of(context)?.isCurrent == false) return false;
    // nie przechwytuj pisania w polach tekstowych
    final focusCtx = FocusManager.instance.primaryFocus?.context;
    if (focusCtx != null && focusCtx.findAncestorWidgetOfExactType<EditableText>() != null) return false;
    final digit = AnswerKeyboard.digits[event.logicalKey];
    if (digit != null) {
      widget.onDigit(digit);
      return true;
    }
    if (event.logicalKey == LogicalKeyboardKey.space) {
      widget.onSpace();
      return true;
    }
    return false;
  }

  @override
  Widget build(BuildContext context) => widget.child;
}
