import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:memonic_app/widgets/question_image.dart';

void main() {
  testWidgets('obrazek pytania mieści się na telefonie i na PC, tap otwiera powiększenie', (tester) async {
    for (final size in const [Size(360, 640), Size(1280, 800)]) {
      tester.view.physicalSize = size;
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      await tester.pumpWidget(const MaterialApp(
        home: Scaffold(
          body: Padding(
            padding: EdgeInsets.all(16),
            child: QuestionImage(imagePath: 'f1p6_25f98605e6.png'),
          ),
        ),
      ));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      final box = tester.getSize(find.byType(QuestionImage));
      expect(box.width, lessThanOrEqualTo(size.width));
      final img = tester.getSize(find.byType(Image));
      expect(img.height, lessThanOrEqualTo(size.height * 0.3 + 1));
      expect(find.text('Brak obrazka'), findsNothing);
      await tester.tap(find.byType(QuestionImage));
      await tester.pumpAndSettle();
      expect(find.byType(InteractiveViewer), findsOneWidget);
      await tester.tapAt(const Offset(2, 2));
      await tester.pumpAndSettle();
    }
  });
}
