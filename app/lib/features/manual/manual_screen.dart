import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../widgets/app_drawer.dart';
import 'manual_content.dart';

/// Język Manuala: false = polski, true = angielski.
final manualEnglishProvider = StateProvider<bool>((ref) => false);

const _icons = <String, IconData>{
  'home': Icons.home_outlined,
  'school': Icons.school_outlined,
  'timer': Icons.timer_outlined,
  'auto_awesome': Icons.auto_awesome,
  'assignment': Icons.assignment_outlined,
  'local_fire_department': Icons.local_fire_department_outlined,
  'bar_chart': Icons.bar_chart,
  'slideshow': Icons.slideshow,
  'storage': Icons.storage,
  'settings': Icons.settings_outlined,
  'sync_alt': Icons.sync_alt,
  'lightbulb': Icons.lightbulb_outline,
  'mail_outline': Icons.mail_outline,
};

class ManualScreen extends ConsumerWidget {
  const ManualScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final en = ref.watch(manualEnglishProvider);
    final scheme = Theme.of(context).colorScheme;
    return Scaffold(
      drawer: const AppDrawer(),
      appBar: AppBar(title: Text(manualTitle.of(en))),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Center(
            child: SegmentedButton<bool>(
              segments: const [
                ButtonSegment(value: false, label: Text('PL')),
                ButtonSegment(value: true, label: Text('ENG')),
              ],
              selected: {en},
              onSelectionChanged: (v) => ref.read(manualEnglishProvider.notifier).state = v.first,
            ),
          ),
          const SizedBox(height: 16),
          Text(manualIntro.of(en), style: const TextStyle(fontSize: 16)),
          const SizedBox(height: 12),
          for (var i = 0; i < manualSections.length; i++)
            Card(
              margin: const EdgeInsets.only(bottom: 8),
              child: Theme(
                data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
                child: ExpansionTile(
                  key: PageStorageKey('manual-$i'),
                  initiallyExpanded: i == 0,
                  leading: Icon(_icons[manualSections[i].icon] ?? Icons.info_outline, color: scheme.primary),
                  title: Text(manualSections[i].title.of(en), style: const TextStyle(fontWeight: FontWeight.w600)),
                  childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
                  expandedCrossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    for (final p in manualSections[i].body) _Paragraph(p.of(en)),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _Paragraph extends StatelessWidget {
  const _Paragraph(this.text);

  final String text;

  @override
  Widget build(BuildContext context) {
    final bullet = text.startsWith('• ');
    return Padding(
      padding: EdgeInsets.only(bottom: 8, left: bullet ? 8 : 0),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (bullet) const Padding(padding: EdgeInsets.only(right: 8), child: Text('•', style: TextStyle(fontSize: 15))),
          Expanded(child: Text(bullet ? text.substring(2) : text, style: const TextStyle(fontSize: 15, height: 1.35))),
        ],
      ),
    );
  }
}
