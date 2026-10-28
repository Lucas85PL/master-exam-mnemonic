import 'dart:convert';
import 'dart:io';

import 'package:path/path.dart' as p;
import 'package:shared_preferences_platform_interface/shared_preferences_platform_interface.dart';
import 'package:shared_preferences_platform_interface/types.dart';

import 'app_paths.dart';

/// Ustawienia aplikacji (SharedPreferences) w trybie przenośnym: zwykły plik JSON `user_data\settings.json`
/// zamiast wspólnego magazynu użytkownika Windows — dzięki temu wersja przenośna nie widzi klucza API ani
/// ustawień zwykłej instalacji i odwrotnie.
class PortablePrefsStore extends SharedPreferencesStorePlatform {
  PortablePrefsStore._(this._file, Map<String, Object> data) : _inner = InMemorySharedPreferencesStore.withData(data);

  final File _file;
  final InMemorySharedPreferencesStore _inner;

  /// Jeśli działa tryb przenośny, podmienia magazyn ustawień. Wywołać przed pierwszym użyciem SharedPreferences.
  static Future<void> installIfPortable() async {
    if (!AppPaths.isPortable) return;
    SharedPreferencesStorePlatform.instance =
        await PortablePrefsStore.open(File(p.join(AppPaths.portableDir.path, 'settings.json')));
  }

  /// Magazyn zapisywany w pliku JSON [file] (wczytuje istniejące wartości).
  static Future<PortablePrefsStore> open(File file) async {
    final data = <String, Object>{};
    if (file.existsSync()) {
      try {
        final raw = jsonDecode(file.readAsStringSync()) as Map<String, dynamic>;
        raw.forEach((k, v) {
          if (v is List) {
            data[k] = v.map((e) => e.toString()).toList();
          } else if (v != null) {
            data[k] = v as Object;
          }
        });
      } catch (_) {
        // uszkodzony plik ustawień — zaczynamy od pustych
      }
    }
    return PortablePrefsStore._(file, data);
  }

  Future<bool> _save() async {
    final all = await _inner.getAll();
    await _file.writeAsString(const JsonEncoder.withIndent(' ').convert(all), flush: true);
    return true;
  }

  @override
  Future<bool> remove(String key) async {
    await _inner.remove(key);
    return _save();
  }

  @override
  Future<bool> setValue(String valueType, String key, Object value) async {
    await _inner.setValue(valueType, key, value);
    return _save();
  }

  @override
  Future<bool> clear() async {
    await _inner.clear();
    return _save();
  }

  @override
  Future<bool> clearWithPrefix(String prefix) async {
    await _inner.clearWithPrefix(prefix);
    return _save();
  }

  @override
  Future<bool> clearWithParameters(ClearParameters parameters) async {
    await _inner.clearWithParameters(parameters);
    return _save();
  }

  @override
  Future<Map<String, Object>> getAll() => _inner.getAll();

  @override
  Future<Map<String, Object>> getAllWithPrefix(String prefix) => _inner.getAllWithPrefix(prefix);

  @override
  Future<Map<String, Object>> getAllWithParameters(GetAllParameters parameters) =>
      _inner.getAllWithParameters(parameters);
}
