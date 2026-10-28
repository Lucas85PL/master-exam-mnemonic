import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/test_history.dart';
import '../../domain/hardest.dart';
import '../../providers/app_providers.dart';
import '../../theme/answer_highlight_colors.dart';
import '../../widgets/app_drawer.dart';
import '../test/test_screen.dart' show testOrange, testOrangeDark;

class StatsData {
  StatsData({
    required this.answers,
    required this.correct,
    required this.knownAnswers,
    required this.knownCorrect,
    required this.sessions,
    required this.ranked,
    this.tests = const [],
  });

  final int answers;
  final int correct;

  /// Odpowiedzi na pytania pokazane już wcześniej (bez pierwszego pojawienia się pytania).
  final int knownAnswers;
  final int knownCorrect;
  final List<SessionStat> sessions;

  /// W pełni zakończone TESTY (przerwane nie są zapisywane), od najnowszego.
  final List<TestResult> tests;

  /// Pytania z co najmniej jednym błędem, od najtrudniejszych.
  final List<QuestionErrorStat> ranked;

  double get percent => answers == 0 ? 0 : 100 * correct / answers;
  double get knownPercent => knownAnswers == 0 ? 0 : 100 * knownCorrect / knownAnswers;
}

final statsDataProvider = FutureProvider.autoDispose<StatsData>((ref) async {
  final repo = await ref.watch(repositoryProvider.future);
  final answers = await repo.allAnswers();
  final stats = await repo.questionErrorStats();
  return StatsData(
    answers: answers.length,
    correct: answers.where((a) => a.$2).length,
    knownAnswers: answers.where((a) => a.$3).length,
    knownCorrect: answers.where((a) => a.$3 && a.$2).length,
    sessions: splitSessions(answers),
    ranked: rankByDifficulty(stats.where((s) => s.wrong > 0)),
    tests: [for (final t in await TestHistory.load()) if (t.answered >= t.total) t],
  );
});

/// Statystyki sesji: false = wszystkie pytania, true = tylko pytania znane (pokazane już wcześniej).
final sessionsKnownOnlyProvider = StateProvider<bool>((ref) => false);

/// Ile pozycji listy najtrudniejszych pytań pokazać (100 / 200 / 300).
final hardestCountProvider = StateProvider<int>((ref) => hardestListSizes.first);

String _fmtDate(DateTime d) {
  String two(int v) => v.toString().padLeft(2, '0');
  return '${d.year}-${two(d.month)}-${two(d.day)} ${two(d.hour)}:${two(d.minute)}';
}

String _pct(double v) => '${v.toStringAsFixed(1)}%';

class StatsScreen extends ConsumerWidget {
  const StatsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final data = ref.watch(statsDataProvider);
    return DefaultTabController(
      length: 3,
      child: Scaffold(
        drawer: const AppDrawer(),
        appBar: AppBar(
          title: const Text('Statystyki'),
          bottom: const TabBar(tabs: [
            Tab(text: 'Ogólne'),
            Tab(text: 'Sesje'),
            Tab(text: 'Najtrudniejsze'),
          ]),
        ),
        body: data.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, _) => Center(child: Text('Błąd: $e')),
          data: (d) => TabBarView(children: [
            _Overall(d),
            _Sessions(d),
            _Hardest(d),
          ]),
        ),
      ),
    );
  }
}

class _Overall extends StatelessWidget {
  const _Overall(this.d);

  final StatsData d;

