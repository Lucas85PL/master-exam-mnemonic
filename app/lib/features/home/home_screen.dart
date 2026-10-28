import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../domain/category_filter.dart';
import '../../domain/study_plan.dart';
import '../../providers/app_providers.dart';
import '../../providers/settings_providers.dart';
import '../test/test_screen.dart' show testOrange;
import '../../widgets/app_drawer.dart';

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  /// Zaznacza/odznacza dział; co najmniej jeden dział musi zostać zaznaczony.
  Future<void> _toggle(BuildContext context, WidgetRef ref, StudyCategory current, StudyCategory c) async {
    final picked = {...current.values};
    final v = c.values.first;
    if (picked.contains(v)) {
      if (picked.length == 1) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Zostaw zaznaczony co najmniej jeden dział'), duration: Duration(seconds: 2)),
        );
        return;
      }
      picked.remove(v);
    } else {
      picked.add(v);
    }
    await ref.read(selectedCategoryProvider.notifier).setSelected(picked);
    ref.invalidate(studyStatsProvider);
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final category = ref.watch(selectedCategoryProvider);
    final statsAsync = ref.watch(studyStatsProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Master Exam Mnemonic')),
      drawer: const AppDrawer(),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(
              'Działy do nauki',
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 4),
            Row(
              children: [
                for (final c in StudyCategory.selectable)
                  Expanded(
                    child: InkWell(
                      key: ValueKey('cat-${c.label}'),
                      borderRadius: BorderRadius.circular(8),
                      onTap: () => _toggle(context, ref, category, c),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Checkbox(
                            value: category.values.contains(c.values.first),
                            onChanged: (_) => _toggle(context, ref, category, c),
                          ),
                          Flexible(child: Text(c.label, overflow: TextOverflow.ellipsis)),
                        ],
                      ),
                    ),
                  ),
              ],
            ),
            const SizedBox(height: 24),
            statsAsync.when(
              data: (s) => Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      _ProgressBar(plan: s.plan),
                      const SizedBox(height: 12),
                      Text('Pula (OK): ${s.total}'),
                      Text('Do powtórki teraz: ${s.due}'),
                      Text('Zaplanowane na najbliższe 24 h: ${s.upcoming}'),
                      Text('Nowe karty: ${s.newCards}'),
                      if (s.hard > 0) Text('Trudne (często błędne): ${s.hard}'),
                    ],
                  ),
                ),
              ),
              loading: () => const Center(child: CircularProgressIndicator()),
              error: (e, _) => Text('Błąd: $e'),
            ),
            const SizedBox(height: 24),
            OutlinedButton.icon(
              onPressed: statsAsync.maybeWhen(
                data: (s) => s.upcoming + s.due > 0
                    ? () {
                        ref.read(reviewAheadProvider.notifier).state = true;
                        ref.read(drillQueueProvider.notifier).state = null;
                        context.push('/study');
                      }
                    : null,
                orElse: () => null,
              ),
              icon: const Icon(Icons.replay),
              label: const Text('Powtórz zaplanowane (24 h)'),
            ),
            const SizedBox(height: 12),
            _TestButton(),
            const SizedBox(height: 12),
            FilledButton.icon(
              onPressed: statsAsync.maybeWhen(
                data: (s) => s.total > 0 && !(ref.watch(newOnlyProvider) && s.newCards == 0)
                    ? () {
                        ref.read(reviewAheadProvider.notifier).state = false;
                        ref.read(drillQueueProvider.notifier).state = null;
                        context.push('/study');
                      }
                    : null,
                orElse: () => null,
              ),
              icon: const Icon(Icons.school),
              label: const Text('Start nauki'),
            ),
            const SizedBox(height: 8),
            SegmentedButton<bool>(
              segments: const [
                ButtonSegment(value: false, label: Text('Wszystkie')),
                ButtonSegment(value: true, label: Text('Same nowe')),
              ],
              selected: {ref.watch(newOnlyProvider)},
              onSelectionChanged: (v) => ref.read(newOnlyProvider.notifier).state = v.first,
            ),
          ],
        ),
      ),
    );
  }

}

/// „Pasek doświadczenia”: ile pytań jest już znanych (seria 3 dni nauki) + dzienny cel do egzaminu.
class _ProgressBar extends StatelessWidget {
  const _ProgressBar({required this.plan});

  final DailyPlan plan;

