import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../data/ai_disputed.dart';
import '../../data/question_repository.dart';
import '../../data/test_history.dart';
import '../../domain/answer_shuffle.dart';
import '../../domain/slideshow.dart';
import '../../providers/app_providers.dart';
import '../../providers/settings_providers.dart';
import '../../theme/answer_highlight_colors.dart';
import '../../widgets/answer_keyboard.dart';
import '../../widgets/app_drawer.dart';
import '../../widgets/question_image.dart';
import '../../widgets/uncertain_banner.dart';
import '../study/explain_sheet.dart';

/// „Slideshow”: szybkie przypomnienie trudnych i starych pytań — treść pytania i tylko poprawna odpowiedź (zielona),
/// bez zapisu odpowiedzi i bez zmian harmonogramu nauki.
class SlideshowSetupScreen extends ConsumerStatefulWidget {
  const SlideshowSetupScreen({super.key});

  @override
  ConsumerState<SlideshowSetupScreen> createState() => _SlideshowSetupScreenState();
}

class _SlideshowSetupScreenState extends ConsumerState<SlideshowSetupScreen> {
  int _tests = 5;
  int _hard = 50;
  int _oldest = 50;
  bool _busy = false;
  bool _withUncertain = true; // true = „Wszystkie”, false = „Bez niepewnych”
  int _testsWithData = 0;

  @override
  void initState() {
    super.initState();
    TestHistory.load().then((all) {
      if (mounted) setState(() => _testsWithData = all.where((t) => t.recordsWrong).length);
    });
  }

  static String _testLabel(int v) => v == 0 ? 'Brak' : (v == slideshowAllTests ? 'Wszystkie' : '$v');
  static String _countLabel(int v) => v == 0 ? 'Brak' : '$v';

  Future<void> _start() async {
    setState(() => _busy = true);
    try {
      final repo = await ref.read(repositoryProvider.future);
      final wrong = _tests > 0 ? (await TestHistory.recentWrong(_tests)).ids : <int>{};
      final list = await repo.buildSlideshow(
          testWrongIds: wrong, hardN: _hard, oldestN: _oldest, excludeUncertain: !_withUncertain);
      if (!mounted) return;
      if (list.isEmpty) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Brak pytań do pokazania dla wybranych opcji.')),
        );
        return;
      }
      ref.read(slideshowQueueProvider.notifier).state = list;
      context.push('/slideshow/play');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Widget _row(String label, String hint, int value, List<int> choices, String Function(int) fmt, ValueChanged<int> onChanged,
      {Key? key}) {
    final scheme = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.only(bottom: 18),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(label, style: const TextStyle(fontWeight: FontWeight.w600)),
                Text(hint, style: TextStyle(fontSize: 12, color: scheme.outline)),
              ],
            ),
          ),
          const SizedBox(width: 12),
          DropdownButton<int>(
            key: key,
            value: value,
            items: [for (final c in choices) DropdownMenuItem(value: c, child: Text(fmt(c)))],
            onChanged: (v) => v == null ? null : onChanged(v),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final none = _tests == 0 && _hard == 0 && _oldest == 0;
    return Scaffold(
      drawer: const AppDrawer(),
      appBar: AppBar(title: const Text('Slideshow')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text('Szybkie przypomnienie trudnych i starych pytań. Pokazuję treść pytania i prawidłową odpowiedź.',
              style: TextStyle(color: scheme.outline)),
          const SizedBox(height: 20),
          _row('Błędne odpowiedzi z ostatnich testów', 'liczba testów (zapisane błędy z $_testsWithData testów)', _tests,
              slideshowTestChoices, _testLabel, (v) => setState(() => _tests = v),
              key: const ValueKey('slide-tests')),
          _row('Ostatnie trudne', 'pytania z błędami, od ostatnio błędnych', _hard, slideshowCountChoices, _countLabel,
              (v) => setState(() => _hard = v),
              key: const ValueKey('slide-hard')),
          _row('Najstarsze pytania', 'od tych, które były wyświetlone najdawniej', _oldest, slideshowCountChoices, _countLabel,
              (v) => setState(() => _oldest = v),
              key: const ValueKey('slide-oldest')),
          Text(
            'Pytania się nie powtarzają: jeśli pytanie jest już w jednej puli, nie jest brane z kolejnej (w jej miejsce '
            'wchodzi następne).',
            style: TextStyle(fontSize: 12, color: scheme.outline),
          ),
          const SizedBox(height: 16),
          const Text('Pytania niepewne', style: TextStyle(fontWeight: FontWeight.w600)),
          const SizedBox(height: 6),
          SegmentedButton<bool>(
            key: const ValueKey('slide-uncertain'),
            segments: const [
              ButtonSegment(value: true, label: Text('Wszystkie')),
              ButtonSegment(value: false, label: Text('Bez niepewnych')),
            ],
            selected: {_withUncertain},
            onSelectionChanged: (v) => setState(() => _withUncertain = v.first),
          ),
          const SizedBox(height: 20),
          FilledButton.icon(
            key: const ValueKey('slide-start'),
            onPressed: _busy || none ? null : _start,
            icon: _busy
                ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                : const Icon(Icons.slideshow),
            label: const Text('Start'),
          ),
        ],
      ),
    );
  }
}

