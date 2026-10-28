import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../data/ai_disputed.dart';
import '../../data/cmke_diff.dart';
import '../../data/question_repository.dart';
import '../../data/test_history.dart';
import '../../domain/answer_shuffle.dart';
import '../../domain/category_filter.dart';
import '../../domain/fsrs.dart';
import '../../domain/test_plan.dart';
import '../../providers/app_providers.dart';
import '../../providers/settings_providers.dart';
import '../../widgets/answer_keyboard.dart';
import '../../widgets/question_image.dart';
import '../../widgets/uncertain_banner.dart';

/// Pastelowy pomarańcz TESTU (przycisk na ekranie głównym i akcenty ekranu testu).
const testOrange = Color(0xFFFFB877);
const testOrangeDark = Color(0xFFB85C00);

class _Answered {
  _Answered(this.question, this.picked);

  final QuestionRow question;

  /// null = „Nie wiem”.
  final String? picked;

  bool get correct => picked != null && picked == question.poprawnaOdpowiedz;
}

/// TEST: symulacja egzaminu — losowe pytania z puli Master / Angielski / Pokład (proporcje w Ustawieniach),
/// bez podpowiedzi w trakcie; wynik na końcu. Błędne odpowiedzi trafiają od razu do powtórek (FSRS: Again).
class TestScreen extends ConsumerStatefulWidget {
  const TestScreen({super.key});

  @override
  ConsumerState<TestScreen> createState() => _TestScreenState();
}