  @override
  Widget build(BuildContext context) {
    final pct = (plan.progress * 100).toStringAsFixed(plan.progress > 0 && plan.progress < 0.1 ? 1 : 0);
    final scheme = Theme.of(context).colorScheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            const Text('Opanowanie materiału', style: TextStyle(fontWeight: FontWeight.bold)),
            Text('$pct%', style: const TextStyle(fontWeight: FontWeight.bold)),
          ],
        ),
        const SizedBox(height: 6),
        ClipRRect(
          borderRadius: BorderRadius.circular(6),
          child: LinearProgressIndicator(value: plan.progress, minHeight: 12),
        ),
        const SizedBox(height: 4),
        Text(
          'Znane: ${plan.known} / ${plan.total} (poprawne odpowiedzi 3 dni nauki z rzędu)',
          style: TextStyle(fontSize: 12, color: scheme.outline),
        ),
        const SizedBox(height: 6),
        if (!plan.hasExam)
          Text('Ustaw termin egzaminu w Ustawieniach, aby zobaczyć dzienny cel.',
              style: TextStyle(fontSize: 13, color: scheme.outline))
        else if (plan.remainingReviews == 0)
          const Text('Cały materiał opanowany — wystarczy utrzymanie powtórkami.')
        else ...[
          Text(
            'Cel na dziś: ${plan.doneToday} / ${plan.goalToday} pytań'
            '${plan.hasOwnData ? '' : ' (szacunek — za mało własnych danych o tempie)'}',
            style: TextStyle(
              fontWeight: FontWeight.w600,
              color: plan.tooLate ? Colors.orange : null,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            plan.daysLeft == 0
                ? 'Termin docelowy (egzamin − $examBufferDays dni) minął. Do opanowania zostało ok. ${plan.total - plan.known} pytań.'
                : 'Do opanowania: ok. ${plan.total - plan.known} pytań w ${plan.daysLeft} dni (do terminu docelowego = egzamin − $examBufferDays dni). '
                    'Twoje tempo (ostatnie ${plan.windowDays} dni): ~${plan.answersPerDay.round()} odpowiedzi dziennie, '
                    'opanowujesz ~${plan.masteredPerDay.toStringAsFixed(1)} pytań dziennie; '
                    'jedno opanowane pytanie kosztuje Cię ok. ${(plan.costPerUnit * knownStreakDays).toStringAsFixed(1)} odpowiedzi.',
            style: TextStyle(fontSize: 12, color: scheme.outline),
          ),
          const SizedBox(height: 2),
          Builder(builder: (context) {
            final d = plan.projectedDays;
            if (d == null) {
              return Text(
                'Prognoza: brak jeszcze przyrostu opanowanych pytań — po kilku dniach nauki pokażę, kiedy opanujesz materiał.',
                style: TextStyle(fontSize: 12, color: scheme.outline),
              );
            }
            final date = DateTime.now().add(Duration(days: d));
            final diff = plan.daysLeft - d;
            final ok = diff >= 0;
            return Text(
              'Prognoza przy obecnym tempie: opanowanie ok. '
              '${date.day.toString().padLeft(2, '0')}.${date.month.toString().padLeft(2, '0')} — '
              '${ok ? (diff == 0 ? 'dokładnie w terminie' : '$diff dni przed terminem') : '${-diff} dni po terminie, zwiększ tempo do ok. ${plan.goalToday} pytań dziennie'}.',
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w600,
                color: ok ? Colors.green.shade700 : Colors.orange.shade800,
              ),
            );
          }),
        ],
      ],
    );
  }
}

/// Przycisk TEST (pastelowy pomarańcz) + wynik ostatniego testu.
class _TestButton extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final cfg = ref.watch(testConfigProvider);
    final last = ref.watch(lastTestProvider).valueOrNull;
    final scheme = Theme.of(context).colorScheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        FilledButton.icon(
          style: FilledButton.styleFrom(
            backgroundColor: testOrange,
            foregroundColor: Colors.black87,
            padding: const EdgeInsets.symmetric(vertical: 16),
          ),
          onPressed: () => context.push('/test'),
          icon: const Icon(Icons.quiz),
          label: Text('TEST  (${cfg.total} pytań, zaliczenie ${cfg.passMark})',
              style: const TextStyle(fontWeight: FontWeight.bold)),
        ),
        const SizedBox(height: 8),
        SegmentedButton<bool>(
          key: const ValueKey('test-mode'),
          segments: const [
            ButtonSegment(value: false, label: Text('Normalny')),
            ButtonSegment(value: true, label: Text('Trudny')),
          ],
          selected: {ref.watch(testHardProvider)},
          onSelectionChanged: (v) => ref.read(testHardProvider.notifier).state = v.first,
        ),
        if (last != null)
          Padding(
            padding: const EdgeInsets.only(top: 4),
            child: Text(
              'Ostatni test: ${last.correct} / ${last.total} — ${last.passed ? 'zaliczony' : 'niezaliczony'}',
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 12,
                color: last.passed ? Colors.green.shade700 : scheme.error,
              ),
            ),
          ),
      ],
    );
  }
}
