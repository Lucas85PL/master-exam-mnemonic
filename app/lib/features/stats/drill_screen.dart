import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../domain/hardest.dart';
import '../../providers/app_providers.dart';
import '../../widgets/app_drawer.dart';

/// „Powtórka trudnych”: wybór 50/100/150/200 pytań z puli pytań, na które już odpowiadano.
class DrillScreen extends ConsumerStatefulWidget {
  const DrillScreen({super.key});

  @override
  ConsumerState<DrillScreen> createState() => _DrillScreenState();
}

class _DrillScreenState extends ConsumerState<DrillScreen> {
  int _count = drillSizes.first;

  /// Kolejność pytań: true = od najtrudniejszych, false = losowo.
  bool _hardestFirst = false;
  bool _busy = false;

  Future<void> _start() async {
    setState(() => _busy = true);
    try {
      final repo = await ref.read(repositoryProvider.future);
      final ranked = rankByDifficulty(await repo.questionErrorStats());
      if (ranked.isEmpty) {
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Brak przerobionych pytań — najpierw zacznij naukę.')),
        );
        return;
      }
      final picked = orderDrill(pickByNormalRank(ranked, _count, Random()), hardestFirst: _hardestFirst);
      ref.read(drillQueueProvider.notifier).state = [for (final s in picked) s.id];
      ref.read(reviewAheadProvider.notifier).state = false;
      if (!mounted) return;
      context.push('/study');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Scaffold(
      drawer: const AppDrawer(),
      appBar: AppBar(title: const Text('Powtórka trudnych')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text('Ile pytań powtórzyć?', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 12),
          SegmentedButton<int>(
            segments: [for (final n in drillSizes) ButtonSegment(value: n, label: Text('$n'))],
            selected: {_count},
            onSelectionChanged: (v) => setState(() => _count = v.first),
          ),
          const SizedBox(height: 20),
          Text('Kolejność', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 12),
          SegmentedButton<bool>(
            key: const ValueKey('drill-order'),
            segments: const [
              ButtonSegment(value: true, label: Text('Od najtrudniejszych')),
              ButtonSegment(value: false, label: Text('Losowo')),
            ],
            selected: {_hardestFirst},
            onSelectionChanged: (v) => setState(() => _hardestFirst = v.first),
          ),
          const SizedBox(height: 16),
          Text(
            'Pytania są losowane spośród tych, na które już odpowiadałeś — im częściej odpowiadałeś błędnie, tym większa szansa '
            '(rozkład normalny względem rankingu trudności: najgorsze pytania wchodzą niemal zawsze, dalsze coraz rzadziej). '
            'Większa liczba (np. 100 zamiast 50) poszerza zakres losowanych pytań o kolejne, nieco łatwiejsze.',
            style: TextStyle(color: scheme.outline),
          ),
          const SizedBox(height: 24),
          FilledButton.icon(
            onPressed: _busy ? null : _start,
            icon: const Icon(Icons.local_fire_department),
            label: Text('Start powtórki ($_count pytań)'),
          ),
        ],
      ),
    );
  }
}