class _TestScreenState extends ConsumerState<TestScreen> {
  List<QuestionRow> _questions = [];
  final List<_Answered> _answers = [];
  TestConfig _config = const TestConfig();
  int _index = 0;
  String? _selected;
  bool _loading = true;
  bool _finished = false;
  bool _saving = false;
  DateTime? _shownAt;
  String? _emptyReason;
  bool _hard = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _start());
  }

  Future<void> _start() async {
    await ref.read(testConfigProvider.notifier).ready;
    _config = ref.read(testConfigProvider);
    final repo = await ref.read(repositoryProvider.future);
    const cats = [StudyCategory.master, StudyCategory.angielski, StudyCategory.poklad];
    final pcts = [_config.masterPct, _config.englishPct, _config.pokladPct];
    final hard = _hard = ref.read(testHardProvider);
    // pytania z 2 ostatnich zakończonych testów (Normalnych i Trudnych) nie mogą się powtórzyć
    final exclude = await repo.duplicateKeysForIds(await TestHistory.recentQuestionIds(testNoRepeatDepth));
    Future<List<QuestionRow>> draw(Set<String> ex) => hard
        ? repo.pickHardTestQuestions(_config.total, exclude: ex)
        : repo.pickTestQuestions(cats, allocateTest(_config.total, pcts), pcts, exclude: ex);
    var list = await draw(exclude);
    // zbyt mała pula po wykluczeniu (np. mała baza) — wtedy bez wykluczeń, żeby test w ogóle się odbył
    if (exclude.isNotEmpty && list.length < _config.total) list = await draw(const {});
    await ref.read(shuffleAnswersProvider.notifier).ready;
    if (ref.read(shuffleAnswersProvider)) {
      final rnd = Random();
      list = [for (final q in list) shuffleAnswers(q, rnd)];
    }
    if (!mounted) return;
    setState(() {
      _questions = list;
      _loading = false;
      _emptyReason = list.isEmpty ? 'Brak pytań w puli nauki — nie można rozpocząć testu.' : null;
      _shownAt = DateTime.now();
    });
  }

  QuestionRow get _q => _questions[_index];

  Future<void> _submit(String? picked) async {
    if (_saving) return;
    setState(() => _saving = true);
    final q = _q;
    final a = _Answered(q, picked);
    _answers.add(a);
    if (!a.correct) {
      // błędna odpowiedź => pytanie od razu wpada do powtórek w swoim dziale (FSRS: Again, powrót po 1 i 10 min)
      final now = DateTime.now();
      await ref.read(desiredRetentionProvider.notifier).ready;
      final scheduler = ref.read(fsrsSchedulerProvider);
      final repo = await ref.read(repositoryProvider.future);
      final card = await repo.loadSrs(q.id) ?? FsrsCard(questionId: q.id);
      final updated = scheduler.review(card, Rating.again, now);
      await repo.saveSrs(updated);
      await repo.recordAnswer(
        questionId: q.id,
        correct: false,
        rating: Rating.again.value,
        lapses: updated.lapses,
        now: now,
        seconds: _shownAt == null ? null : now.difference(_shownAt!).inSeconds,
      );
    }
    if (_index + 1 >= _questions.length) {
      await _finish();
    } else if (mounted) {
      setState(() {
        _index++;
        _selected = null;
        _shownAt = DateTime.now();
      });
    }
    if (mounted) setState(() => _saving = false);
  }

  Future<void> _finish() async {
    final per = <String, List<int>>{};
    for (final a in _answers) {
      final name = StudyCategory.choices
          .firstWhere((c) => c.dbValue == a.question.kategoria, orElse: () => StudyCategory.all)
          .label;
      final e = per.putIfAbsent(name, () => [0, 0]);
      e[1]++;
      if (a.correct) e[0]++;
    }
    final correct = _answers.where((a) => a.correct).length;
    await TestHistory.add(TestResult(
      timestamp: DateTime.now(),
      total: _questions.length,
      answered: _answers.length,
      correct: correct,
      passMark: _config.passMark,
      perCategory: per,
      hard: _hard,
      questionIds: [for (final q in _questions) q.id],
      wrongIds: [for (final a in _answers) if (!a.correct) a.question.id],
      recordsWrong: true,
    ));
    ref.invalidate(lastTestProvider);
    ref.invalidate(studyStatsProvider);
    if (mounted) setState(() => _finished = true);
  }

  Future<bool> _confirmExit() async {
    if (_finished) return true;
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Przerwać test?'),
        content: const Text(
          'Wynik testu nie zostanie zapisany. Błędne odpowiedzi udzielone do tej pory '
          'są już dodane do powtórek.',
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Kontynuuj test')),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Przerwij')),
        ],
      ),
    );
    return ok ?? false;
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: _finished || _loading || _questions.isEmpty,
      onPopInvokedWithResult: (didPop, _) async {
        if (didPop) return;
        if (await _confirmExit() && context.mounted) context.go('/');
      },
      child: Scaffold(
        appBar: AppBar(
          title: Text(_finished
              ? 'Wynik testu'
              : _loading || _questions.isEmpty
                  ? 'TEST'
                  : 'TEST${_hard ? ' (trudny)' : ''}  ${_index + 1} / ${_questions.length}'),
          backgroundColor: testOrange,
          foregroundColor: Colors.black87,
        ),
        body: _loading
            ? const Center(child: CircularProgressIndicator())
            : _emptyReason != null
                ? Center(child: Text(_emptyReason!))
                : _finished
                    ? _buildResult(context)
                    : AnswerKeyboard(
                        // 1, 2, 3… = wybór kolejnej odpowiedzi, spacja = „Dalej” (zatwierdza zaznaczoną)
                        onDigit: (i) {
                          final opts = _q.visibleOptions;
                          if (!_saving && i < opts.length) setState(() => _selected = opts[i].key);
                        },
                        onSpace: () {
                          if (_selected != null && !_saving) _submit(_selected);
                        },
                        child: _buildQuestion(context),
                      ),
      ),
    );
  }

  Widget _buildQuestion(BuildContext context) {
    final q = _q;
    final scheme = Theme.of(context).colorScheme;
    final last = _index + 1 >= _questions.length;
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            LinearProgressIndicator(
              value: _index / _questions.length,
              color: testOrangeDark,
              backgroundColor: testOrange.withValues(alpha: 0.3),
              minHeight: 8,
            ),
            const SizedBox(height: 12),
            Expanded(
              child: SingleChildScrollView(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Card(
                      color: q.cmkeDiff ? CmkeDiff.background : (q.aiDisputed ? AiDisputed.background : null),
                      child: Padding(
                        padding: const EdgeInsets.all(16),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            if (q.cmkeDiff) ...[
                              const Text(CmkeDiff.banner,
                                  style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold, color: Colors.black87)),
                              const SizedBox(height: 10),
                            ],
                            if (q.aiDisputed) ...[
                              const UncertainBanner(),
                              const SizedBox(height: 10),
                            ],
                            if (q.imagePath != null) ...[
                              QuestionImage(imagePath: q.imagePath!),
                              const SizedBox(height: 12),
                            ],
                            Text(q.pytanie, style: TextStyle(fontSize: 18, color: (q.aiDisputed || q.cmkeDiff) ? Colors.black87 : null)),
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(height: 12),
                    for (final opt in q.visibleOptions)
                      Padding(
                        padding: const EdgeInsets.only(bottom: 8),
                        child: OutlinedButton(
                          style: OutlinedButton.styleFrom(
                            alignment: Alignment.centerLeft,
                            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
                            backgroundColor:
                                _selected == opt.key ? testOrange.withValues(alpha: 0.35) : null,
                            side: BorderSide(
                              color: _selected == opt.key ? testOrangeDark : scheme.outlineVariant,
                              width: _selected == opt.key ? 2 : 1,
                            ),
                          ),
                          onPressed: _saving ? null : () => setState(() => _selected = opt.key),
                          child: Text('${opt.key}) ${opt.value}',
                              textAlign: TextAlign.left, style: const TextStyle(fontSize: 16)),
                        ),
                      ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                OutlinedButton(
                  onPressed: _saving ? null : () => _submit(null),
                  child: const Text('Nie wiem'),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: FilledButton(
                    style: FilledButton.styleFrom(
                      backgroundColor: testOrange,
                      foregroundColor: Colors.black87,
                    ),
                    onPressed: _selected == null || _saving ? null : () => _submit(_selected),
                    child: Text(last ? 'Zakończ test' : 'Dalej'),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildResult(BuildContext context) {
    final correct = _answers.where((a) => a.correct).length;
    final wrong = _answers.where((a) => !a.correct).toList();
    final passed = _config.isPassed(correct);
    final pct = _questions.isEmpty ? 0.0 : correct * 100 / _questions.length;
    final per = <String, List<int>>{};
    for (final a in _answers) {
      final name = StudyCategory.choices
          .firstWhere((c) => c.dbValue == a.question.kategoria, orElse: () => StudyCategory.all)
          .label;
      final e = per.putIfAbsent(name, () => [0, 0]);
      e[1]++;
      if (a.correct) e[0]++;
    }
    final color = passed ? Colors.green.shade700 : Colors.red.shade700;
    return SafeArea(
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Card(
            color: color.withValues(alpha: 0.12),
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                children: [
                  Text(passed ? 'TEST ZALICZONY' : 'TEST NIEZALICZONY',
                      style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold, color: color)),
                  const SizedBox(height: 8),
                  Text('$correct / ${_questions.length} poprawnych (${pct.toStringAsFixed(1)}%)',
                      style: const TextStyle(fontSize: 18)),
                  Text('Próg zaliczenia: ${_config.passMark}'
                      '${passed ? '' : ' — brakuje ${_config.passMark - correct}'}'),
                ],
              ),
            ),
          ),
          const SizedBox(height: 12),
          for (final e in per.entries)
            Text('${e.key}: ${e.value[0]} / ${e.value[1]}'),
          const SizedBox(height: 12),
          Text(
            wrong.isEmpty
                ? 'Brak błędów.'
                : '${wrong.length} błędnych pytań trafiło do powtórek w swoich działach '
                    '(wrócą w nauce po 1 i 10 min, potem wg FSRS).',
            style: const TextStyle(fontWeight: FontWeight.w600),
          ),
          const SizedBox(height: 8),
          for (final a in wrong)
            Card(
              child: ExpansionTile(
                title: Text(a.question.pytanie, maxLines: 2, overflow: TextOverflow.ellipsis),
                subtitle: Text(
                  a.picked == null ? 'Nie wiem' : 'Twoja odpowiedź: ${a.picked}',
                  style: TextStyle(color: Colors.red.shade700),
                ),
                childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
                expandedCrossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (a.question.imagePath != null) QuestionImage(imagePath: a.question.imagePath!),
                  Text(a.question.pytanie),
                  const SizedBox(height: 8),
                  for (final o in a.question.visibleOptions)
                    Text(
                      '${o.key}) ${o.value}',
                      style: TextStyle(
                        fontWeight: o.key == a.question.poprawnaOdpowiedz ? FontWeight.bold : null,
                        color: o.key == a.question.poprawnaOdpowiedz
                            ? Colors.green.shade700
                            : (o.key == a.picked ? Colors.red.shade700 : null),
                      ),
                    ),
                ],
              ),
            ),
          const SizedBox(height: 16),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: testOrange, foregroundColor: Colors.black87),
            onPressed: () => context.go('/'),
            child: const Text('Wróć na ekran główny'),
          ),
        ],
      ),
    );
  }
}
