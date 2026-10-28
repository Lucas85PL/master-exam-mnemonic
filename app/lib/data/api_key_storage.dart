import 'package:shared_preferences/shared_preferences.dart';

const _keyApiKey = 'openrouter_api_key';

/// Klucz API w SharedPreferences (lokalnie na urządzeniu użytkownika).
class ApiKeyStorage {
  Future<String?> read() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_keyApiKey);
  }

  Future<void> write(String key) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_keyApiKey, key);
  }

  Future<void> delete() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_keyApiKey);
  }
}