  @override
  Widget build(BuildContext context) {
    if (d.answers == 0) return const Center(child: Text('Brak odpowiedzi — zacznij naukę.'));
    final scheme = Theme.of(context).colorScheme;
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Card(
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              children: [
                Text('Poprawne odpowiedzi (wszystkie sesje)', style: Theme.of(context).textTheme.titleMedium),
                const SizedBox(height: 12),
                Text(_pct(d.percent),
                    style: Theme.of(context).textTheme.displayMedium?.copyWith(color: scheme.primary, fontWeight: FontWeight.bold)),
                const SizedBox(height: 12),
                LinearProgressIndicator(value: d.percent / 100, minHeight: 10, borderRadius: BorderRadius.circular(5)),
                const SizedBox(height: 12),
                Text('${d.correct} poprawnych z ${d.answers} odpowiedzi · błędnych: ${d.answers - d.correct}'),
                const SizedBox(height: 4),
                Text('Liczba sesji: ${d.sessions.length}${d.tests.isEmpty ? '' : ' · testów: ${d.tests.length}'}',
                    style: TextStyle(color: scheme.outline)),
                if (d.knownAnswers > 0) ...[
                  const Divider(height: 28),
                  Text('Tylko pytania znane (powtórne pojawienie się): ${_pct(d.knownPercent)}',
                      style: const TextStyle(fontWeight: FontWeight.w600)),
                  Text('${d.knownCorrect} z ${d.knownAnswers} odpowiedzi', style: TextStyle(color: scheme.outline)),
                ],
              ],
            ),
          ),
        ),
        const SizedBox(height: 8),
        Text(
          'Sesja = seria odpowiedzi bez przerwy dłuższej niż $sessionGapMinutes min. W statystykach są odpowiedzi z nauki i '
          'powtórek oraz błędy z TESTU (poprawne odpowiedzi w teście nie są zapisywane w dzienniku).',
          style: TextStyle(fontSize: 12, color: scheme.outline),
        ),
      ],
    );
  }
}

class _Sessions extends ConsumerWidget {
  const _Sessions(this.d);

  final StatsData d;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final known = ref.watch(sessionsKnownOnlyProvider);
    final scheme = Theme.of(context).colorScheme;
    final toggle = Padding(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
      child: SegmentedButton<bool>(
        segments: const [
          ButtonSegment(value: false, label: Text('Wszystkie pytania')),
          ButtonSegment(value: true, label: Text('Tylko znane')),
        ],
        selected: {known},
        onSelectionChanged: (v) => ref.read(sessionsKnownOnlyProvider.notifier).state = v.first,
      ),
    );
    final note = Padding(
      padding: const EdgeInsets.fromLTRB(16, 4, 16, 4),
      child: Text(
        known
            ? 'Pytania znane = pokazane już wcześniej (drugie i kolejne pojawienie się pytania). Pierwsze odpowiedzi na nowe pytania są pominięte.'
            : 'Wszystkie odpowiedzi, także pierwsze na nowe pytania.',
        style: TextStyle(fontSize: 12, color: scheme.outline),
      ),
    );
    if (d.sessions.isEmpty && d.tests.isEmpty) {
      return Column(children: [toggle, note, const Expanded(child: Center(child: Text('Brak sesji — zacznij naukę.')))]);
    }
    // sesje nauki i zakończone testy w jednej liście, od najnowszych
    final entries = <({DateTime at, SessionStat? s, int number, TestResult? t})>[
      for (var i = 0; i < d.sessions.length; i++) (at: d.sessions[i].start, s: d.sessions[i], number: d.sessions.length - i, t: null),
      for (final t in d.tests) (at: t.timestamp, s: null, number: 0, t: t),
    ]..sort((a, b) => b.at.compareTo(a.at));
    return Column(
      children: [
        toggle,
        note,
        Expanded(
          child: ListView.separated(
            padding: const EdgeInsets.all(16),
            itemCount: entries.length,
            separatorBuilder: (_, __) => const SizedBox(height: 8),
            itemBuilder: (_, i) {
              final e = entries[i];
              final t = e.t;
              if (t != null) return _TestCard(t);
              final s = e.s!;
              final n = known ? s.knownAnswers : s.answers;
              final ok = known ? s.knownCorrect : s.correct;
              final pct = known ? s.knownPercent : s.percent;
              return Card(
                margin: EdgeInsets.zero,
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: Text('Sesja ${e.number} · ${_fmtDate(s.start)}',
                                style: const TextStyle(fontWeight: FontWeight.w600)),
                          ),
                          Text(n == 0 ? '—' : _pct(pct),
                              style: TextStyle(fontWeight: FontWeight.bold, color: scheme.primary)),
                        ],
                      ),
                      const SizedBox(height: 6),
                      LinearProgressIndicator(
                          value: n == 0 ? 0 : pct / 100, minHeight: 6, borderRadius: BorderRadius.circular(3)),
                      const SizedBox(height: 4),
                      Text(
                        n == 0
                            ? 'brak powtórzonych pytań w tej sesji (${s.answers} odpowiedzi na nowe)'
                            : '$ok poprawnych z $n odpowiedzi',
                        style: TextStyle(fontSize: 12, color: scheme.outline),
                      ),
                    ],
                  ),
                ),
              );
            },
          ),
        ),
      ],
    );
  }
}

