import 'dart:io';

import 'package:flutter/services.dart';
import 'package:sqflite/sqflite.dart';

/// Kopiuje wbudowaną bazę (postęp nauki z buildu RC) przy pierwszym uruchomieniu.
class SeedDatabase {
  static const assetPath = 'assets/db/memonic_app_seed.db';

  static Future<void> ensureInstalled(String targetPath) async {
    final file = File(targetPath);
    if (await file.exists()) {
      try {
        final db = await openDatabase(targetPath, readOnly: true);
        final rows = await db.rawQuery('SELECT COUNT(*) AS c FROM questions');
        await db.close();
        final count = rows.first['c'] as int? ?? 0;
        if (count > 0) return;
      } catch (_) {
        // uszkodzony plik — nadpisz seedem
      }
      await file.delete();
    }

    final byteData = await rootBundle.load(assetPath);
    await file.parent.create(recursive: true);
    await file.writeAsBytes(
      byteData.buffer.asUint8List(
        byteData.offsetInBytes,
        byteData.lengthInBytes,
      ),
      flush: true,
    );
  }
}
