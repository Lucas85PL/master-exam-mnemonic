import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../app_info.dart';
import '../../data/app_paths.dart';
import '../../data/db_info.dart';
import '../../domain/study_plan.dart';
import '../../domain/test_plan.dart';
import '../../domain/openrouter_models.dart';
import '../../providers/app_providers.dart';
import '../../providers/settings_providers.dart';
import '../../providers/theme_provider.dart';
import '../../widgets/app_drawer.dart';
import 'db_transfer_actions.dart';

class SettingsScreen extends ConsumerStatefulWidget {
  const SettingsScreen({super.key});

  @override
  ConsumerState<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends ConsumerState<SettingsScreen> {
  final _apiKeyController = TextEditingController();
  var _obscureKey = true;

  @override
  void dispose() {
    _apiKeyController.dispose();
    super.dispose();
  }

  Future<void> _pickExamDate(DateTime? current) async {
    final now = DateTime.now();
    final picked = await showDatePicker(
      context: context,
      initialDate: current ?? now.add(const Duration(days: 30)),
      firstDate: now,
      lastDate: now.add(const Duration(days: 730)),
      helpText: 'Termin egzaminu',
    );
    if (picked == null) return;
    await ref.read(examDateProvider.notifier).setDate(picked);
    ref.invalidate(studyStatsProvider);
  }

  @override
  Widget build(BuildContext context) {
    final themeMode = ref.watch(themeModeProvider);
    final isDark = themeMode == ThemeMode.dark;
    final aiEnabled = ref.watch(aiExplainEnabledProvider);
    final modelId = ref.watch(aiModelProvider);
    final keyAsync = ref.watch(apiKeyProvider);
    final retention = ref.watch(desiredRetentionProvider);
    final examDate = ref.watch(examDateProvider);
    final test = ref.watch(testConfigProvider);

    keyAsync.whenData((stored) {
      if (stored != null && _apiKeyController.text.isEmpty) {
        _apiKeyController.text = stored;
      }
    });

    return Scaffold(
      appBar: AppBar(title: const Text('Ustawienia')),
      drawer: const AppDrawer(),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          SwitchListTile(
            title: const Text('Tryb ciemny'),
            value: isDark,
            onChanged: (v) =>
                ref.read(themeModeProvider.notifier).setDarkMode(v),
          ),
          SwitchListTile(
            title: const Text('Losowa kolejność odpowiedzi'),
            subtitle: const Text('Treści odpowiedzi mieszają się pod A/B/C — bez uczenia się „tu zawsze A” (nauka i TEST)'),
            value: ref.watch(shuffleAnswersProvider),
            onChanged: (v) => ref.read(shuffleAnswersProvider.notifier).setEnabled(v),
          ),
          const Divider(),
          const Text(
            'Nauka (FSRS)',
            style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 8),
          Text('Docelowa retencja: ${(retention * 100).round()}%'),
          Slider(
            value: retention,
            min: 0.80,
            max: 0.97,
            divisions: 17,
            label: '${(retention * 100).round()}%',
            onChanged: (v) => ref.read(desiredRetentionProvider.notifier).setRetention(v),
          ),
          const Text(
            'Wyższa retencja = częstsze powtórki i mniej zapomnianych pytań. '
            'Błędne pytania wracają w tej samej sesji (po 1 i 10 min), potem następnego dnia rano.',
            style: TextStyle(fontSize: 12, color: Colors.grey),
          ),
          const Divider(height: 32),
          const Text(
            'TEST (symulacja egzaminu)',
            style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 8),
          Text('Liczba pytań w teście: ${test.total}'),
          Slider(
            value: test.total.toDouble(),
            min: 20,
            max: 200,
            divisions: 36,
            label: '${test.total}',
            onChanged: (v) => ref.read(testConfigProvider.notifier).update(test.copyWith(total: v.round())),
          ),
          Text('Próg zaliczenia: ${test.passMark} poprawnych (${(test.passMark * 100 / test.total).round()}%)'),
          Slider(
            value: test.passMark.toDouble().clamp(1, test.total.toDouble()),
            min: 1,
            max: test.total.toDouble(),
            divisions: test.total - 1,
            label: '${test.passMark}',
            onChanged: (v) => ref.read(testConfigProvider.notifier).update(test.copyWith(passMark: v.round())),
          ),
          Text('Master: ${test.masterPct}%'),
          Slider(
            value: test.masterPct.toDouble(),
            min: 0,
            max: 100,
            divisions: 20,
            label: '${test.masterPct}%',
            onChanged: (v) => ref.read(testConfigProvider.notifier).update(test.copyWith(masterPct: v.round())),
          ),
          Text('Angielski: ${test.englishPct}%'),
          Slider(
            value: test.englishPct.toDouble().clamp(0, 100 - test.masterPct).toDouble(),
            min: 0,
            max: (100 - test.masterPct).toDouble().clamp(1, 100).toDouble(),
            divisions: ((100 - test.masterPct) / 5).round().clamp(1, 20),
            label: '${test.englishPct}%',
            onChanged: (v) => ref.read(testConfigProvider.notifier).update(test.copyWith(englishPct: v.round())),
          ),
          Text('Pokład: ${test.pokladPct}% (reszta)'),
          Text(
            'Liczba pytań z każdej puli: ${allocateTest(test.total, [test.masterPct, test.englishPct, test.pokladPct]).join(' / ')} '
            '(Master / Angielski / Pokład). Błędne odpowiedzi z testu trafiają od razu do powtórek w swoim dziale.',
            style: const TextStyle(fontSize: 12, color: Colors.grey),
          ),
          const Divider(height: 32),
          const Text(
            'Egzamin',
            style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
          ),
          ListTile(
            contentPadding: EdgeInsets.zero,
            title: const Text('Termin egzaminu'),
            subtitle: Text(
              examDate == null
                  ? 'Nie ustawiono — na ekranie głównym pojawi się dzienny cel po wpisaniu daty '
                      '(materiał ma być znany $examBufferDays dni przed egzaminem).'
                  : '${examDate.day.toString().padLeft(2, '0')}.${examDate.month.toString().padLeft(2, '0')}.${examDate.year}',
            ),
            trailing: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                if (examDate != null)
                  IconButton(
                    tooltip: 'Usuń termin',
                    icon: const Icon(Icons.clear),
                    onPressed: () {
                      ref.read(examDateProvider.notifier).setDate(null);
                      ref.invalidate(studyStatsProvider);
                    },
                  ),
                IconButton(
                  tooltip: 'Wybierz datę',
                  icon: const Icon(Icons.event),
                  onPressed: () => _pickExamDate(examDate),
                ),
              ],
            ),
            onTap: () => _pickExamDate(examDate),
          ),
          const Divider(height: 32),
          const Text(
            'Wyjaśnienia AI (eksperymentalne)',
            style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 8),
          SwitchListTile(
            title: const Text('Włącz wyjaśnienia AI'),
            subtitle: const Text('Przycisk „Wyjaśnij” po odpowiedzi w nauce'),
            value: aiEnabled,
            onChanged: (v) =>
                ref.read(aiExplainEnabledProvider.notifier).setEnabled(v),
          ),
          DropdownButtonFormField<String>(
            initialValue: modelId,
            decoration: const InputDecoration(
              labelText: 'Model OpenRouter',
              border: OutlineInputBorder(),
            ),
            items: OpenRouterModels.presets
                .map(
                  (p) => DropdownMenuItem(
                    value: p.modelId,
                    child: Text(p.label),
                  ),
                )
                .toList(),
            onChanged: (v) {
              if (v != null) {
                ref.read(aiModelProvider.notifier).setModel(v);
              }
            },
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _apiKeyController,
            obscureText: _obscureKey,
            decoration: InputDecoration(
              labelText: 'Klucz API OpenRouter',
              border: const OutlineInputBorder(),
              suffixIcon: IconButton(
                icon: Icon(_obscureKey ? Icons.visibility : Icons.visibility_off),
                onPressed: () => setState(() => _obscureKey = !_obscureKey),
              ),
            ),
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              FilledButton(
                onPressed: () async {
                  await saveApiKey(ref, _apiKeyController.text);
                  if (context.mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('Klucz zapisany lokalnie')),
                    );
                  }
                },
                child: const Text('Zapisz klucz'),
              ),
              const SizedBox(width: 8),
              OutlinedButton(
                onPressed: () async {
                  _apiKeyController.clear();
                  await deleteApiKey(ref);
                  if (context.mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('Klucz usunięty')),
                    );
                  }
                },
                child: const Text('Usuń'),
              ),
            ],
          ),
          const Divider(height: 32),
          const Text(
            'Baza danych',
            style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              FilledButton.icon(
                onPressed: () => exportDatabase(context, ref),
                icon: const Icon(Icons.upload_file),
                label: const Text('Eksportuj bazę'),
              ),
              OutlinedButton.icon(
                onPressed: () => importDatabase(context, ref),
                icon: const Icon(Icons.download),
                label: const Text('Importuj bazę'),
              ),
            ],
          ),
          const Padding(
            padding: EdgeInsets.only(top: 8),
            child: Text(
              'Eksport zapisuje całą bazę: pytania wraz ze statusami (OK / Błąd), '
              'postęp nauki i zapisane wyjaśnienia. Klucz API nie jest eksportowany.',
              style: TextStyle(fontSize: 12, color: Colors.grey),
            ),
          ),
          const Padding(
            padding: EdgeInsets.only(top: 8),
            child: Text(
              'Klucz jest przechowywany tylko lokalnie na tym komputerze. '
              'Nie trafia do repozytorium git.',
              style: TextStyle(fontSize: 12, color: Colors.grey),
            ),
          ),
          const Divider(height: 32),
          Center(
            child: Text(
              '$appName $appVersionFull · baza pytań ${DbInfo.version ?? '—'}'
              '${AppPaths.isPortable ? ' — wersja przenośna (dane w folderze user_data obok programu)' : ''}',
              style: const TextStyle(fontSize: 12, color: Colors.grey),
            ),
          ),
        ],
      ),
    );
  }
}
