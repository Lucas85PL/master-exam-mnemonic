import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../data/ai_disputed.dart';
import '../../data/question_categories.dart';
import '../../domain/fsrs.dart';
import '../../providers/app_providers.dart';
import '../../widgets/app_drawer.dart';
import '../../widgets/question_image.dart';

class QuestionEditScreen extends ConsumerStatefulWidget {
  const QuestionEditScreen({super.key, required this.questionId});

  final int questionId;

  @override
  ConsumerState<QuestionEditScreen> createState() =>
      _QuestionEditScreenState();
}

class _QuestionEditScreenState extends ConsumerState<QuestionEditScreen> {
  final _pytanie = TextEditingController();
  final _odpA = TextEditingController();
  final _odpB = TextEditingController();
  final _odpC = TextEditingController();
  final _odpD = TextEditingController();
  String _correct = 'A';
  String _originalCorrect = 'A';
  bool _studyHidden = false;
  bool _uncertain = false;
  bool _loading = true;
  String? _reviewStatus;
  Set<String> _categories = {};
  Set<String> _originalCategories = {};
  String? _imagePath;
  FsrsCard? _srs;

  @override
  void dispose() {
    _pytanie.dispose();
    _odpA.dispose();
    _odpB.dispose();
    _odpC.dispose();
    _odpD.dispose();
    super.dispose();
  }

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final repo = await ref.read(repositoryProvider.future);
    final row = await repo.getQuestionById(widget.questionId);
    if (!mounted) return;
    if (row == null) {
      setState(() => _loading = false);
      return;
    }
    _pytanie.text = row['pytanie'] as String? ?? '';
    _odpA.text = row['odp_a'] as String? ?? '';
    _odpB.text = row['odp_b'] as String? ?? '';
    _odpC.text = row['odp_c'] as String? ?? '';
    _odpD.text = row['odp_d'] as String? ?? '';
    _correct = (row['poprawna_odpowiedz'] as String? ?? 'A').toUpperCase();
    _originalCorrect = _correct;
    _studyHidden = (row['study_hidden'] as int? ?? 0) == 1;
    _reviewStatus = row['review_status'] as String?;
    _categories = (await repo.categoriesOf(widget.questionId)).toSet();
    _originalCategories = {..._categories};
    _imagePath = row['image_path'] as String?;
    _uncertain = AiDisputed.ids.contains(widget.questionId);
    _srs = await repo.loadSrs(widget.questionId);
    setState(() => _loading = false);
  }

  String _optionText(String letter) =>
      {'A': _odpA, 'B': _odpB, 'C': _odpC, 'D': _odpD}[letter]!.text.trim();

  Future<void> _save() async {
    String? problem;
    if (_pytanie.text.trim().isEmpty) {
      problem = 'Treść pytania nie może być pusta.';
    } else if (_categories.isEmpty) {
      problem = 'Wybierz co najmniej jedną kategorię (Master, Angielski lub Pokład).';
    } else if (_optionText(_correct).isEmpty) {
      problem = 'Poprawna odpowiedź ($_correct) wskazuje pusty wariant.';
    } else if (['A', 'B', 'C', 'D'].where((l) => _optionText(l).isNotEmpty).length < 2) {
      problem = 'Potrzebne są co najmniej dwa warianty odpowiedzi.';
    }
    if (problem != null) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(problem)));
      return;
    }
    // zmiana klucza w pytaniu niepewnym: zapytaj, czy odpowiedź jest już pewna
    if (_uncertain && _correct != _originalCorrect && AiDisputed.ids.contains(widget.questionId)) {
      final sure = await showDialog<bool>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: const Text('Zmienić status pytania na „Pewna odpowiedź”?'),
          content: Text('Zmieniono poprawną odpowiedź z $_originalCorrect na $_correct. Pytanie jest teraz oznaczone jako niepewne.'),
          actions: [
            TextButton(key: const ValueKey('sure-no'), onPressed: () => Navigator.pop(ctx, false), child: const Text('NIE')),
            FilledButton(key: const ValueKey('sure-yes'), onPressed: () => Navigator.pop(ctx, true), child: const Text('TAK')),
          ],
        ),
      );
      if (sure == null) return; // zamknięto okno — nie zapisuj
      if (sure) _uncertain = false;
    }
    final repo = await ref.read(repositoryProvider.future);
    await repo.updateQuestion(widget.questionId, {
      'pytanie': _pytanie.text,
      'odp_a': _odpA.text,
      'odp_b': _odpB.text,
      'odp_c': _odpC.text,
      'odp_d': _odpD.text,
      'poprawna_odpowiedz': _correct,
    });
    if (!(_categories.length == _originalCategories.length && _categories.containsAll(_originalCategories))) {
      await repo.setCategories(widget.questionId, _categories);
    }
    await repo.setStudyHidden(widget.questionId, _studyHidden);
    if (_uncertain != AiDisputed.ids.contains(widget.questionId)) {
      await repo.setUncertain(widget.questionId, _uncertain);
    }
    ref.invalidate(studyStatsProvider);
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Zapisano')),
      );
      context.pop();
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return const Scaffold(
        body: Center(child: CircularProgressIndicator()),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: Text('Pytanie #${widget.questionId}'),
        actions: [
          IconButton(onPressed: _save, icon: const Icon(Icons.save)),
        ],
      ),
      drawer: const AppDrawer(),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Kategoria (dział) — można wybrać kilka:'),
                  const SizedBox(height: 4),
                  Wrap(
                    spacing: 8,
                    children: [
                      for (final k in QuestionCategories.order)
                        FilterChip(
                          key: ValueKey('edit-cat-$k'),
                          label: Text(QuestionCategories.labelOf(k)),
                          selected: _categories.contains(k),
                          onSelected: (on) => setState(() => on ? _categories.add(k) : _categories.remove(k)),
                        ),
                    ],
                  ),
                  const SizedBox(height: 6),
                  Text('Import review_status: ${_reviewStatus ?? "—"}'),
                  if (_srs != null) ...[
                    const SizedBox(height: 8),
                    Text(
                      'FSRS: ocen ${_srs!.reps}, błędów ${_srs!.lapses}, '
                      'stan ${_srs!.state.name}, '
                      'stabilność ${(_srs!.stability ?? 0).toStringAsFixed(1)} d, '
                      'trudność ${(_srs!.difficulty ?? 0).toStringAsFixed(1)}, '
                      'due ${_srs!.due.toLocal().toString().substring(0, 16)}',
                    ),
                  ],
                ],
              ),
            ),
          ),
          const SizedBox(height: 12),
          SwitchListTile(
            title: const Text('Status nauki'),
            subtitle: Text(_studyHidden ? 'Błąd (ukryte)' : 'OK (w puli)'),
            value: !_studyHidden,
            onChanged: (ok) => setState(() => _studyHidden = !ok),
          ),
          SwitchListTile(
            key: const ValueKey('edit-uncertain'),
            title: const Text('Niepewne (odp. niepewna)'),
            subtitle: const Text('Włączone: pytanie ma pomarańczowe tło w nauce i w teście'),
            value: _uncertain,
            onChanged: (v) => setState(() => _uncertain = v),
          ),
          const Divider(),
          if (_imagePath != null) ...[
            QuestionImage(imagePath: _imagePath!),
            const SizedBox(height: 12),
          ],
          TextField(
            key: const ValueKey('edit-question'),
            controller: _pytanie,
            style: _uncertain ? const TextStyle(color: Colors.black87) : null,
            decoration: InputDecoration(
              labelText: 'Pytanie',
              filled: _uncertain,
              fillColor: _uncertain ? AiDisputed.background : null,
              labelStyle: _uncertain ? const TextStyle(color: Colors.black87) : null,
            ),
            minLines: 2,
            maxLines: 8,
          ),
          const SizedBox(height: 8),
          for (final e in {'A': _odpA, 'B': _odpB, 'C': _odpC, 'D': _odpD}.entries)
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: TextField(
                key: ValueKey('edit-opt-${e.key}'),
                controller: e.value,
                decoration: InputDecoration(labelText: 'Odpowiedź ${e.key}'),
                minLines: 1,
                maxLines: 5,
                onChanged: (_) => setState(() {}),
              ),
            ),
          const SizedBox(height: 12),
          DropdownButtonFormField<String>(
            value: _correct,
            decoration: const InputDecoration(labelText: 'Poprawna odpowiedź'),
            items: ['A', 'B', 'C', 'D']
                .where((l) => l == _correct || _optionText(l).isNotEmpty)
                .map((l) => DropdownMenuItem(value: l, child: Text(l)))
                .toList(),
            onChanged: (v) {
              if (v != null) setState(() => _correct = v);
            },
          ),
          const SizedBox(height: 24),
          FilledButton(onPressed: _save, child: const Text('Zapisz')),
        ],
      ),
    );
  }
}
