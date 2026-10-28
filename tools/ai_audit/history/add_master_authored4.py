"""Jednorazowo (2026-10-08): autorskie pytania Master — klasyfikacja akwenow manewrowych (akwen nieograniczony, plytkowodzie,
kanal, poglebiony tor wodny). Zrodla: polskie materialy szkoleniowe 'Zapas wody pod stepka - manewrowanie' (zanotowane.pl, MSM 006),
PIANC 1992 (podzial H/T), Jurdzinski (UMG) 'Informacje manewrowe statku...'."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from authored_lib import Authored  # noqa: E402

A = Authored("2026-10-08", "akweny_manewrowe")
NAW = "nawigacja"
SRC = "materiały szkoleniowe: Zapas wody pod stępką — manewrowanie (MSM 006); PIANC 1992; M. Jurdziński, UMG: informacje manewrowe statku"

A.add(NAW, "Ze względu na wpływ dna i brzegów na manewrowanie statku akweny manewrowe dzieli się na:",
      "akwen nieograniczony (otwarty), płytkowodzie, pogłębiony tor wodny i kanał",
      ["morze otwarte, morze terytorialne, wody wewnętrzne i porty",
       "akweny głębokie, średnie i płytkie, wyłącznie wg zanurzenia statku bez względu na szerokość akwenu",
       "porty, redy, kotwicowiska i farwatery"], SRC)
A.add(NAW, "Akwen nieograniczony (otwarty) w rozumieniu manewrowania statkiem to akwen:",
      "na którym dno i brzegi nie zakłócają układu fal wytwarzanych przez statek — szerokość akwenu przekracza ok. 30 szerokości statku, a głębokość jest wystarczająca (wg wzoru Taylora)",
      ["o głębokości ograniczonej tak, że wpływ dna na manewrowość występuje już przy głębokości poniżej czterech zanurzeń",
       "wąski tor ograniczony brzegami tak, że zakłóca układ fal statku i powoduje zassanie do brzegu",
       "sztuczny tor pogłębiony w płytkiej wodzie dla statków o określonym zanurzeniu"], SRC)
A.add(NAW, "Płytkowodzie to akwen, na którym:",
      "ograniczona jest głębokość: wpływ dna na manewrowość zaznacza się przy głębokości mniejszej niż ok. cztery zanurzenia, a wyraźny — przy ok. 2–2,5 zanurzenia; szerokość nie wpływa jeszcze na układ fal statku",
      ["szerokość akwenu jest mniejsza niż 10 szerokości statku, a głębokość nie ma znaczenia",
       "głębokość przekracza pięć zanurzeń, a szerokość jest większa od 30 szerokości statku",
       "wpływ dna na manewrowość występuje dopiero przy zapasie wody pod stępką większym niż jedno zanurzenie"], SRC)
A.add(NAW, "Pogłębiony tor wodny jako akwen manewrowy to:",
      "szczególny rodzaj akwenu ograniczonego, położony między płytkowodziem a kanałem — zwykle sztuczny tor pogłębiony w płytkiej wodzie dla statków o określonym zanurzeniu",
      ["naturalny, głęboki akwen otwarty, na którym brzegi nie mają wpływu na statek",
       "wyłącznie rzeka śródlądowa z nurtem o stałej prędkości",
       "dowolny akwen, na którym statek płynie z zapasem wody pod stępką większym niż 1 m"], SRC)
A.add(NAW, "Kanał jako akwen manewrowy to:",
      "tor wodny tak ograniczony brzegami, że zakłócają one układ fal wytwarzanych przez statek; wpływ szerokości trzeba poważnie uwzględniać, gdy jest ona mniejsza niż ok. 10 szerokości statku",
      ["akwen o głębokości ograniczonej, na którym szerokość nie wpływa jeszcze na fale statku",
       "akwen otwarty, na którym szerokość przekracza 30 szerokości statku",
       "wyłącznie tor wodny o głębokości większej niż pięć zanurzeń statku"], SRC)
A.add(NAW, "Według klasyfikacji PIANC woda, w której stosunek głębokości do zanurzenia statku wynosi H/T = 1,3, jest wodą:",
      "płytką (1,2 < H/T < 1,5), z wyraźnym wzrostem osiadania",
      ["głęboką (H/T > 3,0), w której dno nie wpływa na manewrowanie",
       "średnio głęboką (1,5 < H/T < 3,0), w której wpływ dna jest pomijalny",
       "bardzo płytką (H/T < 1,2), w której statek nie może zwiększać prędkości"], SRC)
A.add(NAW, "Statek idzie po akwenie, którego szerokość wynosi ponad 40 szerokości statku, a głębokość jest około 6 razy większa od zanurzenia. Jest to akwen:",
      "nieograniczony (otwarty)",
      ["płytkowodzie", "kanał", "pogłębiony tor wodny"], SRC)
A.add(NAW, "Statek idzie po szerokim akwenie (szerokość ponad 30 szerokości statku), na którym głębokość wynosi około 2 zanurzenia statku. Jest to:",
      "płytkowodzie",
      ["akwen nieograniczony (otwarty)", "kanał", "akwen, na którym wpływ dna na manewrowość nie występuje"], SRC)
A.add(NAW, "Statek wchodzi do portu torem sztucznie pogłębionym w płytkiej wodzie, z płyciznami po bokach toru i głębokością dostosowaną do jego zanurzenia. Jest to:",
      "pogłębiony tor wodny",
      ["akwen nieograniczony (otwarty)", "płytkowodzie bez ograniczeń szerokości", "morze terytorialne"], SRC)
A.add(NAW, "Statek idzie wąskim torem o stromych brzegach, którego szerokość wynosi około sześciu szerokości statku i który wyraźnie zakłóca układ fal statku. Jest to:",
      "kanał",
      ["akwen nieograniczony (otwarty)", "płytkowodzie", "otwarta redę portową"], SRC)
A.add(NAW, "Efekt kanałowy w kanale objawia się m.in.:",
      "efektem płycizny, zassaniem statku do brzegu (ściany kanału lub nabrzeża), spadkiem prędkości oraz utrudnionymi zwrotami na krzywiźnie toru",
      ["zwiększeniem prędkości statku bez zmiany obrotów śruby",
       "zmniejszeniem średnicy cyrkulacji i skróceniem drogi hamowania",
       "brakiem wpływu brzegów na statek, jeśli statek idzie środkiem toru"], SRC)
A.add(NAW, "Na płytkowodziu, w porównaniu z wodą głęboką, średnica cyrkulacji statku:",
      "rośnie (np. zapas wody pod stępką rzędu 20% zanurzenia może zwiększyć cyrkulację nawet o ok. 75%), a droga zatrzymania statku się wydłuża",
      ["maleje, bo zwiększony opór wody zmniejsza promień zwrotu",
       "pozostaje bez zmian, bo cyrkulacja zależy tylko od kąta wychylenia steru",
       "maleje, a droga zatrzymania statku skraca się"], SRC)

A.commit()
