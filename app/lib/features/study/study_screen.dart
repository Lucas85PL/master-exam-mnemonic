import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../data/ai_disputed.dart';
import '../../data/cmke_diff.dart';
import '../../data/question_repository.dart';
import '../../domain/answer_shuffle.dart';
import '../../domain/fsrs.dart';
import '../../domain/study_plan.dart';
import '../../providers/app_providers.dart';
import '../../providers/settings_providers.dart';
import '../../theme/answer_highlight_colors.dart';
import '../../widgets/answer_keyboard.dart';
import '../../widgets/app_drawer.dart';
import '../../widgets/question_image.dart';
import '../../widgets/uncertain_banner.dart';
import 'explain_sheet.dart';

/// Pastelowa zieleń przycisku „odłóż pytanie” (klepsydra) i dostępne okresy odłożenia (dni).
const snoozeGreen = Color(0xFFB5E3C4);
const snoozeChoices = [3, 6, 12];

class StudyScreen extends ConsumerStatefulWidget {
  const StudyScreen({super.key});

  @override
  ConsumerState<StudyScreen> createState() => _StudyScreenState();
}

class _StudyScreenState extends ConsumerState<StudyScreen> {
  QuestionRow? _question;
  bool _answered = false;
  String? _picked;
  int _sessionCount = 0;
  int _sessionCorrect = 0;
  int _sessionWrong = 0;

  /// Wyniki ostatnich odpowiedzi sesji (do dynamicznego odstępu między nowymi pytaniami)
  /// oraz liczba odpowiedzi od ostatniego nowego pytania.
  final List<bool> _recent = [];
  int _sinceNew = 0;
  bool _loading = true;
  bool _explaining = false;
  final _rnd = Random();
  int? _lastId;
  DateTime? _shownAt;
  String? _nextLabel;

  /// Zapis oceny karty zakończony — dopiero wtedy można ręcznie odłożyć pytanie (inaczej wyścig z zapisem).
  bool _srsReady = false;

  /// Tryb „Powtórz zaplanowane”: karty już zaliczone w tej sesji (nie wracają, żeby kolejka się kończyła).
  final Set<int> _aheadDone = {};

  /// Pozycja w kolejce „Powtórki – najtrudniejsze” (drillQueueProvider).
  int _drillPos = 0;

