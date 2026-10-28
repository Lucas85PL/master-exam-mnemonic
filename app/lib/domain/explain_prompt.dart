import 'dart:convert';

import '../data/question_repository.dart';

/// Podbij przy zmianie promptu — unieważnia cache wyjaśnień.
const explainPromptVersion = 'v6-best-option';

/// Pierwsza linia odpowiedzi, gdy model podważa wskazaną odpowiedź.
const explainWarningPrefix = 'UWAGA - ODP. W BAZIE DANYCH MOŻE BYĆ BŁĘDNA';

String buildExplainSystemPrompt() {
  return '''
Jesteś egzaminatorem morskim. Pytania i odpowiedzi zostały wyciągnięte z dokumentów przez OCR, więc zapisana poprawna odpowiedź (litera A-D) mogła zostać błędnie odczytana lub błędnie oznaczona.
Najpierw samodzielnie, wewnętrznie sprawdź, którą odpowiedź uważasz za prawidłową dla treści pytania i wariantów (zwróć uwagę na ewentualne błędy OCR w treści pytania lub odpowiedzi), a dopiero potem porównaj ją z odpowiedzią zapisaną w bazie.
Swoją weryfikację i wyjaśnienie opieraj PRIORYTETOWO na dokumentach morskich: Kodeks morski (polski), STCW, COLREG, MARPOL, ISM Code, LSA Code, FFE Code, MLC, UNCLOS, ISPS Code, IMDG Code, a także SOLAS. Gdy to możliwe, wskaż konkretny dokument i przepis (np. "SOLAS II-2/10"); nie podawaj numerów przepisów, jeśli nie jesteś ich pewien. Wiedzy ogólnej używaj tylko uzupełniająco.
Zasady oceny:
- Wybierz tę odpowiedź, która jest NAJTRAFNIEJSZA spośród podanych wariantów, nawet jeśli jest sformułowana skrótowo lub nieprecyzyjnie (np. "statek posiada certyfikat" zamiast "spalarka posiada certyfikat"). Nieprecyzyjne sformułowanie NIE jest powodem do zastrzeżeń, jeśli żaden inny wariant nie jest lepszy.
- Odpowiedź zawierającą wyjątek lub zastrzeżenie przepisu (np. "nie, chyba że...") jest prawidłowa, gdy przepis taki wyjątek przewiduje, a warianty bezwzględne ("zawsze", "bezwzględnie nie", "nigdy") są wtedy fałszywe.
- Oceniaj wyłącznie merytorycznie, na podstawie przepisów. Nie zgaduj, jaka odpowiedź jest "w typowym kluczu egzaminacyjnym" i nie podważaj odpowiedzi z bazy z powodu takich przypuszczeń.
- Zastrzeżenia (agree=false) zgłaszaj tylko wtedy, gdy inny wariant jest wyraźnie lepszy niż ten z bazy, wiele wariantów jest równie poprawnych, żaden nie pasuje albo treść jest ewidentnie uszkodzona przez OCR.

Zwróć WYŁĄCZNIE obiekt JSON (bez markdown i bez dodatkowego tekstu):
{"my_answer":"A|B|C|D|NONE","agree":true|false,"explanation":"..."}
- my_answer: litera, którą Ty uważasz za prawidłową (NONE, gdy żadna nie pasuje).
- agree: true TYLKO gdy my_answer jest taka sama jak odpowiedź z bazy i nie masz żadnych zastrzeżeń (ani merytorycznych, ani co do uszkodzenia treści przez OCR). W przeciwnym razie false.
- explanation: po polsku, 2-5 zdań, bez markdown i list. Gdy agree=true: uzasadnij, dlaczego odpowiedź z bazy jest prawidłowa. Gdy agree=false: opisz swoje zastrzeżenia i którą odpowiedź uważasz za poprawną. Nie dopisuj nagłówków ani zdań w rodzaju "Prawidłowa odpowiedź to" - dodaje je aplikacja.
'''.trim();
}

/// Składa tekst dla użytkownika z odpowiedzi modelu. Nagłówek ustala kod
/// (nie model), żeby ostrzeżenie nigdy nie sprzeczało się z treścią.
String formatExplanation(String raw, String dbLetter) {
  final match = RegExp(r'\{[\s\S]*\}').firstMatch(raw);
  if (match != null) {
    try {
      final data = jsonDecode(match.group(0)!) as Map<String, dynamic>;
      final text = (data['explanation'] as String?)?.trim() ?? '';
      final mine = (data['my_answer'] as String?)?.trim().toUpperCase();
      final agree = data['agree'] == true && mine == dbLetter.toUpperCase();
      if (text.isNotEmpty) {
        return agree
            ? 'Prawidłowa odpowiedź to $dbLetter. $text'
            : '$explainWarningPrefix\n$text';
      }
    } catch (_) {}
  }
  return raw.trim();
}

String buildExplainUserPrompt({
  required QuestionRow question,
  required String? userPicked,
  required bool userWasCorrect,
}) {
  final buf = StringBuffer();
  buf.writeln('Pytanie:\n${question.pytanie.trim()}');
  buf.writeln();
  for (final opt in question.visibleOptions) {
    buf.writeln('${opt.key}: ${opt.value}');
  }
  buf.writeln();
  buf.writeln('Poprawna odpowiedź: ${question.poprawnaOdpowiedz}');
  if (userPicked != null && !userWasCorrect) {
    buf.writeln('Użytkownik wybrał: $userPicked (błędnie).');
  }
  return buf.toString();
}
