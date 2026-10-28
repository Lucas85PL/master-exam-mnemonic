import 'dart:io';

import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';

/// Tryb przenośny (standalone PC): jeśli obok pliku .exe leży `portable.flag`, program trzyma bazę i ustawienia
/// w folderze `user_data` obok .exe — nie dotyka `Documents\memonic_app.db` ani zwykłych ustawień użytkownika.
class AppPaths {
  static const portableFlag = 'portable.flag';
  static const portableDataDir = 'user_data';

  static String? _exeDir;

  static String get exeDir => _exeDir ??= p.dirname(Platform.resolvedExecutable);

  static bool get isPortable {
    if (!(Platform.isWindows || Platform.isLinux || Platform.isMacOS)) return false;
    try {
      return File(p.join(exeDir, portableFlag)).existsSync();
    } catch (_) {
      return false;
    }
  }

  /// Folder danych portable (tworzony przy pierwszym użyciu).
  static Directory get portableDir {
    final d = Directory(p.join(exeDir, portableDataDir));
    if (!d.existsSync()) d.createSync(recursive: true);
    return d;
  }

  /// Folder z bazą: `user_data` (portable) albo dokumenty użytkownika (zwykła instalacja / Android).
  static Future<Directory> dataDir() async {
    if (isPortable) return portableDir;
    return getApplicationDocumentsDirectory();
  }
}
