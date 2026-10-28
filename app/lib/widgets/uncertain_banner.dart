import 'package:flutter/material.dart';

/// Wzmianka przy pytaniu oznaczonym jako niepewne (pomarańczowe tło): pogrubiony czerwony napis.
class UncertainBanner extends StatelessWidget {
  const UncertainBanner({super.key});

  static const text = 'Odpowiedź niepewna! (Jeśli znasz odp. to edytuj pytanie w Bazie Pytań w apce.)';

  @override
  Widget build(BuildContext context) => const Text(
        text,
        key: ValueKey('uncertain-banner'),
        style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold, color: Color(0xFFC62828)),
      );
}
