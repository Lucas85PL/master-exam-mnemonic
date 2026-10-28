import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../data/ai_disputed.dart';
import '../../data/question_repository.dart';
import '../../domain/category_filter.dart';
import '../../providers/app_providers.dart';
import '../../widgets/app_drawer.dart';

class DatabaseListScreen extends ConsumerStatefulWidget {
  const DatabaseListScreen({super.key});

  @override
  ConsumerState<DatabaseListScreen> createState() => _DatabaseListScreenState();
}

class _DatabaseListScreenState extends ConsumerState<DatabaseListScreen> {
  final _searchController = TextEditingController();
  final _scrollController = ScrollController();
  final List<QuestionListItem> _items = [];
  var _loading = false;
  var _hasMore = true;
  var _offset = 0;
  static const _pageSize = 80;
  String _search = '';
  StudyCategory _category = StudyCategory.all;
  bool _onlyFlaggedError = false;
  bool _onlyUncertain = false;

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(_onScroll);
    _loadMore(reset: true);
  }

  @override
  void dispose() {
    _searchController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _onScroll() {
    if (_scrollController.position.pixels >=
            _scrollController.position.maxScrollExtent - 200 &&
        !_loading &&
        _hasMore) {
      _loadMore();
    }
  }

  Future<void> _loadMore({bool reset = false}) async {
    if (_loading) return;
    setState(() => _loading = true);
    if (reset) {
      _offset = 0;
      _hasMore = true;
      _items.clear();
    }
    final repo = await ref.read(repositoryProvider.future);
    final batch = await repo.listAllQuestions(
      category: _category == StudyCategory.all ? null : _category,
      onlyStudyHidden: _onlyFlaggedError,
      onlyUncertain: _onlyUncertain,
      search: _search.isEmpty ? null : _search,
      limit: _pageSize,
      offset: _offset,
    );
    if (!mounted) return;
    setState(() {
      _items.addAll(batch);
      _offset += batch.length;
      _hasMore = batch.length >= _pageSize;
      _loading = false;
    });
  }

  void _applySearch() {
    _search = _searchController.text.trim();
    _loadMore(reset: true);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Baza Pytań')),
      drawer: const AppDrawer(),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 12, 12, 0),
            child: Column(
              children: [
                Row(
                  children: [
                    Expanded(
                      child: DropdownButtonFormField<StudyCategory>(
                        value: _category,
                        decoration: const InputDecoration(
                          labelText: 'Kategoria',
                          border: OutlineInputBorder(),
                          isDense: true,
                        ),
                        items: StudyCategory.choices
                            .map(
                              (c) => DropdownMenuItem(
                                value: c,
                                child: Text(c.label),
                              ),
                            )
                            .toList(),
                        onChanged: (v) {
                          if (v == null) return;
                          setState(() => _category = v);
                          _loadMore(reset: true);
                        },
                      ),
                    ),
                  ],
                ),
                CheckboxListTile(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Tylko oznaczone jako Błąd'),
                  value: _onlyFlaggedError,
                  onChanged: (v) {
                    setState(() => _onlyFlaggedError = v ?? false);
                    _loadMore(reset: true);
                  },
                  controlAffinity: ListTileControlAffinity.leading,
                ),
                CheckboxListTile(
                  key: const ValueKey('db-only-uncertain'),
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Tylko niepewne'),
                  value: _onlyUncertain,
                  onChanged: (v) {
                    setState(() => _onlyUncertain = v ?? false);
                    _loadMore(reset: true);
                  },
                  controlAffinity: ListTileControlAffinity.leading,
                ),
                Row(
                  children: [
                    Expanded(
                      child: TextField(
                        controller: _searchController,
                        decoration: const InputDecoration(
                          hintText: 'Szukaj (ID lub treść)',
                          border: OutlineInputBorder(),
                          isDense: true,
                        ),
                        onSubmitted: (_) => _applySearch(),
                      ),
                    ),
                    const SizedBox(width: 8),
                    IconButton(
                      onPressed: _applySearch,
                      icon: const Icon(Icons.search),
                    ),
                  ],
                ),
              ],
            ),
          ),
          Expanded(
            child: _items.isEmpty && !_loading
                ? const Center(child: Text('Brak pytań. Zaimportuj bazę w Ustawieniach.'))
                : ListView.builder(
                    controller: _scrollController,
                    itemCount: _items.length + (_hasMore ? 1 : 0),
                    itemBuilder: (context, index) {
                      if (index >= _items.length) {
                        return const Padding(
                          padding: EdgeInsets.all(16),
                          child: Center(child: CircularProgressIndicator()),
                        );
                      }
                      final item = _items[index];
                      final uncertain = AiDisputed.ids.contains(item.id);
                      return ListTile(
                        key: ValueKey('db-item-${item.id}'),
                        tileColor: uncertain ? AiDisputed.background : null,
                        title: Text(
                          '#${item.id} · ${item.pytanie}',
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: uncertain ? const TextStyle(color: Colors.black87) : null,
                        ),
                        subtitle: Text(
                          '${item.kategorieLabel}'
                          '${item.reviewStatus != null ? ' · import: ${item.reviewStatus}' : ''}'
                          '${uncertain ? ' · NIEPEWNE' : ''}',
                          style: uncertain ? const TextStyle(color: Colors.black87) : null,
                        ),
                        trailing: _StatusChip(
                          label: item.studyLabel,
                          isError: item.studyHidden,
                        ),
                        onTap: () async {
                          await context.push('/database/${item.id}');
                          if (mounted) setState(() {}); // odśwież oznaczenie „Niepewne” po edycji
                        },
                      );
                    },
                  ),
          ),
        ],
      ),
    );
  }
}

class _StatusChip extends StatelessWidget {
  const _StatusChip({required this.label, required this.isError});

  final String label;
  final bool isError;

  @override
  Widget build(BuildContext context) {
    return Chip(
      label: Text(label, style: const TextStyle(fontSize: 12)),
      backgroundColor: isError
          ? Colors.red.shade100
          : Colors.green.shade100,
      padding: EdgeInsets.zero,
      visualDensity: VisualDensity.compact,
    );
  }
}
