import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'features/database/database_list_screen.dart';
import 'features/database/question_edit_screen.dart';
import 'features/home/home_screen.dart';
import 'features/manual/manual_screen.dart';
import 'features/settings/settings_screen.dart';
import 'features/slideshow/slideshow_screen.dart';
import 'features/stats/drill_screen.dart';
import 'features/stats/stats_screen.dart';
import 'features/study/study_screen.dart';
import 'features/test/test_screen.dart';
import 'providers/theme_provider.dart';

final _router = GoRouter(
  routes: [
    GoRoute(path: '/', builder: (_, __) => const HomeScreen()),
    GoRoute(path: '/study', builder: (_, __) => const StudyScreen()),
    GoRoute(path: '/test', builder: (_, __) => const TestScreen()),
    GoRoute(path: '/stats', builder: (_, __) => const StatsScreen()),
    GoRoute(path: '/hardest', builder: (_, __) => const DrillScreen()),
    GoRoute(path: '/slideshow', builder: (_, __) => const SlideshowSetupScreen()),
    GoRoute(path: '/slideshow/play', builder: (_, __) => const SlideshowPlayScreen()),
    GoRoute(path: '/manual', builder: (_, __) => const ManualScreen()),
    GoRoute(path: '/settings', builder: (_, __) => const SettingsScreen()),
    GoRoute(path: '/database', builder: (_, __) => const DatabaseListScreen()),
    GoRoute(
      path: '/database/:id',
      builder: (_, state) {
        final id = int.parse(state.pathParameters['id']!);
        return QuestionEditScreen(questionId: id);
      },
    ),
  ],
);

class MemonicApp extends ConsumerWidget {
  const MemonicApp({super.key});

  static ThemeData _lightTheme() {
    return ThemeData(
      colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF1565C0)),
      useMaterial3: true,
    );
  }

  static ThemeData _darkTheme() {
    return ThemeData(
      colorScheme: ColorScheme.fromSeed(
        seedColor: const Color(0xFF1565C0),
        brightness: Brightness.dark,
      ),
      useMaterial3: true,
    );
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final themeMode = ref.watch(themeModeProvider);

    return MaterialApp.router(
      title: 'Master Exam Mnemonic',
      debugShowCheckedModeBanner: kDebugMode,
      theme: _lightTheme(),
      darkTheme: _darkTheme(),
      themeMode: themeMode,
      routerConfig: _router,
    );
  }
}
