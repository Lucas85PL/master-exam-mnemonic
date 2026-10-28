import 'package:flutter/material.dart';

/// Obrazek pytania (`assets/question_images/<plik>`): skaluje się do szerokości ekranu
/// (PC i telefon), ma biało tło (flagi/rysunki są jasne także w trybie ciemnym),
/// dotknięcie otwiera powiększenie.
class QuestionImage extends StatelessWidget {
  const QuestionImage({super.key, required this.imagePath});

  final String imagePath;

  static String assetOf(String imagePath) => 'assets/question_images/$imagePath';

  @override
  Widget build(BuildContext context) {
    final maxHeight = MediaQuery.sizeOf(context).height * 0.3;
    return Center(
      child: GestureDetector(
        onTap: () => _zoom(context),
        child: Container(
          constraints: BoxConstraints(maxWidth: 420, maxHeight: maxHeight.clamp(120, 320)),
          padding: const EdgeInsets.all(8),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: Colors.black12),
          ),
          child: Image.asset(
            assetOf(imagePath),
            fit: BoxFit.contain,
            filterQuality: FilterQuality.medium,
            semanticLabel: 'Rysunek do pytania',
            errorBuilder: (_, __, ___) => const Padding(
              padding: EdgeInsets.all(16),
              child: Text('Brak obrazka', style: TextStyle(color: Colors.black54)),
            ),
          ),
        ),
      ),
    );
  }

  void _zoom(BuildContext context) {
    showDialog<void>(
      context: context,
      builder: (ctx) => Dialog(
        backgroundColor: Colors.white,
        insetPadding: const EdgeInsets.all(12),
        child: InteractiveViewer(
          minScale: 1,
          maxScale: 6,
          child: GestureDetector(
            onTap: () => Navigator.of(ctx).pop(),
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Image.asset(
                assetOf(imagePath),
                fit: BoxFit.contain,
                filterQuality: FilterQuality.medium,
              ),
            ),
          ),
        ),
      ),
    );
  }
}
