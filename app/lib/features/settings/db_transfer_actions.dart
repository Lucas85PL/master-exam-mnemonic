import 'dart:io';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/db_transfer_service.dart';
import '../../providers/app_providers.dart';

String _stamp() {
  final n = DateTime.now();
  String two(int v) => v.toString().padLeft(2, '0');
  return '${n.year}${two(n.month)}${two(n.day)}_${two(n.hour)}${two(n.minute)}';
}

void _snack(BuildContext context, String text) {
  if (!context.mounted) return;
  ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text)));
}

/// Eksport całej bazy (pytania ze statusami OK/Błąd, postęp nauki, cache wyjaśnień).
Future<void> exportDatabase(BuildContext context, WidgetRef ref) async {
  try {
    final db = await ref.read(databaseProvider.future);
    final bytes = await DbTransferService(db).snapshotBytes();
    final fileName = 'memonic_baza_${_stamp()}.db';

    final mobile = Platform.isAndroid || Platform.isIOS;
    final picked = await FilePicker.platform.saveFile(
      dialogTitle: 'Eksport bazy danych',
      fileName: fileName,
      type: FileType.any,
      bytes: mobile ? bytes : null,
    );
    if (picked == null || !context.mounted) return; // anulowano

    var target = picked;
    if (!mobile) {
      if (!target.toLowerCase().endsWith('.db')) target = '$target.db';
      await File(target).writeAsBytes(bytes, flush: true);
    }
    if (!context.mounted) return;
    _snack(context, 'Wyeksportowano bazę (${(bytes.length / 1024 / 1024).toStringAsFixed(1)} MB)');
  } catch (e) {
    if (!context.mounted) return;
    _snack(context, 'Eksport nie powiódł się: $e');
  }
}

/// Import bazy z zewnątrz: plik → wybór trybu A/B/C/D → potwierdzenie → wykonanie.
Future<void> importDatabase(BuildContext context, WidgetRef ref) async {
  final picked = await FilePicker.platform.pickFiles(type: FileType.any);
  final path = picked?.files.single.path;
  if (path == null || !context.mounted) return;

  try {
    DbTransferService.inspectSource(path);
  } on ImportSourceException catch (e) {
    if (!context.mounted) return;
    _snack(context, e.message);
    return;
  }
  if (!context.mounted) return;

  final mode = await _askMode(context);
  if (mode == null || !context.mounted) return;

  final sure = await showDialog<bool>(
    context: context,
    builder: (ctx) => AlertDialog(
      title: Text('Czy na pewno wykonać: ${mode.letter}?'),
      content: Text('${mode.letter} — ${mode.title}\n\n${mode.description}'),
      actions: [
        TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Anuluj')),
        FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Wykonaj')),
      ],
    ),
  );
  if (sure != true || !context.mounted) return;

  showDialog<void>(
    context: context,
    barrierDismissible: false,
    builder: (_) => const Center(child: CircularProgressIndicator()),
  );
  String message;
  try {
    final db = await ref.read(databaseProvider.future);
    final r = await DbTransferService(db).run(mode, path);
    ref.invalidate(databaseProvider);
    ref.invalidate(studyStatsProvider);
    switch (mode) {
      case ImportMode.fullOverwrite:
        message = 'Zaimportowano bazę (A). Kopia poprzedniej: ${r.backupPath}';
      case ImportMode.statusesOnly:
        message = 'Statusy (B): zaktualizowano ${r.updated}, bez zmian ${r.unchanged}, '
            'nie znaleziono ${r.notFound}, niejednoznaczne ${r.ambiguous}';
      case ImportMode.missingQuestions:
        message = 'Nowe pytania (C): dodano ${r.added}, pominięto ${r.skipped}';
      case ImportMode.updateKeepProgress:
        message = 'Aktualizacja (D): dodano ${r.added} nowych pytań, zmieniono ${r.updated} '
            '(w tym poprawny klucz: ${r.keyChanged}), bez zmian ${r.unchanged}, pominięto ${r.skipped}. '
            'Postęp nauki zachowany.';
    }
  } catch (e) {
    message = 'Import nie powiódł się: $e';
  }
  if (context.mounted) Navigator.of(context, rootNavigator: true).pop();
  if (!context.mounted) return;
  await showDialog<void>(
    context: context,
    builder: (ctx) => AlertDialog(
      title: const Text('Import bazy'),
      content: Text(message),
      actions: [TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('OK'))],
    ),
  );
}

Future<ImportMode?> _askMode(BuildContext context) {
  var selected = ImportMode.updateKeepProgress;
  return showDialog<ImportMode>(
    context: context,
    builder: (ctx) => StatefulBuilder(
      builder: (ctx, setState) => AlertDialog(
        title: const Text('Import bazy — wybierz tryb'),
        content: SingleChildScrollView(
          child: RadioGroup<ImportMode>(
            groupValue: selected,
            onChanged: (v) => setState(() => selected = v ?? selected),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                for (final m in ImportMode.values)
                  RadioListTile<ImportMode>(
                    value: m,
                    title: Text('${m.letter} — ${m.title}'),
                    subtitle: Text(m.description, style: const TextStyle(fontSize: 12)),
                  ),
              ],
            ),
          ),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Anuluj')),
          FilledButton(onPressed: () => Navigator.pop(ctx, selected), child: const Text('Dalej')),
        ],
      ),
    ),
  );
}
