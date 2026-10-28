/// Filtry kategorii UI → wartości w bazie pipeline. Filtr to zbiór działów ([values]); pusty zbiór = bez filtra (wszystkie).
class StudyCategory {
  const StudyCategory(this.label, this.values);

  final String label;

  /// Wartości kolumny `kategoria` objęte filtrem (pusta lista = wszystkie).
  final List<String> values;

  /// Wartość dla filtra jednego działu (null = wiele działów lub wszystkie).
  String? get dbValue => values.length == 1 ? values.first : null;

  bool get isAll => values.isEmpty;

  static const all = StudyCategory('All', []);
  static const master = StudyCategory('Master', ['Kapitan żeglugi wielkiej']);
  static const angielski = StudyCategory('Angielski', ['Angielski']);
  static const poklad = StudyCategory('Pokład', ['Dział pokładowy']);

  /// Pojedyncze działy (używane m.in. w TEŚCIE i w liście Bazy Danych).
  static const choices = [all, master, angielski, poklad];

  /// Działy do wyboru (zaznaczane) na ekranie głównym — w tej kolejności.
  static const selectable = [master, angielski, poklad];

  /// Filtr złożony z zaznaczonych działów (kolejność jak w [selectable]); pusty zbiór = wszystkie działy.
  static StudyCategory fromSelected(Set<String> dbValues) {
    final picked = [for (final c in selectable) if (dbValues.contains(c.values.first)) c];
    if (picked.isEmpty) return all;
    return StudyCategory(picked.map((c) => c.label).join(' + '), [for (final c in picked) c.values.first]);
  }

  @override
  bool operator ==(Object other) =>
      other is StudyCategory && other.values.length == values.length && other.values.every(values.contains);

  @override
  int get hashCode => Object.hashAllUnordered(values);

  /// Wsteczna zgodność z poprzednimi nazwami.
  static const kapitan = master;
  static const dzial = poklad;
}
