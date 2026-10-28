/// Treść Manuala aplikacji (PL / ENG). Akapity zaczynające się od „• ” są wyświetlane jako punkty listy.
class L {
  const L(this.pl, this.en);

  final String pl;
  final String en;

  String of(bool english) => english ? en : pl;
}

class ManualSection {
  const ManualSection(this.icon, this.title, this.body);

  /// Nazwa ikony (patrz manual_screen.dart).
  final String icon;
  final L title;
  final List<L> body;
}

const manualTitle = L('Manual aplikacji', 'App manual');

const manualIntro = L(
  'Master Exam Mnemonic to aplikacja do nauki pytań testowych na egzaminy morskie (Master, Pokład, Angielski). '
      'Uczy metodą powtórek w odstępach: pytania, które znasz, wracają rzadko, a te, które sprawiają kłopot — często.',
  'Master Exam Mnemonic is an app for learning multiple-choice questions for maritime exams (Master, Deck, English). '
      'It uses spaced repetition: questions you know come back rarely, while those you struggle with come back often.',
);

const manualSections = <ManualSection>[
  ManualSection('home', L('Ekran główny', 'Home screen'), [
    L('Ekran główny to punkt startowy. Od góry:', 'The home screen is your starting point. From the top:'),
    L('• Działy do nauki — trzy pola wyboru w jednej linii: Master, Angielski, Pokład. Zaznacz działy, na których chcesz pracować (możesz kilka naraz; co najmniej jeden musi '
        'zostać zaznaczony). Statystyki, nauka, cel dzienny i prognoza dotyczą wyłącznie zaznaczonych działów. Wybór jest zapamiętywany.',
        '• Sections to study — three check boxes in one line: Master, English, Deck. Tick the sections you want to work on (several at once; at least one must stay ticked). '
            'Statistics, learning, the daily goal and the forecast refer only to the ticked sections. Your choice is remembered.'),
    L('• Opanowanie materiału — pasek pokazuje, ile pytań jest już „znanych” (patrz niżej), oraz Twój cel na dziś i prognozę.',
        '• Mastery — the bar shows how many questions are already “known” (see below), plus your goal for today and a forecast.'),
    L('• Pula (OK) — wszystkie pytania dostępne w nauce w tym dziale.', '• Pool (OK) — all questions available for learning in this section.'),
    L('• Do powtórki teraz — pytania, których termin powtórki już minął.', '• Due now — questions whose review date has already passed.'),
    L('• Zaplanowane na najbliższe 24 h — np. pytania z błędem, które wrócą jutro rano.',
        '• Scheduled for the next 24 h — e.g. questions you got wrong that will return tomorrow morning.'),
    L('• Nowe karty — pytania, których jeszcze nie widziałeś.', '• New cards — questions you have not seen yet.'),
    L('• Trudne — pytania, które często zaznaczasz błędnie.', '• Hard — questions you often answer wrongly.'),
    L('• Przełącznik pod „Start nauki”: „Wszystkie” — dotychczasowy sposób nauki (powtórki, zaległe i nowe pytania); „Same nowe” — w sesji pojawiają się wyłącznie '
        'nowe karty, czyli pytania, których nie widziałeś ani razu (bez powtórek). Gdy nowych kart zabraknie, sesja się kończy.',
        '• The switch under “Start nauki”: “Wszystkie” (All) — the usual way of learning (reviews, overdue and new questions); “Same nowe” (New only) — the session contains '
            'only new cards, i.e. questions you have never seen (no reviews). When new cards run out, the session ends.'),
    L('• Przełącznik pod „TEST”: „Normalny” — zwykły test; „Trudny” — test z większym udziałem pytań, które sprawiają Ci kłopot (patrz rozdział „TEST”).',
        '• The switch under “TEST”: “Normalny” (Normal) — an ordinary test; “Trudny” (Hard) — a test with more questions you struggle with (see the “TEST” section).'),
    L('Przyciski: „Start nauki”, „Powtórz zaplanowane (24 h)” i „TEST”. Bazę pytań wczytujesz w Ustawienia → Importuj bazę.',
        'Buttons: “Start nauki” (start learning), “Powtórz zaplanowane (24 h)” (review scheduled) and “TEST”. To load a database use Settings → Import database.'),
  ]),
  ManualSection('school', L('Nauka', 'Learning'), [
    L('Po „Start nauki” dostajesz kolejne pytania. Zaznacz odpowiedź — aplikacja od razu pokaże, czy jest poprawna (zielone) czy błędna (czerwone), '
        'i zapisze wynik. Postęp zapisuje się po każdej odpowiedzi, nic nie ginie po zamknięciu programu.',
        'After “Start nauki” you get question after question. Pick an answer — the app immediately shows whether it is right (green) or wrong (red) '
            'and saves the result. Progress is saved after every answer, nothing is lost when you close the program.'),
    L('Tryb „Same nowe” (przełącznik na ekranie głównym): pytanie, na które odpowiesz, przestaje być nowe — wróci już w zwykłym harmonogramie powtórek '
        '(błędne również; w tym trybie nie pojawiają się krótkie powtórki po 1 i 10 minutach).',
        '“New only” mode (the switch on the home screen): once you answer a question it is no longer new — it comes back later on the normal review schedule '
            '(also if you got it wrong; this mode does not show the short 1- and 10-minute repeats).'),
    L('Przyciski podczas nauki:', 'Buttons while learning:'),
    L('• Nie wiem — pokazuje poprawną odpowiedź; liczy się jak błąd, więc pytanie wróci do powtórki.',
        '• Nie wiem (I don’t know) — shows the correct answer; counts as a mistake, so the question will come back.'),
    L('• Błąd (czerwony, u góry) — ukrywa pytanie, które jest wadliwe (np. źle zapisane). Możesz je później przywrócić w Bazie Pytań.',
        '• Błąd (Error, red, top) — hides a faulty question (e.g. badly written). You can restore it later in the Question database screen.'),
    L('• Wyjaśnij — krótkie wyjaśnienie, dlaczego dana odpowiedź jest poprawna (patrz rozdział „Wyjaśnij”).',
        '• Wyjaśnij (Explain) — a short explanation of why an answer is correct (see the “Explain” section).'),
    L('• Zielona klepsydra — odkłada pytanie na 3, 6 lub 12 dni. Użyj, gdy znasz odpowiedź z doświadczenia i nie chcesz jej widzieć zbyt często.',
        '• Green hourglass — postpones the question by 3, 6 or 12 days. Use it when you know the answer from experience and do not want to see it too often.'),
    L('• Dalej — kolejne pytanie.', '• Dalej (Next) — next question.'),
    L('Skróty klawiaturowe (komputer): klawisze 1–9 wybierają kolejny wiersz odpowiedzi, Spacja = „Dalej”.',
        'Keyboard shortcuts (PC): keys 1–9 pick the corresponding answer row, Space = “Next”.'),
    L('Nagłówek „X/Y/Z”: X — odpowiedzi w tej sesji, Y (zielone) — poprawne, Z (czerwone) — błędne. '
        'Etykiety „Nowe” i „Trudne” nad pytaniem informują o rodzaju pytania.',
        'The “X/Y/Z” header: X — answers in this session, Y (green) — correct, Z (red) — wrong. '
            'The “Nowe” (New) and “Trudne” (Hard) labels above a question tell you its kind.'),
    L('Pomarańczowe tło pytania oznacza, że odpowiedź tego pytania jest niepewna: klucz jest jeszcze weryfikowany albo różni się od odpowiedzi w oficjalnym arkuszu (PDF) CMKE. '
        'Nad treścią takiego pytania (w nauce, w powtórce trudnych i w teście) pojawia się pogrubiony czerwony napis „Odpowiedź niepewna! (Jeśli znasz odp. to edytuj pytanie w Bazie Pytań w apce.)”. '
        'Oznaczenie możesz sam włączyć lub wyłączyć w Bazie Pytań, w edycji pytania (przełącznik „Niepewne”) — po wyłączeniu znika też napis. '
        'Uczy się ich normalnie, ale warto sprawdzić odpowiedź w innym źródle.',
        'An orange question background means that the answer of that question is uncertain: the key is still being verified or differs from the answer in the official CMKE sheet (PDF). '
            'Above the text of such a question (in learning, in the hard-questions review and in a test) a bold red note “Odpowiedź niepewna! (Jeśli znasz odp. to edytuj pytanie w Bazie Pytań w apce.)” (Answer uncertain! If you know the answer, edit the question in the Question database) appears. '
            'You can switch the mark on or off yourself in the Question database, in the question editor (the “Niepewne” switch) — the note disappears with it. '
            'Study them as usual, but it is worth checking the answer in another source.'),
    L('Ciemnożółte tło z napisem „UWAGA: Odp rzeczywista (prawdziwa) ≠ odpowiedź na arkuszach CMKE” (i etykietą „Odp. wg. CMKE” przy wariancie z arkusza po odpowiedzi) '
        'to starsze oznaczenie rozbieżności z arkuszem CMKE. Obecnie wszystkie takie pytania są oznaczone jako niepewne (pomarańczowo), więc to tło zwykle się nie pojawia.',
        'A dark-yellow background with the text “UWAGA: Odp rzeczywista (prawdziwa) ≠ odpowiedź na arkuszach CMKE” (and an “Odp. wg. CMKE” label on the sheet’s option after you answer) '
            'is the older mark for a difference from the CMKE sheet. All such questions are now marked uncertain (orange), so this background does not normally appear.'),
  ]),
  ManualSection('timer', L('Jak działają powtórki (FSRS)', 'How repetition works (FSRS)'), [
    L('Aplikacja używa nowoczesnego algorytmu FSRS-6. Każde pytanie ma swój termin powtórki:',
        'The app uses the modern FSRS-6 algorithm. Every question has its own review date:'),
    L('• Błąd lub „Nie wiem” — pytanie wraca w tej samej sesji po około 1 minucie, potem po 10 minutach, a następnie według harmonogramu.',
        '• A mistake or “I don’t know” — the question returns in the same session after about 1 minute, then after 10 minutes, then on schedule.'),
    L('• Poprawna odpowiedź — następna powtórka jest coraz dalej (dni, tygodnie). Odpowiedź poprawna, ale bardzo wolna (ponad 25 s) '
        'liczy się słabiej, bo mogło to być zgadywanie.',
        '• A correct answer — the next review moves further away (days, weeks). A correct but very slow answer (over 25 s) counts less, '
            'because it may have been a guess.'),
    L('• Pytania „na dni” są dostępne od 4:00 rano.', '• Day-based reviews become available at 4:00 a.m.'),
    L('• Co kilka odpowiedzi aplikacja wstawia nowe pytanie; im lepiej Ci idzie, tym częściej.',
        '• Every few answers the app inserts a new question; the better you do, the more often.'),
    L('• Pytanie jest „znane”, gdy odpowiedziałeś na nie poprawnie w 3 różne dni nauki z rzędu (błąd zeruje serię).',
        '• A question is “known” once you answered it correctly on 3 different study days in a row (a mistake resets the streak).'),
    L('• Kopie tego samego pytania w bazie (np. z różnych arkuszy) dzielą jeden harmonogram — nie wrócą tego samego dnia pod innym numerem.',
        '• Copies of the same question in the database (e.g. from different sheets) share one schedule — they will not return on the same day under another number.'),
  ]),
  ManualSection('auto_awesome', L('Wyjaśnij', 'Explain'), [
    L('Przycisk „Wyjaśnij” pojawia się po udzieleniu odpowiedzi.', 'The “Explain” button appears after you answer.'),
    L('• Większość pytań ma gotowe wyjaśnienie zapisane w bazie — działa od razu, bez internetu i bez klucza API.',
        '• Most questions have a ready explanation stored in the database — it works instantly, offline and without an API key.'),
    L('• Jeśli wyjaśnienia brakuje, a w Ustawieniach włączysz wyjaśnienia AI i wpiszesz własny klucz OpenRouter, wyjaśnienie wygeneruje model AI '
        '(wynik jest zapamiętany na przyszłość).',
        '• If an explanation is missing and you enable AI explanations in Settings and enter your own OpenRouter key, an AI model will generate it '
            '(the result is remembered for next time).'),
    L('• Nagłówek „UWAGA – ODP. W BAZIE DANYCH MOŻE BYĆ BŁĘDNA” oznacza, że wyjaśnienie podważa klucz zapisany w bazie.',
        '• A heading “WARNING – THE DATABASE ANSWER MAY BE WRONG” means the explanation questions the key stored in the database.'),
    L('• Dla pytań z rysunkiem wyjaśnienia AI są niedostępne (model nie widzi obrazka).',
        '• AI explanations are not available for questions with a picture (the model cannot see the image).'),
    L('Wyjaśnienia są pomocą w nauce, nie źródłem prawa — rozstrzygający jest klucz z oficjalnych arkuszy Urzędu Morskiego.',
        'Explanations are a study aid, not a legal source — the key from the official Maritime Office sheets is what counts.'),
  ]),
  ManualSection('assignment', L('TEST — symulacja egzaminu', 'TEST — exam simulation'), [
    L('Pomarańczowy przycisk TEST na ekranie głównym uruchamia próbny egzamin: domyślnie 105 pytań, do zaliczenia 70 poprawnych.',
        'The orange TEST button on the home screen starts a mock exam: 105 questions by default, 70 correct answers to pass.'),
    L('• Pytania pochodzą z trzech pul: Master 50% / Angielski 20% / Pokład 30% (do zmiany w Ustawieniach). W jednym teście nie powtarzają się.',
        '• Questions come from three pools: Master 50% / English 20% / Deck 30% (changeable in Settings). They do not repeat within one test.'),
    L('• Pytania z dwóch ostatnich zakończonych testów (Normalnych i Trudnych) nie wracają w kolejnym teście — kolejny test losuje wyłącznie inne pytania. '
        'Test przerwany się nie liczy. Wyjątek: gdy po takim wykluczeniu zabrakłoby pytań, aplikacja losuje bez wykluczeń.',
        '• Questions from the last two completed tests (Normal and Hard) do not return in the next test — the next test draws only other questions. '
            'An abandoned test does not count. Exception: if the exclusion would leave too few questions, the app draws without it.'),
    L('• Tryb „Trudny” (przełącznik pod przyciskiem TEST) losuje ze wszystkich trzech działów: 50% pytań spośród 200 najtrudniejszych (z największym odsetkiem błędów), '
        '30% pytań trudniejszych (z błędami), których ostatnia odpowiedź była dawniej niż 5 dni temu, oraz 20% zupełnie losowo. Pytania się nie powtarzają. '
        'Próg zaliczenia i liczba pytań są takie same jak w teście Normalnym. Pytania, których jeszcze nie widziałeś, trafiają tylko do części losowej.',
        '• The “Trudny” (Hard) mode (the switch under the TEST button) draws from all three sections: 50% of the questions from the 200 hardest ones (highest share of mistakes), '
            '30% harder questions (with mistakes) whose last answer was more than 5 days ago, and 20% completely at random. Questions never repeat. '
            'The pass mark and number of questions are the same as in the Normal test. Questions you have not seen yet can only appear in the random part.'),
    L('• W trakcie testu nie ma podpowiedzi: wybierasz odpowiedź i idziesz dalej (lub „Nie wiem”).',
        '• There are no hints during the test: you pick an answer and move on (or “I don’t know”).'),
    L('• Na końcu widzisz wynik, wynik wg pul i listę błędnych odpowiedzi z poprawnymi.',
        '• At the end you see your score, the score per pool and a list of wrong answers with the correct ones.'),
    L('• Błędne odpowiedzi z testu od razu trafiają do powtórek w swoim dziale. Poprawne nie zmieniają harmonogramu nauki.',
        '• Wrong answers from the test go straight into reviews in their section. Correct ones do not change the study schedule.'),
    L('• Przerwanie testu nie zapisuje wyniku. Ostatni wynik widać pod przyciskiem TEST, a zakończone testy — także na liście sesji w Statystykach.',
        '• Quitting a test does not save a result. The latest result is shown under the TEST button, and completed tests also appear in the session list in Statistics.'),
  ]),
  ManualSection('local_fire_department', L('Powtórka trudnych', 'Hard questions review'), [
    L('Zakładka w menu bocznym. Wybierasz 50, 100, 150 lub 200 pytań, a aplikacja losuje je spośród pytań, na które już odpowiadałeś.',
        'A tab in the side menu. You choose 50, 100, 150 or 200 questions and the app draws them from the questions you have already answered.'),
    L('• Pytania są uszeregowane od najtrudniejszych (najczęściej błędnie zaznaczanych). Szansa wylosowania maleje wraz z miejscem w rankingu '
        '(rozkład normalny): najgorsze wchodzą niemal zawsze, dalsze coraz rzadziej.',
        '• Questions are ranked from hardest (most often answered wrongly). The chance of being drawn falls with the rank '
            '(normal distribution): the worst almost always make it, the later ones less and less.'),
    L('• Przełącznik „Kolejność” pod wyborem liczby pytań: „Od najtrudniejszych” — wybrane pytania pojawiają się od najtrudniejszego do najłatwiejszego; „Losowo” (domyślnie) — w losowej kolejności. '
        'Przełącznik zmienia tylko kolejność, a nie to, które pytania zostały wybrane.',
        '• The “Kolejność” (Order) switch below the question count: “Od najtrudniejszych” (hardest first) — the chosen questions appear from the hardest to the easiest; “Losowo” (random, default) — in random order. '
            'The switch changes only the order, not which questions were chosen.'),
    L('• Większa liczba (np. 100 zamiast 50) po prostu poszerza zakres losowania o kolejne, nieco łatwiejsze pytania.',
        '• A larger number (e.g. 100 instead of 50) simply widens the range with further, slightly easier questions.'),
    L('• Powtórka działa jak zwykła nauka (te same przyciski i wyjaśnienia), a odpowiedzi wpływają na harmonogram powtórek.',
        '• The review works like normal learning (same buttons and explanations) and your answers affect the review schedule.'),
  ]),
  ManualSection('bar_chart', L('Statystyki', 'Statistics'), [
    L('Zakładka w menu bocznym, trzy karty:', 'A tab in the side menu with three tabs:'),
    L('• Ogólne — procent poprawnych odpowiedzi ze wszystkich sesji, liczba odpowiedzi i sesji oraz osobny wynik dla pytań znanych.',
        '• Overall — percentage of correct answers across all sessions, number of answers and sessions, and a separate score for known questions.'),
    L('• Sesje — wynik każdej sesji (sesja = seria odpowiedzi bez przerwy dłuższej niż 30 minut). Przełącznik „Wszystkie pytania / Tylko znane”: '
        '„znane” to pytania pokazane już wcześniej (drugie i kolejne pojawienie się) — bez pierwszych odpowiedzi na nowe pytania, '
        'które zwykle obniżają wynik.',
        '• Sessions — the result of each session (a session = a series of answers without a break longer than 30 minutes). The “All questions / Known only” switch: '
            '“known” means questions shown before (second and later appearance) — without first answers to new questions, which usually lower the score.'),
    L('   Na liście sesji są też w pełni zakończone TESTY (pomarańczowa karta: wynik, zaliczony / niezaliczony, próg). Test w trybie Trudnym ma dopisek „Wersja trudna”. '
        'Testy przerwane się nie pokazują, a przełącznik „Tylko znane” ich nie dotyczy.',
        '   The session list also contains fully completed TESTS (an orange card: score, passed / failed, pass mark). A test in Hard mode carries a “Wersja trudna” (Hard version) note. '
            'Abandoned tests are not shown, and the “Known only” switch does not apply to them.'),
    L('• Najtrudniejsze — lista 100, 200 lub 300 pytań z najgorszymi wynikami (liczba błędów / liczba odpowiedzi).',
        '• Hardest — a list of the 100, 200 or 300 questions with the worst results (mistakes / answers).'),
    L('Do statystyk wchodzą odpowiedzi z nauki i powtórek oraz błędy z TESTU (poprawne odpowiedzi w teście nie są zapisywane).',
        'Statistics include answers from learning and reviews, and mistakes from the TEST (correct answers in the test are not recorded).'),
  ]),
  ManualSection('slideshow', L('Slideshow', 'Slideshow'), [
    L('Zakładka w menu bocznym — szybkie przypomnienie trudnych i starych pytań, bez odpowiadania i bez zmian w harmonogramie nauki.',
        'A tab in the side menu — a quick refresher of hard and old questions, without answering and without changing the study schedule.'),
    L('Najpierw wybierasz trzy pule pytań (każdą można wyłączyć opcją „Brak”):',
        'First you choose three pools of questions (each can be switched off with “Brak” — None):'),
    L('• Błędne odpowiedzi z ostatnich testów — z 5, 10, 15 lub wszystkich ostatnich zakończonych testów (pytania, na które odpowiedziałeś błędnie lub „Nie wiem”). '
        'Lista błędów jest zapisywana od wersji 2.8, więc starsze testy nie mają jej w historii — ekran pokazuje, z ilu testów są dane.',
        '• Wrong answers from recent tests — from the last 5, 10, 15 or all completed tests (questions you answered wrongly or with “I don’t know”). '
            'The list of mistakes is stored since version 2.8, so older tests have none in the history — the screen shows how many tests have data.'),
    L('• Ostatnie trudne — 10, 50, 100, 150 lub 200 pytań z błędami (trudność co najmniej 0,4), od tych, na które ostatnio odpowiedziałeś błędnie.',
        '• Latest hard — 10, 50, 100, 150 or 200 questions with mistakes (difficulty of at least 0.4), starting from those you most recently answered wrongly.'),
    L('• Najstarsze pytania — 10, 50, 100, 150 lub 200 pytań, które były wyświetlone najdawniej (spośród tych, na które już odpowiadałeś).',
        '• Oldest questions — 10, 50, 100, 150 or 200 questions that were shown longest ago (among those you have already answered).'),
    L('Przełącznik „Pytania niepewne”: „Wszystkie” (domyślnie) — niepewne pytania są w pokazie, na pomarańczowym tle z napisem „Odpowiedź niepewna!” jak w nauce i w teście; '
        '„Bez niepewnych” — niepewne pytania odpadają, a ich miejsce zajmują kolejne z danej puli.',
        'The “Pytania niepewne” (Uncertain questions) switch: “Wszystkie” (All, default) — uncertain questions are in the show, on an orange background with the “Odpowiedź niepewna!” note as in learning and in tests; '
            '“Bez niepewnych” (Without uncertain) — uncertain questions are dropped and the next ones from the pool take their place.'),
    L('Pokaz to suma wybranych pul w losowej kolejności. Pytania się nie powtarzają: jeśli pytanie jest już w jednej puli (także jako kopia pod innym numerem), '
        'nie jest brane z kolejnej, a w jego miejsce wchodzi następne.',
        'The show is the sum of the chosen pools in random order. Questions never repeat: if a question is already in one pool (also as a copy under another number), '
            'it is not taken from the next one and the next candidate takes its place.'),
    L('W pokazie widzisz treść pytania, a pod nią na zielono wyłącznie prawidłową odpowiedź (bez liter A/B/C). Przyciski: „Wyjaśnij” (jak w nauce; '
        'niedostępne przy pytaniach z rysunkiem) i „Dalej” — Spacja też działa jak „Dalej”.',
        'You see the question text and, below it in green, only the correct answer (without the A/B/C letters). Buttons: “Wyjaśnij” (Explain; as in learning, '
            'unavailable for questions with a picture) and “Dalej” (Next) — Space also works as “Next”.'),
  ]),
  ManualSection('storage', L('Baza Pytań', 'Question database'), [
    L('Przeglądarka wszystkich pytań w bazie.', 'A browser of all questions in the database.'),
    L('• Filtr kategorii oraz pola „Tylko oznaczone jako Błąd” i „Tylko niepewne” (same pytania z pomarańczowym oznaczeniem niepewnej odpowiedzi); można łączyć je z wyszukiwaniem.',
        '• A category filter and the “Tylko oznaczone jako Błąd” (only questions marked Error) and “Tylko niepewne” (only uncertain questions, marked orange) checkboxes; they can be combined with the search.'),
    L('• Po dotknięciu pytania otwiera się edycja: treść pytania, warianty A–D i lista rozwijana „Poprawna odpowiedź” (tylko litery z treścią). '
        'Zapis jest możliwy, gdy pytanie ma treść, co najmniej dwa warianty, a poprawna odpowiedź wskazuje wypełniony wariant.',
        '• Tap a question to open the editor: the question text, options A–D and a “Poprawna odpowiedź” (correct answer) drop-down (only letters that have text). '
            'Saving works when the question has text, at least two options, and the correct answer points to a filled option.'),
    L('• Kategoria (dział): w edycji zaznacz jeden lub kilka działów — Master, Angielski, Pokład (co najmniej jeden). Pytanie z kilkoma działami pojawia się w nauce, w statystykach i na liście '
        'każdego z wybranych działów (w TEŚCIE nadal nie powtarza się). Dział główny pytania (liczony w rozdziale pul TESTU) zostaje, dopóki jest zaznaczony. '
        'Zmiana dotyczy tego jednego pytania — jego kopie w innych działach to osobne wpisy. Domyślnie każde pytanie ma dział, do którego należało dotąd.',
        '• Category (section): in the editor tick one or several sections — Master, Angielski (English), Pokład (Deck) (at least one). A question with several sections shows up in learning, statistics and the list '
            'of each chosen section (in a TEST it still never repeats). The question’s main section (used for the TEST pool split) stays as long as it is ticked. '
            'The change applies to this one question — its copies in other sections are separate entries. By default each question has the section it belonged to before.'),
    L('• Przełącznik „Status nauki” przywraca pytanie ukryte jako „Błąd”. Przełącznik „Niepewne” (domyślnie wyłączony) oznacza pytanie na pomarańczowo w nauce i w teście; '
        'dotyczy też kopii tego samego pytania pod innymi numerami. Jeśli zmienisz poprawną odpowiedź w pytaniu niepewnym, aplikacja zapyta, czy zmienić status na „Pewna odpowiedź” — TAK zdejmuje oznaczenie niepewne, NIE zostawia je. Pytania niepewne są podświetlone na pomarańczowo także na liście Bazy Pytań (z dopiskiem „NIEPEWNE”) i w edycji pytania.',
        '• The “Status nauki” switch restores a question hidden as “Error”. The “Niepewne” (Uncertain) switch (off by default) marks the question orange in learning and in tests; '
            'it also applies to copies of the same question under other numbers. If you change the correct answer of an uncertain question, the app asks whether to change the status to “Pewna odpowiedź” (certain answer) — YES (TAK) removes the uncertain mark, NO (NIE) keeps it. Uncertain questions are highlighted orange also in the Question database list (with a “NIEPEWNE” note) and in the editor.'),
    L('Zmiany w treści są zapisywane lokalnie na Twoim urządzeniu. Ręcznie edytowane pytanie dostaje znacznik w kolumnie weryfikacji, a jego zapisane wyjaśnienie AI '
        'przestaje pasować, jeśli zmienisz klucz lub treść — „Wyjaśnij” wygeneruje je wtedy od nowa.',
        'Changes to the text are stored locally on your device. A manually edited question gets a mark in the verification column, and its saved AI explanation '
            'stops matching if you change the key or text — “Wyjaśnij” will then generate it again.'),
  ]),
  ManualSection('settings', L('Ustawienia', 'Settings'), [
    L('• Na dole ekranu widać numer wersji aplikacji i wersję bazy pytań (np. „baza pytań 3.0”). Wersja bazy przenosi się razem z nią przy imporcie.',
        '• At the bottom of the screen you see the app version and the question database version (e.g. “baza pytań 3.0”). The database version travels with it on import.'),
    L('• Tryb ciemny — ciemny motyw aplikacji.', '• Dark mode — a dark theme for the app.'),
    L('• Losowa kolejność odpowiedzi — treści odpowiedzi mieszają się pod literami A/B/C, żebyś nie uczył się „tu zawsze A”. Domyślnie wyłączone. '
        'Wyjaśnienia dopasowują litery do wyświetlonej kolejności.',
        '• Random answer order — answer texts are shuffled under the letters A/B/C so you do not memorise “always A here”. Off by default. '
            'Explanations adjust their letters to the displayed order.'),
    L('• Docelowa retencja (80–97%, domyślnie 90%) — jak dużą część pytań chcesz pamiętać w chwili powtórki. Wyżej = częstsze powtórki, mniej zapomnianych.',
        '• Target retention (80–97%, default 90%) — what share of questions you want to remember at review time. Higher = more frequent reviews, fewer forgotten.'),
    L('• TEST — liczba pytań, próg zaliczenia oraz udział procentowy puli Master i Angielski (Pokład to reszta).',
        '• TEST — number of questions, pass mark and the percentage share of the Master and English pools (Deck is the rest).'),
    L('• Termin egzaminu — po wpisaniu daty na ekranie głównym pojawia się dzienny cel i prognoza. Materiał ma być „znany” na 3 dni przed egzaminem, '
        'a aplikacja skraca odstępy powtórek tak, żeby się to udało.',
        '• Exam date — once you enter a date, the home screen shows a daily goal and a forecast. The material should be “known” 3 days before the exam, '
            'and the app shortens review intervals to make it possible.'),
    L('• Wyjaśnienia AI — włącznik, wybór modelu i własny klucz OpenRouter. Klucz jest przechowywany tylko na Twoim urządzeniu; nie trafia do bazy ani do eksportu. '
        'Gotowe wyjaśnienia z bazy działają bez klucza.',
        '• AI explanations — a switch, model choice and your own OpenRouter key. The key is stored only on your device; it never goes into the database or an export. '
            'Ready-made explanations from the database work without a key.'),
    L('• Eksportuj bazę / Importuj bazę — patrz następny rozdział.', '• Export database / Import database — see the next section.'),
  ]),
  ManualSection('sync_alt', L('Eksport i import bazy', 'Database export and import'), [
    L('Eksport zapisuje całą bazę (pytania, statusy, postęp nauki, wyjaśnienia) do pliku — to także kopia zapasowa. Klucz API nie jest eksportowany.',
        'Export saves the whole database (questions, statuses, learning progress, explanations) to a file — it also works as a backup. The API key is not exported.'),
    L('Import po wyborze pliku pyta o tryb:', 'After choosing a file, import asks for a mode:'),
    L('• A — pełny import z nadpisaniem: zastępuje całą bazę (wcześniej powstaje kopia bieżącej).',
        '• A — full import with overwrite: replaces the whole database (a copy of the current one is made first).'),
    L('• B — tylko statusy (OK / Błąd) pytań, które już masz.', '• B — only the statuses (OK / Error) of questions you already have.'),
    L('• C — dodanie pytań, których jeszcze nie masz.', '• C — adds questions you do not have yet.'),
    L('• D — aktualizacja z zachowaniem postępu (domyślny): dodaje nowe pytania, poprawia treść i klucze istniejących, dołącza wyjaśnienia, '
        'a Twoja nauka, historia odpowiedzi i oznaczenia „Błąd” zostają bez zmian. Tak aktualizuj bazę po poprawkach.',
        '• D — update keeping progress (default): adds new questions, fixes the text and keys of existing ones, attaches explanations, '
            'while your learning, answer history and “Error” marks stay untouched. Use this to update the database after corrections.'),
    L('Przed pełnym importem zawsze zostaje kopia zapasowa bieżącej bazy.', 'A backup of the current database is always kept before a full import.'),
  ]),
  ManualSection('lightbulb', L('Wskazówki', 'Tips'), [
    L('• Ucz się codziennie po trochu — algorytm najlepiej działa przy regularności.', '• Study a little every day — the algorithm works best with regularity.'),
    L('• Zacznij od zaległych („Do powtórki teraz”), nowe pytania przyjdą same.', '• Start with the overdue ones (“Due now”); new questions will come on their own.'),
    L('• Pytania z rysunkiem (np. flagi, światła statków) pokazują obrazek nad treścią; dotknij go, aby powiększyć.',
        '• Questions with a picture (e.g. flags, ship lights) show the image above the text; tap it to enlarge.'),
    L('• Gdy widzisz błąd w pytaniu, użyj „Błąd” lub popraw je w Bazie Pytań.', '• If you see a mistake in a question, use “Error” or fix it in the Question database screen.'),
    L('• Wersja przenośna na PC trzyma dane w folderze user_data obok programu; usunięcie tego folderu zeruje postęp nauki.',
        '• The portable PC version keeps its data in the user_data folder next to the program; deleting that folder resets your progress.'),
    L('• Windows 8.1: w folderze programu musi leżeć plik sqlite3.dll (jest w paczce).', '• Windows 8.1: the sqlite3.dll file must stay in the program folder (it is in the package).'),
  ]),
  ManualSection('mail_outline', L('Kontakt', 'Contact'), [
    L('Pytania, uwagi i zgłoszenia błędów w pytaniach: menu boczne → Kontakt (Lukasz, acardo1985@gmail.com).',
        'Questions, remarks and reports of errors in questions: side menu → Contact (Lukasz, acardo1985@gmail.com).'),
  ]),
];
