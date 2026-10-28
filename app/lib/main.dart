import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app.dart';
import 'data/portable_prefs.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await PortablePrefsStore.installIfPortable(); // wersja przenośna: osobne ustawienia (bez klucza API zwykłej instalacji)
  runApp(
    const ProviderScope(
      child: MemonicApp(),
    ),
  );
}
