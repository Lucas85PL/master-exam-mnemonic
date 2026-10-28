import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:memonic_app/data/portable_prefs.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:shared_preferences_platform_interface/shared_preferences_platform_interface.dart';

void main() {
  test('ustawienia w pliku JSON: zapis, odczyt po ponownym otwarciu, brak cudzych kluczy', () async {
    final dir = await Directory.systemTemp.createTemp('portable_prefs');
    final file = File('${dir.path}/settings.json');
    final old = SharedPreferencesStorePlatform.instance;
    addTearDown(() {
      SharedPreferencesStorePlatform.instance = old;
      dir.deleteSync(recursive: true);
    });

    SharedPreferencesStorePlatform.instance = await PortablePrefsStore.open(file);
    var prefs = await SharedPreferences.getInstance();
    expect(prefs.getString('openrouter_api_key'), isNull); // wersja przenośna startuje bez klucza API
    await prefs.setString('exam_date', '2026-12-01T00:00:00.000');
    await prefs.setInt('test_total', 105);
    await prefs.setBool('ai_explain_enabled', false);
    await prefs.setStringList('lista', ['a', 'b']);
    expect(file.existsSync(), isTrue);

    // „restart programu”: nowy magazyn z tego samego pliku
    SharedPreferences.resetStatic();
    SharedPreferencesStorePlatform.instance = await PortablePrefsStore.open(file);
    prefs = await SharedPreferences.getInstance();
    expect(prefs.getString('exam_date'), '2026-12-01T00:00:00.000');
    expect(prefs.getInt('test_total'), 105);
    expect(prefs.getBool('ai_explain_enabled'), false);
    expect(prefs.getStringList('lista'), ['a', 'b']);
    await prefs.remove('test_total');
    SharedPreferences.resetStatic();
    SharedPreferencesStorePlatform.instance = await PortablePrefsStore.open(file);
    prefs = await SharedPreferences.getInstance();
    expect(prefs.getInt('test_total'), isNull);
    expect(file.readAsStringSync().contains('openrouter'), isFalse);
  });
}
