import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../data/api_key_storage.dart';
import '../domain/fsrs.dart';
import '../domain/openrouter_models.dart';
import '../domain/test_plan.dart';

const _keyAiEnabled = 'ai_explain_enabled';
const _keyAiModel = 'ai_explain_model';
const _keyRetention = 'fsrs_desired_retention';
const _keyExamDate = 'exam_date';
const _keyShuffleAnswers = 'shuffle_answers';

final apiKeyStorageProvider = Provider<ApiKeyStorage>((ref) {
  return ApiKeyStorage();
});

final aiExplainEnabledProvider =
    StateNotifierProvider<AiExplainEnabledNotifier, bool>((ref) {
  return AiExplainEnabledNotifier();
});

class AiExplainEnabledNotifier extends StateNotifier<bool> {
  AiExplainEnabledNotifier() : super(false) {
    ready = _load();
  }

  /// Zakończone, gdy wartość z SharedPreferences jest już wczytana.
  late final Future<void> ready;

  Future<void> _load() async {
    final prefs = await SharedPreferences.getInstance();
    state = prefs.getBool(_keyAiEnabled) ?? false;
  }

  Future<void> setEnabled(bool value) async {
    state = value;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_keyAiEnabled, value);
  }
}

final aiModelProvider = StateNotifierProvider<AiModelNotifier, String>((ref) {
  return AiModelNotifier();
});

class AiModelNotifier extends StateNotifier<String> {
  AiModelNotifier() : super(OpenRouterModels.defaultModelId) {
    ready = _load();
  }

  late final Future<void> ready;

  Future<void> _load() async {
    final prefs = await SharedPreferences.getInstance();
    state = prefs.getString(_keyAiModel) ?? OpenRouterModels.defaultModelId;
  }

  Future<void> setModel(String modelId) async {
    state = modelId;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_keyAiModel, modelId);
  }
}

final apiKeyProvider = FutureProvider<String?>((ref) async {
  return ref.watch(apiKeyStorageProvider).read();
});

final aiReadyProvider = Provider<bool>((ref) {
  final enabled = ref.watch(aiExplainEnabledProvider);
  final keyAsync = ref.watch(apiKeyProvider);
  return enabled &&
      keyAsync.maybeWhen(data: (k) => (k ?? '').isNotEmpty, orElse: () => false);
});

/// Czeka na wczytanie ustawień AI (przełącznik, model, klucz) i zwraca gotowość.
/// Bez tego pierwsze kliknięcie "Wyjaśnij" widzi wartości domyślne.
Future<bool> loadAiReady(WidgetRef ref) async {
  await ref.read(aiExplainEnabledProvider.notifier).ready;
  await ref.read(aiModelProvider.notifier).ready;
  await ref.read(apiKeyProvider.future);
  return ref.read(aiReadyProvider);
}

Future<void> saveApiKey(WidgetRef ref, String key) async {
  final trimmed = key.trim();
  final storage = ref.read(apiKeyStorageProvider);
  if (trimmed.isEmpty) {
    await storage.delete();
  } else {
    await storage.write(trimmed);
  }
  ref.invalidate(apiKeyProvider);
}

Future<void> deleteApiKey(WidgetRef ref) async {
  await ref.read(apiKeyStorageProvider).delete();
  ref.invalidate(apiKeyProvider);
}


/// Docelowa retencja FSRS (0.80–0.97): wyższa = częstsze powtórki, mniej zapomnianych pytań.
final desiredRetentionProvider =
    StateNotifierProvider<DesiredRetentionNotifier, double>((ref) {
  return DesiredRetentionNotifier();
});

class DesiredRetentionNotifier extends StateNotifier<double> {
  DesiredRetentionNotifier() : super(0.9) {
    ready = _load();
  }

  late final Future<void> ready;

  Future<void> _load() async {
    final prefs = await SharedPreferences.getInstance();
    state = (prefs.getDouble(_keyRetention) ?? 0.9).clamp(0.8, 0.97);
  }

  Future<void> setRetention(double v) async {
    state = v.clamp(0.8, 0.97);
    final prefs = await SharedPreferences.getInstance();
    await prefs.setDouble(_keyRetention, state);
  }
}

final fsrsSchedulerProvider = Provider<FsrsScheduler>((ref) {
  return FsrsScheduler(desiredRetention: ref.watch(desiredRetentionProvider));
});

/// Termin egzaminu (tylko data) — do paska postępu i dziennego celu; null = nie ustawiono.
final examDateProvider = StateNotifierProvider<ExamDateNotifier, DateTime?>((ref) {
  return ExamDateNotifier();
});

class ExamDateNotifier extends StateNotifier<DateTime?> {
  ExamDateNotifier() : super(null) {
    ready = _load();
  }

  late final Future<void> ready;

  Future<void> _load() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_keyExamDate);
    state = raw == null ? null : DateTime.tryParse(raw);
  }

  Future<void> setDate(DateTime? date) async {
    final d = date == null ? null : DateTime(date.year, date.month, date.day);
    state = d;
    final prefs = await SharedPreferences.getInstance();
    if (d == null) {
      await prefs.remove(_keyExamDate);
    } else {
      await prefs.setString(_keyExamDate, d.toIso8601String());
    }
  }
}

/// Ustawienia TESTU: liczba pytań, próg zaliczenia i udział pul (Master / Angielski; Pokład = reszta).
final testConfigProvider = StateNotifierProvider<TestConfigNotifier, TestConfig>((ref) {
  return TestConfigNotifier();
});

class TestConfigNotifier extends StateNotifier<TestConfig> {
  TestConfigNotifier() : super(const TestConfig()) {
    ready = _load();
  }

  late final Future<void> ready;

  Future<void> _load() async {
    final prefs = await SharedPreferences.getInstance();
    state = const TestConfig().copyWith(
      total: prefs.getInt('test_total'),
      passMark: prefs.getInt('test_pass'),
      masterPct: prefs.getInt('test_master_pct'),
      englishPct: prefs.getInt('test_english_pct'),
    );
  }

  Future<void> update(TestConfig c) async {
    state = c;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setInt('test_total', c.total);
    await prefs.setInt('test_pass', c.passMark);
    await prefs.setInt('test_master_pct', c.masterPct);
    await prefs.setInt('test_english_pct', c.englishPct);
  }
}

/// Losowa kolejność odpowiedzi w nauce i w TEŚCIE (domyślnie wyłączona) — żeby nie uczyć się „tu zawsze A”.
final shuffleAnswersProvider = StateNotifierProvider<ShuffleAnswersNotifier, bool>((ref) {
  return ShuffleAnswersNotifier();
});

class ShuffleAnswersNotifier extends StateNotifier<bool> {
  ShuffleAnswersNotifier() : super(false) {
    ready = _load();
  }

  late final Future<void> ready;

  Future<void> _load() async {
    final prefs = await SharedPreferences.getInstance();
    state = prefs.getBool(_keyShuffleAnswers) ?? false;
  }

  Future<void> setEnabled(bool value) async {
    state = value;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_keyShuffleAnswers, value);
  }
}
