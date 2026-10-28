import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:memonic_app/widgets/app_drawer.dart';

void main() {
  testWidgets('menu zawiera Statystyki i Powtórka trudnych', (tester) async {
    final router = GoRouter(routes: [
      GoRoute(path: '/', builder: (_, __) => Scaffold(appBar: AppBar(), drawer: const AppDrawer(), body: const SizedBox())),
      GoRoute(path: '/stats', builder: (_, __) => const Text('STATS')),
      GoRoute(path: '/hardest', builder: (_, __) => const Text('HARDEST')),
    ]);
    await tester.pumpWidget(MaterialApp.router(routerConfig: router));
    await tester.tap(find.byTooltip('Open navigation menu'));
    await tester.pumpAndSettle();
    expect(find.text('Statystyki'), findsOneWidget);
    expect(find.text('Powtórka trudnych'), findsOneWidget);
    await tester.tap(find.text('Statystyki'));
    await tester.pumpAndSettle();
    expect(find.text('STATS'), findsOneWidget);
  });
}
