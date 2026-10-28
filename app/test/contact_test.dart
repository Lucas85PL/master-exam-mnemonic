import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:memonic_app/widgets/app_drawer.dart';

void main() {
  testWidgets('menu: Kontakt pod Manual pokazuje imię i e-mail', (tester) async {
    final router = GoRouter(routes: [
      GoRoute(path: '/', builder: (_, __) => Scaffold(appBar: AppBar(), drawer: const AppDrawer(), body: const SizedBox())),
    ]);
    await tester.pumpWidget(MaterialApp.router(routerConfig: router));
    await tester.tap(find.byTooltip('Open navigation menu'));
    await tester.pumpAndSettle();
    final db = tester.getTopLeft(find.text('Manual')).dy;
    final contact = tester.getTopLeft(find.text('Kontakt')).dy;
    expect(contact, greaterThan(db)); // Kontakt jest pod „Manual”
    await tester.ensureVisible(find.text('Kontakt')); // menu urosło (Slideshow) — Kontakt może być poza ekranem testu
    await tester.pumpAndSettle();
    await tester.tap(find.text('Kontakt'));
    await tester.pumpAndSettle();
    expect(find.text('Lukasz\nacardo1985@gmail.com'), findsOneWidget);
    expect(find.text('Kopiuj e-mail'), findsOneWidget);
  });
}