/// Pokaz: pytanie, pod nim na zielono tylko poprawna odpowiedź; „Wyjaśnij” i „Dalej” (spacja = Dalej).
class SlideshowPlayScreen extends ConsumerStatefulWidget {
  const SlideshowPlayScreen({super.key});

  @override
  ConsumerState<SlideshowPlayScreen> createState() => _SlideshowPlayScreenState();
}

class _SlideshowPlayScreenState extends ConsumerState<SlideshowPlayScreen> {
  int _index = 0;
  bool _explaining = false;

  List<QuestionRow> get _list => ref.read(slideshowQueueProvider);

  void _next() {
    if (_index < _list.length) setState(() => _index++);
  }

  Future<void> _explain(QuestionRow q) async {
    if (_explaining) return;
    final service = await ref.read(explainServiceProvider.future);
    final cached = await service.cachedExplanation(q.original ?? q);
    if (cached != null) {
      if (!mounted) return;
      await showExplainSheet(context, remapExplanationLetters(cached, q.letterMap));
      return;
    }
    if (!await loadAiReady(ref)) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Brak gotowego wyjaśnienia. Włącz wyjaśnienia AI i zapisz klucz OpenRouter w Ustawieniach.'),
        ),
      );
      return;
    }
    setState(() => _explaining = true);
    try {
      final apiKey = await ref.read(apiKeyProvider.future);
      if (apiKey == null || apiKey.isEmpty) throw Exception('Brak klucza API');
      final text = await service.explain(
        apiKey: apiKey,
        modelId: ref.read(aiModelProvider),
        question: q.original ?? q,
        userPicked: q.originalLetterOf(q.poprawnaOdpowiedz),
        userWasCorrect: true,
      );
      if (!mounted) return;
      await showExplainSheet(context, remapExplanationLetters(text, q.letterMap));
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Wyjaśnienie: $e')));
    } finally {
      if (mounted) setState(() => _explaining = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final list = ref.watch(slideshowQueueProvider);
    final finished = _index >= list.length;
    final scheme = Theme.of(context).colorScheme;
    final colors = AnswerHighlightColors.of(context);
    return Scaffold(
      appBar: AppBar(title: Text(finished ? 'Slideshow' : 'Slideshow  ${_index + 1} / ${list.length}')),
      body: SafeArea(
        child: AnswerKeyboard(
          onDigit: (_) {},
          onSpace: () {
            if (!finished) _next();
          },
          child: finished
              ? Center(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text('Koniec — przejrzano ${list.length} pytań', style: Theme.of(context).textTheme.titleMedium),
                      const SizedBox(height: 16),
                      FilledButton(onPressed: () => context.pop(), child: const Text('Wróć')),
                    ],
                  ),
                )
              : _slide(list[_index], scheme, colors),
        ),
      ),
    );
  }

  Widget _slide(QuestionRow q, ColorScheme scheme, AnswerHighlightColors colors) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        if (q.imagePath != null) ...[QuestionImage(imagePath: q.imagePath!), const SizedBox(height: 12)],
        if (q.aiDisputed)
          Card(
            color: AiDisputed.background,
            margin: EdgeInsets.zero,
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const UncertainBanner(),
                  const SizedBox(height: 10),
                  Text(q.pytanie,
                      key: const ValueKey('slide-question'), style: const TextStyle(fontSize: 18, height: 1.35, color: Colors.black87)),
                ],
              ),
            ),
          )
        else
          Text(q.pytanie, key: const ValueKey('slide-question'), style: const TextStyle(fontSize: 18, height: 1.35)),
        const SizedBox(height: 18),
        Container(
          key: const ValueKey('slide-answer'),
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(color: colors.correctBackground, borderRadius: BorderRadius.circular(12)),
          child: Text(q.correctText,
              style: TextStyle(fontSize: 17, fontWeight: FontWeight.w600, color: colors.correctForeground, height: 1.3)),
        ),
        const SizedBox(height: 20),
        // AI nie widzi obrazka — dla pytań z rysunkiem „Wyjaśnij” jest wyłączone (jak w nauce)
        if (q.imagePath == null)
          OutlinedButton.icon(
            key: const ValueKey('slide-explain'),
            onPressed: _explaining ? null : () => _explain(q),
            icon: _explaining
                ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                : const Icon(Icons.auto_awesome),
            label: const Text('Wyjaśnij'),
          ),
        const SizedBox(height: 10),
        FilledButton(
          key: const ValueKey('slide-next'),
          onPressed: _next,
          child: Text(_index + 1 >= _list.length ? 'Zakończ' : 'Dalej'),
        ),
      ],
    );
  }
}