  /// Poprawna, ale wolna odpowiedź (prawdopodobne zgadywanie) liczy się jako „trudna”.
  static const _slowAnswerSeconds = 25;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _loadNext());
  }

  Future<void> _loadNext() async {
    setState(() {
      _loading = true;
      _answered = false;
      _picked = null;
      _nextLabel = null;
      _srsReady = false;
    });
    final repo = await ref.read(repositoryProvider.future);
    final cat = ref.read(selectedCategoryProvider);
    final ahead = ref.read(reviewAheadProvider);
    final preferNew = !ahead && _sinceNew >= newCardGap(_recent);
    final drill = ref.read(drillQueueProvider);
    Map<String, dynamic>? row;
    if (drill != null) {
      // „Powtórka trudnych”: kolejne pytania z wylosowanej kolejki
      while (row == null && _drillPos < drill.length) {
        row = await repo.fetchCardById(drill[_drillPos++]);
      }
    } else {
      row = await repo.fetchNextCard(
        cat,
        excludeId: _lastId,
        ahead: ahead,
        preferNew: preferNew,
        onlyNew: !ahead && ref.read(newOnlyProvider),
        doneIds: _aheadDone,
      );
    }
    if (row == null && drill == null && ahead && _lastId != null) {
      // zostać może tylko karta po błędzie, którą właśnie widziałeś - pokaż ją jeszcze raz
      row = await repo.fetchNextCard(cat, ahead: true, doneIds: _aheadDone);
    }
    if (!mounted) return;
    if (row == null) {
      setState(() {
        _loading = false;
        _question = null;
      });
      return;
    }
    var q = repo.rowFromMap(row);
    await ref.read(shuffleAnswersProvider.notifier).ready;
    if (ref.read(shuffleAnswersProvider)) q = shuffleAnswers(q, _rnd);
    _lastId = q.id;
    if (q.isNewCard) _sinceNew = 0;
    _shownAt = DateTime.now();
    setState(() {
      _question = q;
      _loading = false;
    });
  }

  Future<void> _showExplain() async {
    if (_question == null || !_answered || _explaining) return;
    // Wyjaśnienie zapisane w bazie (cache) wyświetlamy zawsze — także bez klucza API i przy wyłączonym AI.
    final cachedService = await ref.read(explainServiceProvider.future);
    final shownQ = _question!;
    final cachedText = await cachedService.cachedExplanation(shownQ.original ?? shownQ);
    if (cachedText != null) {
      if (!mounted) return;
      await showExplainSheet(context, remapExplanationLetters(cachedText, shownQ.letterMap));
      return;
    }
    if (!await loadAiReady(ref)) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Brak gotowego wyjaśnienia. Włącz wyjaśnienia AI i zapisz klucz OpenRouter w Ustawieniach.',
          ),
        ),
      );
      return;
    }

    setState(() => _explaining = true);
    try {
      final service = await ref.read(explainServiceProvider.future);
      final apiKey = await ref.read(apiKeyProvider.future);
      if (apiKey == null || apiKey.isEmpty) {
        throw Exception('Brak klucza API');
      }
      final model = ref.read(aiModelProvider);
      final q = _question!;
      final text = await service.explain(
        apiKey: apiKey,
        modelId: model,
        question: q.original ?? q,
        userPicked: q.originalLetterOf(_picked),
        userWasCorrect: _picked == q.poprawnaOdpowiedz,
      );
      if (!mounted) return;
      await showExplainSheet(context, remapExplanationLetters(text, q.letterMap));
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Wyjaśnienie: $e')),
      );
    } finally {
      if (mounted) setState(() => _explaining = false);
    }
  }

  /// "Nie wiem": pokazuje poprawną odpowiedź i planuje powtórkę jak po błędzie.
  Future<void> _dontKnow() => _pickAnswer(null);

  Future<void> _pickAnswer(String? letter) async {
    if (_answered || _question == null) return;
    final q = _question!;
    final correct = letter != null && letter == q.poprawnaOdpowiedz;
    setState(() {
      _picked = letter;
      _answered = true;
      _sessionCount++;
      if (correct) {
        _sessionCorrect++;
      } else {
        _sessionWrong++;
      }
      _recent.add(correct);
      _sinceNew++;
    });

    final now = DateTime.now();
    final elapsed = _shownAt == null ? 0 : now.difference(_shownAt!).inSeconds;
    final rating = !correct
        ? Rating.again
        : (elapsed > _slowAnswerSeconds ? Rating.hard : Rating.good);

    await ref.read(desiredRetentionProvider.notifier).ready;
    final scheduler = ref.read(fsrsSchedulerProvider);
    final repo = await ref.read(repositoryProvider.future);
    final card = await repo.loadSrs(q.id) ?? FsrsCard(questionId: q.id);
    final updated = scheduler.review(card, rating, now);
    await repo.saveSrs(updated); // zapis od razu - postęp nie zależy od zamknięcia programu
    final outcome = await repo.recordAnswer(
      questionId: q.id,
      correct: correct,
      rating: rating.value,
      lapses: updated.lapses,
      now: now,
      seconds: elapsed,
    );
    if (updated.state == CardState.review) {
      // pytania „trudne” wracają najpóźniej po 3 dniach; przy ustawionym egzaminie odstęp mieści się w terminie
      await ref.read(examDateProvider.notifier).ready;
      final exam = ref.read(examDateProvider);
      final target = exam == null ? null : studyDayOfDate(exam) - examBufferDays;
      var days = capIntervalForExam(
        intervalDays: updated.intervalDays,
        streakAfter: outcome.streakDays,
        today: outcome.today,
        targetDay: target,
      );
      if (outcome.hard && days > hardMaxIntervalDays) days = hardMaxIntervalDays;
      if (days != updated.intervalDays) {
        updated.intervalDays = days;
        updated.due = scheduler.dueInDays(now, days);
        await repo.saveSrs(updated);
      }
    }
    if (ref.read(reviewAheadProvider) && updated.state == CardState.review) {
      _aheadDone.add(q.id); // zaliczona w tej sesji - nie wraca w trybie „Powtórz zaplanowane”
    }
    if (mounted) {
      setState(() {
        _nextLabel = 'Powtórka: ${FsrsScheduler.dueLabel(updated.due, now)}';
        _srsReady = true;
      });
    }
    ref.invalidate(studyStatsProvider);
  }

  /// Ręczne odłożenie: „znam tę odpowiedź z doświadczenia” — nadpisuje harmonogram FSRS dla tego pytania.
  Future<void> _showSnoozeMenu() async {
    if (!_srsReady || _question == null) return;
    final days = await showModalBottomSheet<int>(
      context: context,
      showDragHandle: true,
      builder: (ctx) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Padding(
              padding: EdgeInsets.fromLTRB(20, 0, 20, 8),
              child: Text(
                'Odłóż pytanie (nadpisuje harmonogram nauki)',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
              ),
            ),
            for (final d in snoozeChoices)
              ListTile(
                leading: const Icon(Icons.hourglass_bottom),
                title: Text('Odłóż na $d dni'),
                onTap: () => Navigator.pop(ctx, d),
              ),
          ],
        ),
      ),
    );
    if (days != null) await _snooze(days);
  }

  Future<void> _snooze(int days) async {
    final q = _question;
    if (q == null) return;
    final repo = await ref.read(repositoryProvider.future);
    final card = await repo.loadSrs(q.id);
    if (card == null) return;
    await ref.read(desiredRetentionProvider.notifier).ready;
    final now = DateTime.now();
    final snoozed = ref.read(fsrsSchedulerProvider).snooze(card, days, now);
    await repo.saveSrs(snoozed);
    if (ref.read(reviewAheadProvider)) _aheadDone.add(q.id);
    ref.invalidate(studyStatsProvider);
    if (!mounted) return;
    setState(() => _nextLabel = 'Odłożone na $days dni — powtórka: ${FsrsScheduler.dueLabel(snoozed.due, now)}');
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('Pytanie odłożone na $days dni'), duration: const Duration(seconds: 2)),
    );
  }

  Future<void> _markError() async {
    if (_question == null) return;
    final repo = await ref.read(repositoryProvider.future);
    await repo.hideQuestion(_question!.id);
    ref.invalidate(studyStatsProvider);
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Pytanie ukryte (Błąd)')),
      );
    }
    await _loadNext();
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return const Scaffold(
        body: Center(child: CircularProgressIndicator()),
      );
    }

    if (_question == null) {
      return Scaffold(
        appBar: AppBar(title: const Text('Nauka')),
        drawer: const AppDrawer(),
        body: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(ref.read(drillQueueProvider) != null
                  ? 'Koniec powtórki: przerobiłeś wszystkie wybrane pytania ($_sessionCorrect/$_sessionCount poprawnie).'
                  : ref.read(reviewAheadProvider)
                      ? 'Koniec: przejrzałeś wszystkie zaplanowane pytania.'
                      : ref.read(newOnlyProvider)
                          ? 'Koniec: nie ma już nowych kart w tej kategorii.'
                          : 'Brak kart do nauki w tej kategorii.'),
              const SizedBox(height: 16),
              FilledButton(
                onPressed: () => context.pop(),
                child: const Text('Powrót'),
              ),
            ],
          ),
        ),
      );
    }

    final q = _question!;
    final correctLetter = q.poprawnaOdpowiedz;
    final highlights = AnswerHighlightColors.of(context);

    return AnswerKeyboard(
      // 1, 2, 3… = kolejny wiersz odpowiedzi, spacja = „Dalej”
      onDigit: (i) {
        final opts = _question?.visibleOptions ?? const [];
        if (!_answered && i < opts.length) _pickAnswer(opts[i].key);
      },
      onSpace: () {
        if (_answered) _loadNext();
      },
      child: Scaffold(
      drawer: const AppDrawer(),
      appBar: AppBar(
        title: _SessionCounter(
          total: _sessionCount,
          correct: _sessionCorrect,
          wrong: _sessionWrong,
        ),
        actions: [
          TextButton(
            onPressed: _markError,
            child: const Text(
              'Błąd',
              style: TextStyle(color: Colors.redAccent),
            ),
          ),
        ],
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Expanded(
                child: SingleChildScrollView(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Row(
                        children: [
                          Text(
                            'ID: ${q.id}',
                            style: Theme.of(context).textTheme.labelLarge?.copyWith(
                                  color: Theme.of(context).colorScheme.outline,
                                ),
                          ),
                          const SizedBox(width: 8),
                          if (q.isNewCard) const _Tag('Nowe', Colors.blue),
                          if (q.hard) const _Tag('Trudne', Colors.orange),
                        ],
                      ),
                      const SizedBox(height: 8),
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
                              Text(
                                q.pytanie,
                                style: TextStyle(fontSize: 18, color: (q.aiDisputed || q.cmkeDiff) ? Colors.black87 : null),
                              ),
                            ],
                          ),
                        ),
                      ),
                      const SizedBox(height: 16),
                      ...q.visibleOptions.map((opt) {
                        final letter = opt.key;
                        final isPicked = _picked == letter;
                        final isCorrect = letter == correctLetter;
                        final scheme = Theme.of(context).colorScheme;
                        Color? bg;
                        Color? fg;
                        if (_answered) {
                          if (isCorrect) {
                            bg = highlights.correctBackground;
                            fg = highlights.correctForeground;
                          } else if (isPicked) {
                            bg = highlights.wrongBackground;
                            fg = highlights.wrongForeground;
                          }
                        }
                        final textStyle = TextStyle(
                          fontSize: 16,
                          color: fg,
                        );
                        return Padding(
                          padding: const EdgeInsets.only(bottom: 8),
                          child: Material(
                            color: bg ?? scheme.surfaceContainerHighest,
                            borderRadius: BorderRadius.circular(8),
                            child: InkWell(
                              onTap: _answered ? null : () => _pickAnswer(letter),
                              borderRadius: BorderRadius.circular(8),
                              child: Padding(
                                padding: const EdgeInsets.all(14),
                                child: Row(
                                  children: [
                                    Text(
                                      '$letter.',
                                      style: textStyle.copyWith(
                                        fontWeight: FontWeight.bold,
                                      ),
                                    ),
                                    const SizedBox(width: 8),
                                    Expanded(
                                      child: Text(opt.value, style: textStyle),
                                    ),
                                    if (_answered && letter == q.cmkeShownLetter)
                                      Container(
                                        margin: const EdgeInsets.only(left: 8),
                                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                                        decoration: BoxDecoration(
                                          color: CmkeDiff.tagColor,
                                          borderRadius: BorderRadius.circular(10),
                                        ),
                                        child: const Text(CmkeDiff.tag,
                                            style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: Colors.white)),
                                      ),
                                  ],
                                ),
                              ),
                            ),
                          ),
                        );
                      }),
                      if (!_answered) ...[
                        const SizedBox(height: 4),
                        OutlinedButton.icon(
                          onPressed: _dontKnow,
                          icon: const Icon(Icons.help_outline),
                          label: const Text('Nie wiem'),
                        ),
                      ],
                      if (_answered) ...[
                        const SizedBox(height: 8),
                        Text(
                          _picked == correctLetter
                              ? 'Poprawnie!'
                              : _picked == null
                                  ? 'Nie wiem. Poprawna: $correctLetter (pytanie wróci do powtórki)'
                                  : 'Błędnie. Poprawna: $correctLetter',
                          style: TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.bold,
                            color: _picked == correctLetter
                                ? highlights.feedbackCorrect
                                : highlights.feedbackWrong,
                          ),
                        ),
                        if (_nextLabel != null)
                          Padding(
                            padding: const EdgeInsets.only(top: 4),
                            child: Text(
                              _nextLabel!,
                              style: TextStyle(
                                fontSize: 13,
                                color: Theme.of(context).colorScheme.outline,
                              ),
                            ),
                          ),
                        const SizedBox(height: 8),
                        // AI nie widzi obrazka — dla pytań z rysunkiem „Wyjaśnij” jest wyłączone
                        if (q.imagePath == null)
                          OutlinedButton.icon(
                          onPressed: _explaining ? null : _showExplain,
                          icon: _explaining
                              ? const SizedBox(
                                  width: 18,
                                  height: 18,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2,
                                  ),
                                )
                              : const Icon(Icons.auto_awesome),
                          label: const Text('Wyjaśnij'),
                        ),
                        const SizedBox(height: 10),
                        Center(
                          child: Tooltip(
                            message: 'Odłóż pytanie (3 / 6 / 12 dni)',
                            child: FilledButton(
                              style: FilledButton.styleFrom(
                                backgroundColor: snoozeGreen,
                                foregroundColor: Colors.black87,
                                disabledBackgroundColor: snoozeGreen.withValues(alpha: 0.4),
                                minimumSize: const Size(48, 48),
                                maximumSize: const Size(48, 48),
                                padding: EdgeInsets.zero,
                                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                              ),
                              onPressed: _srsReady ? _showSnoozeMenu : null,
                              child: const Icon(Icons.hourglass_bottom, size: 26),
                            ),
                          ),
                        ),
                      ],
                      const SizedBox(height: 8),
                    ],
                  ),
                ),
              ),
              FilledButton(
                onPressed: _answered ? _loadNext : null,
                child: const Text('Dalej'),
              ),
            ],
          ),
        ),
      ),
      ),
    );
  }
}