class _Hardest extends ConsumerWidget {
  const _Hardest(this.d);

  final StatsData d;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final count = ref.watch(hardestCountProvider);
    final scheme = Theme.of(context).colorScheme;
    final shown = d.ranked.take(count).toList();
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
          child: SegmentedButton<int>(
            segments: [for (final n in hardestListSizes) ButtonSegment(value: n, label: Text('$n'))],
            selected: {count},
            onSelectionChanged: (v) => ref.read(hardestCountProvider.notifier).state = v.first,
          ),
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 4, 16, 4),
          child: Text(
            d.ranked.isEmpty
                ? 'Brak pytań z błędami.'
                : 'Najtrudniejsze pytania (${shown.length} z ${d.ranked.length} z błędami), od najgorszych.',
            style: TextStyle(fontSize: 12, color: scheme.outline),
          ),
        ),
        Expanded(
          child: ListView.separated(
            padding: const EdgeInsets.fromLTRB(16, 4, 16, 16),
            itemCount: shown.length,
            separatorBuilder: (_, __) => const Divider(height: 1),
            itemBuilder: (_, i) {
              final s = shown[i];
              return ListTile(
                contentPadding: EdgeInsets.zero,
                leading: Text('${i + 1}.', style: TextStyle(color: scheme.outline)),
                title: Text(s.pytanie, maxLines: 2, overflow: TextOverflow.ellipsis),
                subtitle: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('ID ${s.id} · błędy ${s.wrong}/${s.attempts} (${_pct(100 * s.errorRate)})'),
                    if (s.correctText.isNotEmpty)
                      Text('Poprawna: ${s.correctText}',
                          maxLines: 3,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(color: AnswerHighlightColors.of(context).feedbackCorrect, fontWeight: FontWeight.w500)),
                  ],
                ),
              );
            },
          ),
        ),
      ],
    );
  }
}

/// Wpis zakończonego TESTU na liście sesji.
class _TestCard extends StatelessWidget {
  const _TestCard(this.t);

  final TestResult t;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final pct = t.total == 0 ? 0.0 : 100 * t.correct / t.total;
    final dark = Theme.of(context).brightness == Brightness.dark;
    final accent = dark ? testOrange : testOrangeDark;
    return Card(
      key: ValueKey('test-card-${t.timestamp.millisecondsSinceEpoch}'),
      margin: EdgeInsets.zero,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: testOrange.withValues(alpha: 0.7)),
      ),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text('TEST · ${_fmtDate(t.timestamp)}',
                      style: TextStyle(fontWeight: FontWeight.w600, color: accent)),
                ),
                Text(_pct(pct), style: TextStyle(fontWeight: FontWeight.bold, color: accent)),
              ],
            ),
            if (t.hard)
              Text('Wersja trudna', style: TextStyle(fontSize: 11, color: scheme.outline, fontStyle: FontStyle.italic)),
            const SizedBox(height: 6),
            LinearProgressIndicator(
              value: pct / 100,
              minHeight: 6,
              color: accent,
              borderRadius: BorderRadius.circular(3),
            ),
            const SizedBox(height: 4),
            Text(
              '${t.correct} poprawnych z ${t.total} · ${t.passed ? 'zaliczony' : 'niezaliczony'} (próg ${t.passMark})',
              style: TextStyle(fontSize: 12, color: t.passed ? Colors.green.shade700 : scheme.error),
            ),
          ],
        ),
      ),
    );
  }
}
