import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:memonic_app/features/manual/manual_content.dart';
import 'package:memonic_app/features/manual/manual_screen.dart';
import 'package:memonic_app/widgets/app_drawer.dart';

void main() {
  test('manual: każdy wpis ma treść po polsku i angielsku', () {
    for (final s in manualSections) {
      expect(s.title.pl.trim(), isNotEmpty);
      expect(s.title.en.trim(), isNotEmpty);
      expect(s.body, isNotEmpty);
      for (final p in s.body) {
        expect(p.pl.trim(), isNotEmpty);
        expect(p.en.trim(), isNotEmpty);
        expect(p.pl.startsWith('• '), p.en.startsWith('• ')); // lista w obu językach tak samo
      }
    }
  });

  testWidgets('manual: Manual w menu nad Kontakt; przełącznik PL/ENG zmienia język', (tester) async {
    final router = GoRouter(routes: [
      GoRoute(path: '/', builder: (_, __) => Scaffold(appBar: AppBar(), drawer: const AppDrawer(), body: const SizedBox())),
      GoRoute(path: '/manual', builder: (_, __) => const ManualScreen()),
    ]);
    await tester.pumpWidget(ProviderScope(child: MaterialApp.router(routerConfig: router)));
    await tester.tap(find.byTooltip('Open navigation menu'));
    await tester.pumpAndSettle();
    expect(tester.getTopLeft(find.text('Manual')).dy, lessThan(tester.getTopLeft(find.text('Kontakt')).dy));
    await tester.tap(find.text('Manual'));
    await tester.pumpAndSettle();
    expect(find.text('Manual aplikacji'), findsOneWidget);
    expect(find.text('Ekran główny'), findsOneWidget);
    await tester.tap(find.text('ENG'));
    await tester.pumpAndSettle();
    expect(find.text('App manual'), findsOneWidget);
    expect(find.text('Home screen'), findsOneWidget);
  });
}