/// „X/Y/Z”: X (białe) odpowiedzi w sesji, Y (zielone) poprawne, Z (czerwone) błędne.
class _SessionCounter extends StatelessWidget {
  const _SessionCounter({
    required this.total,
    required this.correct,
    required this.wrong,
  });

  final int total;
  final int correct;
  final int wrong;

  @override
  Widget build(BuildContext context) {
    final base = Theme.of(context).textTheme.titleMedium!;
    final highlights = AnswerHighlightColors.of(context);
    return Tooltip(
      message: 'Odpowiedzi w sesji / poprawne / błędne',
      child: Text.rich(
        TextSpan(
          style: base,
          children: [
            TextSpan(text: '$total'),
            const TextSpan(text: '/'),
            TextSpan(text: '$correct', style: TextStyle(color: highlights.feedbackCorrect)),
            const TextSpan(text: '/'),
            TextSpan(text: '$wrong', style: TextStyle(color: highlights.feedbackWrong)),
          ],
        ),
      ),
    );
  }
}

class _Tag extends StatelessWidget {
  const _Tag(this.text, this.color);

  final String text;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(right: 6),
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: color),
      ),
      child: Text(text, style: TextStyle(fontSize: 12, color: color, fontWeight: FontWeight.w600)),
    );
  }
}
