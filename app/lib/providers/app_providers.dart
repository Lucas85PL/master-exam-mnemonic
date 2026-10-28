import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:sqflite/sqflite.dart';

import '../data/database.dart';
import '../data/explain_service.dart';
import '../data/import_service.dart';
import '../data/question_repository.dart';
import '../data/test_history.dart';
import '../domain/category_filter.dart';
import '../domain/study_plan.dart';
import 'settings_providers.dart';

final databaseProvider = FutureProvider<Database>((ref) async {
  final appDb = await AppDatabase.open();
  return appDb.db;
});

final repositoryProvider = FutureProvider<QuestionRepository>((ref) async {
  final db = await ref.watch(databaseProvider.future);
  return QuestionRepository(db);
});

final importServiceProvider = FutureProvider<ImportService>((ref) async {
  final db = await ref.watch(databaseProvider.future);
  return ImportService(db);
});

final explainServiceProvider = FutureProvider<ExplainService>((ref) async {
  final db = await ref.watch(databaseProvider.future);
  return ExplainService(db);
});

/// true = sesja „powtórz zaplanowane” (karty z terminem w ciągu 24 h, np. błędy na jutro).
final reviewAheadProvider = StateProvider<bool>((ref) => false);

/// true = „Same nowe”: sesja nauki zawiera wyłącznie karty, które jeszcze się nie pojawiły (false = wszystkie).
final newOnlyProvider = StateProvider<bool>((ref) => false);

/// Tryb TESTU: false = Normalny (jak dotąd), true = Trudny (50% z 200 najtrudniejszych, 30% dawno powtarzanych trudniejszych, 20% losowo).
final testHardProvider = StateProvider<bool>((ref) => false);

/// Kolejka ID pytań „Powtórki – najtrudniejsze” (null = zwykła nauka).
final drillQueueProvider = StateProvider<List<int>?>((ref) => null);

/// Wybrane działy do nauki (zaznaczone pola na ekranie głównym); zapamiętywane między uruchomieniami.
final selectedCategoryProvider = StateNotifierProvider<StudyCategoryNotifier, StudyCategory>((ref) => StudyCategoryNotifier());

class StudyCategoryNotifier extends StateNotifier<StudyCategory> {
  StudyCategoryNotifier() : super(_allSelected) {
    ready = _load();
  }

  static const _key = 'study_categories';
  static final _allSelected = StudyCategory.fromSelected({for (final c in StudyCategory.selectable) c.values.first});

  late final Future<void> ready;

  Future<void> _load() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final saved = prefs.getStringList(_key);
      if (saved != null) {
        final picked = StudyCategory.fromSelected(saved.toSet());
        if (!picked.isAll) state = picked;
      }
    } catch (_) {}
  }

  /// Ustawia zaznaczone działy; co najmniej jeden dział musi pozostać zaznaczony (pusty zbiór jest ignorowany).
  Future<void> setSelected(Set<String> dbValues) async {
    final picked = StudyCategory.fromSelected(dbValues);
    if (picked.isAll) return;
    state = picked;
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setStringList(_key, picked.values);
    } catch (_) {}
  }
}

final studyStatsProvider = FutureProvider<StudyStats>((ref) async {
  final repo = await ref.watch(repositoryProvider.future);
  final cat = ref.watch(selectedCategoryProvider);
  final examDate = ref.watch(examDateProvider);
  await ref.read(examDateProvider.notifier).ready;
  final exam = ref.read(examDateProvider) ?? examDate;
  final due = await repo.countDue(cat);
  final newCount = await repo.countNew(cat);
  final total = await repo.countStudyPool(cat);
  final upcoming = await repo.countUpcoming(cat);
  final known = await repo.countKnown(cat);
  final hard = await repo.countHard(cat);
  final remaining = await repo.countRemainingReviews(cat);
  final today = studyDayOf(DateTime.now());
  final doneToday = await repo.countAnswersOnDay(today, category: cat);
  final pace = await repo.paceStats(cat, today);
  final maxRemaining = await repo.maxRemainingUnits(cat);
  final plan = DailyPlan.compute(
    total: total,
    known: known,
    remainingReviews: remaining,
    doneToday: doneToday,
    today: today,
    examDay: exam == null ? null : studyDayOfDate(exam),
    pace: pace,
    minDaysToFinish: minDaysForUnits(maxRemaining),
  );
  return StudyStats(
      due: due, newCards: newCount, total: total, upcoming: upcoming, hard: hard, plan: plan);
});

class StudyStats {
  StudyStats({
    required this.due,
    required this.newCards,
    required this.total,
    required this.plan,
    this.upcoming = 0,
    this.hard = 0,
  });

  /// Zaplanowane na najbliższe ~24 h (np. pytania z błędem na jutro rano).
  final int upcoming;

  final int due;
  final int newCards;
  final int total;

  /// Pytania często błędnie zaznaczane.
  final int hard;

  /// Postęp „znanych” pytań i dzienny cel do egzaminu.
  final DailyPlan plan;
}

/// Wynik ostatniego TESTU (null = nie było testów).
final lastTestProvider = FutureProvider<TestResult?>((ref) async {
  final all = await TestHistory.load();
  return all.isEmpty ? null : all.first;
});

/// Kolejka pytań Slideshow (ustawiana na ekranie wyboru, odtwarzana na ekranie pokazu).
final slideshowQueueProvider = StateProvider<List<QuestionRow>>((ref) => const []);
