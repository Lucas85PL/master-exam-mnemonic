import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:memonic_app/data/ai_disputed.dart';
import 'package:memonic_app/data/question_repository.dart';
import 'package:memonic_app/data/test_history.dart';
import 'package:memonic_app/domain/slideshow.dart';
import 'package:memonic_app/features/slideshow/slideshow_screen.dart';
import 'package:memonic_app/providers/app_providers.dart';
import 'package:memonic_app/widgets/app_drawer.dart';
import 'package:shared_preferences/shared_preferences.dart';

QuestionRow _q(int id, {String correct = 'A'}) => QuestionRow(
      id: id,
      pytanie: 'Pytanie $id',
      poprawnaOdpowiedz: correct,
      odpA: 'Prawidłowa $id',
      odpB: 'Zła B',
      odpC: 'Zła C',
      odpD: null,
    );

void main() {
  group('pickSlideshow', () {
    List<String> keys(int x) => ['id$x'];
    List<int> pick({
      required List<int> tests,
      required List<int> hard,
      required int hardN,
      required List<int> oldest,
      required int oldestN,
    }) =>
        pickSlideshow<int>(
            fromTests: tests, hardRanked: hard, hardN: hardN, oldest: oldest, oldestN: oldestN, keysOf: keys, random: Random(1));

    test('suma pul bez powtórzeń: ID z testów nie jest ponownie brane z najstarszych', () {
      final r = pick(tests: [666, 2], hard: [10, 11, 12], hardN: 2, oldest: [666, 20, 21, 22], oldestN: 2);
      expect(r.toSet(), {666, 2, 10, 11, 20, 21}); // 666 z testów; z najstarszych 20 i 21 (666 pominięte, bez uzupełnienia 22)
      expect(r.length, 6);
    });

    test('pominięty duplikat jest zastępowany kolejnym kandydatem (pula dostarcza tyle, ile wybrano)', () {
      final r = pick(tests: [1], hard: [1, 2, 3], hardN: 2, oldest: [], oldestN: 0);
      expect(r.toSet(), {1, 2, 3});
    });

    test('kopie z jednej grupy (wspólny klucz) też są pomijane', () {
      final r = pickSlideshow<int>(
        fromTests: [1],
        hardRanked: [2, 3],
        hardN: 2,
        oldest: [],
        oldestN: 0,
        keysOf: (x) => x == 1 || x == 2 ? ['G|a', 'id$x'] : ['id$x'],
        random: Random(1),
      );
      expect(r.toSet(), {1, 3});
    });

    test('wyłączone pule (0) niczego nie dodają, a brak kandydatów nie psuje wyniku', () {
      expect(pick(tests: [], hard: [1, 2], hardN: 0, oldest: [3], oldestN: 0), isEmpty);
      expect(pick(tests: [], hard: [1], hardN: 50, oldest: [], oldestN: 10), [1]);
    });
  });

  test('historia: błędne odpowiedzi z N ostatnich testów, z liczbą testów z danymi', () async {
    SharedPreferences.setMockInitialValues({});
    Future<void> add(int day, List<int> wrong, {bool records = true}) => TestHistory.add(TestResult(
          timestamp: DateTime(2026, 10, day),
          total: 10,
          answered: 10,
          correct: 10 - wrong.length,
          passMark: 7,
          perCategory: const {},
          wrongIds: wrong,
          recordsWrong: records,
        ));
    await add(1, [1, 2], records: false); // stary wpis bez listy błędów
    await add(2, [3, 4]);
    await add(3, [4, 5]);
    final last2 = await TestHistory.recentWrong(2);
    expect(last2.ids, {3, 4, 5});
    expect(last2.testsWithData, 2);
    final all = await TestHistory.recentWrong(slideshowAllTests);
    expect(all.ids, {3, 4, 5});
    expect(all.testsWithData, 2);
  });

  testWidgets('menu: kolejność pozycji, Slideshow nad Kontakt', (tester) async {
    final router = GoRouter(routes: [
      GoRoute(path: '/', builder: (_, __) => Scaffold(appBar: AppBar(), drawer: const AppDrawer(), body: const SizedBox())),
      GoRoute(path: '/slideshow', builder: (_, __) => const Text('SLIDE')),
    ]);
    await tester.pumpWidget(MaterialApp.router(routerConfig: router));
    await tester.tap(find.byTooltip('Open navigation menu'));
    await tester.pumpAndSettle();
    // kolejność pozycji menu od góry
    const order = ['Start', 'Powtórka trudnych', 'Statystyki', 'Slideshow', 'Baza Pytań', 'Ustawienia', 'Manual', 'Kontakt'];
    final ys = [for (final t in order) tester.getTopLeft(find.text(t)).dy];
    for (var i = 1; i < ys.length; i++) {
      expect(ys[i] > ys[i - 1], isTrue, reason: '${order[i]} powinno być pod ${order[i - 1]}');
    }
    await tester.tap(find.text('Slideshow'));
    await tester.pumpAndSettle();
    expect(find.text('SLIDE'), findsOneWidget);
  });

  testWidgets('pokaz: pytanie i tylko poprawna odpowiedź, spacja = Dalej, na końcu „Koniec”', (tester) async {
    await tester.pumpWidget(ProviderScope(
      overrides: [slideshowQueueProvider.overrideWith((ref) => [_q(1), _q(2, correct: 'B')])],
      child: const MaterialApp(home: SlideshowPlayScreen()),
    ));
    await tester.pumpAndSettle();
    expect(find.text('Slideshow  1 / 2'), findsOneWidget);
    expect(find.text('Pytanie 1'), findsOneWidget);
    expect(find.text('Prawidłowa 1'), findsOneWidget);
    expect(find.text('Zła B'), findsNothing); // tylko prawidłowa odpowiedź, bez pozostałych i bez liter
    expect(find.text('Wyjaśnij'), findsOneWidget);
    await tester.sendKeyEvent(LogicalKeyboardKey.space);
    await tester.pumpAndSettle();
    expect(find.text('Slideshow  2 / 2'), findsOneWidget);
    expect(find.text('Zła B'), findsOneWidget); // pytanie 2 ma klucz B, więc to ona jest prawidłowa
    await tester.tap(find.byKey(const ValueKey('slide-next')));
    await tester.pumpAndSettle();
    expect(find.textContaining('Koniec'), findsOneWidget);
  });

  testWidgets('pokaz: niepewne pytanie jest na pomarańczowo z napisem; zwykłe bez', (tester) async {
    AiDisputed.ids = {1};
    addTearDown(() => AiDisputed.ids = {});
    await tester.pumpWidget(ProviderScope(
      overrides: [slideshowQueueProvider.overrideWith((ref) => [_q(1), _q(2)])],
      child: const MaterialApp(home: SlideshowPlayScreen()),
    ));
    await tester.pumpAndSettle();
    expect(find.byKey(const ValueKey('uncertain-banner')), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('slide-next')));
    await tester.pumpAndSettle();
    expect(find.byKey(const ValueKey('uncertain-banner')), findsNothing);
  });

  testWidgets('ustawienia: przełącznik Wszystkie / Bez niepewnych (domyślnie Wszystkie)', (tester) async {
    SharedPreferences.setMockInitialValues({});
    await tester.pumpWidget(const ProviderScope(child: MaterialApp(home: SlideshowSetupScreen())));
    await tester.pumpAndSettle();
    final seg = find.byKey(const ValueKey('slide-uncertain'));
    expect(seg, findsOneWidget);
    expect(tester.widget<SegmentedButton<bool>>(seg).selected, {true});
    await tester.tap(find.text('Bez niepewnych'));
    await tester.pumpAndSettle();
    expect(tester.widget<SegmentedButton<bool>>(seg).selected, {false});
  });
}
