"""Jednorazowo (2026-10-07): autorskie pytania Master (zestaw 2: FAL, laytime, akredytywa, IALA, COLREG, UNCLOS, MARPOL,
sygnaly mglowe, znaki dzienne, OWS, obszary specjalne). Warianty mieszane (seed), ai_verified = ai_authored:<data>.
Kopie *.bak_authored2_* (seed w data/). Zapis do review/Nowe_pytania_Master_2026-10-07.md."""
import collections
import random
import shutil
import sqlite3
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
STAMP = "2026-10-07"
DBS = {"app": Path.home() / "Documents" / "memonic_app.db", "seed": ROOT / "app" / "assets" / "db" / "memonic_app_seed.db"}
KAT = "Kapitan żeglugi wielkiej"
ZS, BN, PM, BS, NAW, URZ = ("zarządzanie statkiem", "bezpieczeństwo nawigacji", "prawo morskie",
                            "bezpieczeństwo statku", "nawigacja", "urządzenia nawigacyjne")

Q = []


def add(tem, q, correct, wrong, src, image=None):
    assert len(wrong) == 3, q
    Q.append({"tem": tem, "q": q, "opts": [correct] + wrong, "src": src, "image": image})


# ---------------------------------------------------------------- handel, czartery, dokumenty portowe
add(ZS, "Laytime w umowie czarterowej to:",
    "uzgodniony w czarterze czas, w którym czarterujący może załadować lub wyładować statek bez dodatkowej opłaty (zwykle liczony od przyjęcia Notice of Readiness)",
    ["czas żeglugi statku między portem załadunku a portem wyładunku",
     "kara umowna płacona armatorowi za przekroczenie czasu przeładunku",
     "okres ważności Notice of Readiness po jego złożeniu w porcie"],
    "GENCON 94 / formularze BIMCO (laytime, demurrage, despatch)")
add(ZS, "Akredytywa (Letter of Credit) w handlu morskim to:",
    "zobowiązanie banku, na zlecenie kupującego, do zapłaty sprzedawcy po przedstawieniu dokumentów (m.in. konosamentu) zgodnych z warunkami akredytywy",
    ["gwarancja przewoźnika, że ładunek zostanie dostarczony w stanie nieuszkodzonym",
     "polisa ubezpieczeniowa ładunku wystawiana przez ubezpieczyciela na rzecz odbiorcy",
     "dokument celny uprawniający do odprawy ładunku w porcie przeznaczenia"],
    "UCP 600 (Uniform Customs and Practice for Documentary Credits)")
FAL_SRC = "IMO Convention on Facilitation of International Maritime Traffic (FAL), Standardized forms"
FAL = {
    1: ("General Declaration (deklaracja ogólna) — podstawowe dane o statku, rejsie, załodze i ładunku przedstawiane władzom portu",
        "wykaz ładunku przewożonego na statku"),
    2: ("Cargo Declaration (deklaracja ładunku) — wykaz ładunku przewożonego na statku",
        "deklaracja ogólna statku"),
    3: ("Ship's Stores Declaration (deklaracja zapasów statkowych) — zapasy znajdujące się na statku (np. żywność, napoje, wyroby tytoniowe, paliwo)",
        "wykaz rzeczy osobistych załogi"),
    4: ("Crew's Effects Declaration (deklaracja rzeczy osobistych załogi)",
        "deklaracja zapasów statkowych"),
    5: ("Crew List (lista załogi)", "lista pasażerów"),
    6: ("Passenger List (lista pasażerów)", "lista załogi"),
    7: ("Dangerous Goods (wykaz/manifest ładunków niebezpiecznych)", "deklaracja ładunku w ujęciu ogólnym, bez ładunków niebezpiecznych"),
}
ALL_FAL = [FAL[i][0] for i in range(1, 8)]
for n in range(1, 8):
    wrong = [x for k, x in zip(range(1, 8), ALL_FAL) if k != n]
    random.Random(n).shuffle(wrong)
    add(ZS, f"Formularz FAL {n} (Konwencja FAL IMO) to:", FAL[n][0], wrong[:3], FAL_SRC)
add(ZS, "Dokumenty przedstawiane władzom portu przy zawinięciu statku (port arrival documents) obejmują zwykle:",
    "formularze FAL (m.in. General Declaration, Cargo Declaration, Ship's Stores Declaration, Crew List), Maritime Declaration of Health oraz informacje wymagane przez ISPS przed wejściem do portu",
    ["wyłącznie świadectwo klasy i polisę ubezpieczeniową statku",
     "tylko konosamenty dotyczące ładunku przewożonego na statku",
     "dziennik pokładowy i dziennik maszynowy za ostatnie 12 miesięcy"],
    "Konwencja FAL (FAL 1–7), SOLAS XI-2 reg. 9 (ISPS), IHR - Maritime Declaration of Health")

# ---------------------------------------------------------------- IALA
IALA_SRC = "IALA Maritime Buoyage System (system A), IALA O-130"
M = {
    "N": ("znak kardynalny północny: czarny nad żółtym, znak szczytowy – dwa stożki wierzchołkami do góry; bezpieczna woda leży na północ od znaku, światło białe Q lub VQ (błyski ciągłe)", "iala_polnocny.png"),
    "E": ("znak kardynalny wschodni: czarny z żółtym pasem, znak szczytowy – dwa stożki podstawami do siebie; bezpieczna woda leży na wschód od znaku, światło białe Q(3) 10 s lub VQ(3) 5 s", "iala_wschodni.png"),
    "S": ("znak kardynalny południowy: żółty nad czarnym, znak szczytowy – dwa stożki wierzchołkami w dół; bezpieczna woda leży na południe od znaku, światło białe Q(6)+LFl 15 s lub VQ(6)+LFl 10 s", "iala_poludniowy.png"),
    "W": ("znak kardynalny zachodni: żółty z czarnym pasem, znak szczytowy – dwa stożki wierzchołkami do siebie; bezpieczna woda leży na zachód od znaku, światło białe Q(9) 15 s lub VQ(9) 10 s", "iala_zachodni.png"),
    "SP": ("znak specjalny: cały żółty, znak szczytowy – żółty krzyż X; oznacza obszar lub obiekt specjalny (np. strefa ćwiczeń, kable, rurociągi), światło żółte o dowolnym rytmie niekolidującym z innymi znakami", "iala_specjalny.png"),
    "SW": ("znak bezpiecznej wody (środka toru): czerwono-białe pionowe pasy, znak szczytowy – czerwona kula; woda żeglowna dookoła znaku, światło białe Iso, Oc, LFl 10 s lub Mo(A)", "iala_bezpiecznej_wody.png"),
}
for key in ("N", "E", "S", "W", "SP", "SW"):
    wrong = [M[k][0] for k in M if k != key]
    random.Random(key).shuffle(wrong)
    add(BN, "Znak nawigacyjny przedstawiony na rysunku (kształt, kolory i znak szczytowy) to:", M[key][0], wrong[:3], IALA_SRC, M[key][1])

# ---------------------------------------------------------------- COLREG
CR = "COLREG 1972, "
add(BN, "Międzynarodowe Prawidła Zapobiegania Zderzeniom na Morzu (COLREG 1972) określają:",
    "zasady drogi (ustępowanie drogi), światła i znaki, sygnały dźwiękowe i świetlne oraz postępowanie statków w celu zapobiegania zderzeniom na morzu i wodach z nim połączonych dostępnych dla statków morskich",
    ["wyłącznie zasady postępowania i odpowiedzialności cywilnej po zderzeniu statków",
     "wymagania konstrukcyjne kadłuba oraz wyposażenia ratunkowego statku",
     "zasady ochrony środowiska morskiego przed zanieczyszczeniem przez statki"],
    CR + "Prawidło 1")
add(BN, "Zgodnie z Prawidłem 2 COLREG (odpowiedzialność) stosowanie Prawideł:",
    "nie zwalnia statku, jego armatora, kapitana ani załogi od skutków zaniedbania przestrzegania Prawideł lub środków ostrożności wymaganych zwykłą praktyką morską",
    ["zwalnia kapitana od odpowiedzialności, jeśli jego statek miał pierwszeństwo drogi",
     "dotyczy wyłącznie statków o pojemności brutto powyżej 500 GT",
     "zwalnia armatora z odpowiedzialności, gdy kapitan działał zgodnie z Prawidłami"],
    CR + "Prawidło 2")
add(BN, "Statek nieodpowiadający za swoje ruchy (NUC) wg Prawidła 3 COLREG to statek, który:",
    "z powodu jakiejś wyjątkowej okoliczności nie jest w stanie manewrować zgodnie z Prawidłami i dlatego nie może ustąpić drogi innemu statkowi",
    ["z powodu charakteru wykonywanej pracy ma ograniczoną zdolność manewrowania zgodnie z Prawidłami",
     "z powodu zanurzenia w stosunku do głębokości wody jest ograniczony w możliwości zbaczania z kursu",
     "pracuje sieciami lub linami połowowymi ograniczającymi jego zdolność manewrową"],
    CR + "Prawidło 3(f)")
add(BN, "Statek o ograniczonej zdolności manewrowej (RAM) wg Prawidła 3 COLREG to statek, który:",
    "z powodu charakteru wykonywanej pracy (np. układanie kabli, pogłębianie, tankowanie w drodze) ma ograniczoną zdolność manewrowania zgodnie z Prawidłami i dlatego nie może ustąpić drogi innemu statkowi",
    ["z powodu jakiejś wyjątkowej okoliczności nie jest w stanie manewrować zgodnie z Prawidłami",
     "idzie pod żaglami z jednoczesnym użyciem napędu mechanicznego",
     "z powodu zanurzenia w stosunku do dostępnej głębokości i szerokości wody jest ograniczony w możliwości zbaczania z kursu"],
    CR + "Prawidło 3(g)")
add(BN, "Statek ograniczony swoim zanurzeniem (CBD) wg Prawidła 3 COLREG to:",
    "statek o napędzie mechanicznym, który z powodu zanurzenia w stosunku do dostępnej głębokości i szerokości wody jest poważnie ograniczony w możliwości zbaczania ze swego kursu",
    ["statek, który z powodu wyjątkowej okoliczności nie może manewrować zgodnie z Prawidłami",
     "każdy statek o zanurzeniu większym niż 7 m, niezależnie od głębokości akwenu",
     "statek zajęty połowem trałem, którego sieć zahaczyła o przeszkodę"],
    CR + "Prawidło 3(h)")
add(BN, "Zgodnie z Prawidłem 5 COLREG każdy statek musi:",
    "przez cały czas prowadzić właściwą obserwację wzrokową i słuchową oraz wszelkimi dostępnymi środkami odpowiednimi do panujących warunków, aby w pełni ocenić sytuację i ryzyko zderzenia",
    ["prowadzić obserwację wyłącznie przy ograniczonej widzialności i w nocy",
     "polegać głównie na radarze, a obserwację wzrokową prowadzić tylko w porcie",
     "prowadzić obserwację tylko w obszarach o dużym natężeniu ruchu"],
    CR + "Prawidło 5")
add(BN, "Prędkość bezpieczna (Prawidło 6 COLREG) to prędkość, która pozwala:",
    "podjąć właściwe i skuteczne działanie w celu uniknięcia zderzenia oraz zatrzymać statek w odległości odpowiedniej do panujących warunków i okoliczności",
    ["osiągnąć najkrótszy czas przejścia trasy przy dopuszczalnym zużyciu paliwa",
     "utrzymać prędkość maksymalną, o ile nie występuje mgła",
     "utrzymać prędkość nie większą niż 10 węzłów w każdych warunkach"],
    CR + "Prawidło 6")
add(BN, "Zgodnie z Prawidłem 7 COLREG, jeżeli kompasowy namiar na zbliżający się statek nie zmienia się w sposób dostrzegalny, to:",
    "należy uznać, że istnieje ryzyko zderzenia",
    ["należy uznać, że ryzyka zderzenia nie ma, jeżeli statek jest mały",
     "ryzyko zderzenia istnieje tylko wtedy, gdy zmniejsza się prędkość drugiego statku",
     "należy zwiększyć prędkość i utrzymać kurs bez dodatkowych działań"],
    CR + "Prawidło 7")
add(BN, "Działanie w celu uniknięcia zderzenia (Prawidło 8 COLREG) powinno być, jeśli okoliczności na to pozwalają:",
    "zdecydowane, podjęte w dostatecznym czasie, a zmiany kursu lub prędkości na tyle duże, by były szybko zauważone przez inny statek; należy unikać serii małych zmian",
    ["wykonywane w serii małych zmian kursu i prędkości, aby nie zaskoczyć drugiego statku",
     "podejmowane dopiero wtedy, gdy odległość między statkami spadnie poniżej 1 mili morskiej",
     "ograniczone wyłącznie do zmiany prędkości, bez zmiany kursu"],
    CR + "Prawidło 8")
add(BN, "Statek idący wąskim torem wodnym lub farwaterem (Prawidło 9 COLREG) powinien:",
    "trzymać się możliwie blisko zewnętrznej granicy toru wodnego znajdującej się po jego prawej burcie, o ile jest to bezpieczne i wykonalne",
    ["trzymać się środka toru wodnego niezależnie od kierunku ruchu",
     "trzymać się lewej strony toru, aby widzieć statki zbliżające się z przeciwka",
     "przecinać tor wodny pod ostrym kątem w celu skrócenia czasu przejścia"],
    CR + "Prawidło 9")
add(BN, "Statek w systemie rozgraniczenia ruchu (TSS) zgodnie z Prawidłem 10 COLREG powinien:",
    "iść w odpowiednim pasie ruchu w ogólnym kierunku ruchu dla tego pasa, w miarę możliwości trzymać się z dala od linii lub strefy rozgraniczającej oraz zwykle wchodzić i opuszczać pas na jego końcach",
    ["iść pasem ruchu w kierunku przeciwnym do ogólnego, aby uniknąć zderzenia",
     "iść wzdłuż strefy rozgraniczenia ruchu i zawsze wchodzić do pasa od jego boku",
     "zatrzymać się na kotwicy w strefie rozgraniczenia, jeśli ruch jest duży"],
    CR + "Prawidło 10")
add(BN, "Dwa statki żaglowe zbliżają się do siebie tak, że ryzyko zderzenia istnieje, a wiatr wieje z różnych burt. Zgodnie z Prawidłem 12 COLREG ustępuje drogi statek, który:",
    "ma wiatr z lewej burty",
    ["ma wiatr z prawej burty",
     "znajduje się po zawietrznej stronie drugiego statku",
     "jest mniejszy, niezależnie od kierunku wiatru"],
    CR + "Prawidło 12")
add(BN, "Statek wyprzedzający (Prawidło 13 COLREG):",
    "ustępuje drogi statkowi wyprzedzanemu bez względu na rodzaje statków i pozostaje do tego obowiązany aż do ostatecznego minięcia",
    ["ma pierwszeństwo drogi, jeśli jest większy lub szybszy od wyprzedzanego",
     "ustępuje drogi tylko wtedy, gdy wyprzedzany statek jest statkiem żaglowym",
     "przestaje być statkiem wyprzedzającym, gdy zmieni kurs o 10°"],
    CR + "Prawidło 13")
add(BN, "Dwa statki o napędzie mechanicznym idą na przeciwnych lub prawie przeciwnych kursach i istnieje ryzyko zderzenia (Prawidło 14 COLREG). Każdy z nich powinien:",
    "zmienić kurs w prawo, aby minąć się lewymi burtami",
    ["zmienić kurs w lewo, aby minąć się prawymi burtami",
     "zmniejszyć prędkość i utrzymać kurs, jeśli jest większy",
     "ustąpić drogi, jeśli ma drugi statek po lewej burcie"],
    CR + "Prawidło 14")
add(BN, "Dwa statki o napędzie mechanicznym zbliżają się do siebie na kursach przecinających się i istnieje ryzyko zderzenia (Prawidło 15 COLREG). Ustępuje drogi statek, który:",
    "ma drugi statek po swojej prawej burcie, i powinien unikać przecinania jego kursu przed dziobem, jeśli okoliczności na to pozwalają",
    ["ma drugi statek po swojej lewej burcie",
     "jest mniejszy, niezależnie od względnego położenia statków",
     "idzie wolniej, niezależnie od względnego położenia statków"],
    CR + "Prawidło 15")
add(BN, "Statek zobowiązany do ustąpienia drogi (give-way, Prawidło 16 COLREG) powinien:",
    "w miarę możliwości podjąć jak najwcześniej działanie zdecydowane i wyraźne, aby ustąpić drogi",
    ["utrzymywać kurs i prędkość do chwili, gdy drugi statek wykona manewr",
     "podjąć działanie dopiero w ostatniej chwili, aby nie wprowadzić drugiego statku w błąd",
     "zawsze zmniejszyć prędkość do zera"],
    CR + "Prawidło 16")
add(BN, "Statek uprzywilejowany (stand-on, Prawidło 17 COLREG):",
    "powinien utrzymywać kurs i prędkość, ale może działać samodzielnie, gdy stwierdzi, że statek ustępujący nie podejmuje właściwego działania, i musi manewrować, gdy zderzenia nie da się uniknąć manewrem samego statku ustępującego",
    ["powinien niezwłocznie zmienić kurs w lewo, aby ułatwić drugiemu statkowi manewr",
     "powinien zatrzymać maszyny i czekać na sygnał drugiego statku",
     "traci wszelkie obowiązki, jeśli drugi statek jest statkiem o napędzie mechanicznym"],
    CR + "Prawidło 17")
add(BN, "Zgodnie z Prawidłem 18 COLREG statek o napędzie mechanicznym w drodze powinien ustępować drogi:",
    "statkowi nieodpowiadającemu za swoje ruchy, statkowi o ograniczonej zdolności manewrowej, statkowi zajętemu połowem oraz statkowi żaglowemu",
    ["wyłącznie statkowi nieodpowiadającemu za swoje ruchy",
     "wyłącznie statkom żaglowym i statkom mniejszym od siebie",
     "każdemu statkowi o mniejszej długości"],
    CR + "Prawidło 18")
add(BN, "Statek wykrywający wyłącznie radarem statek przed trawersem, gdy ryzyko zderzenia istnieje, powinien (Prawidło 19 COLREG) w miarę możliwości unikać:",
    "zmiany kursu w lewo (z wyjątkiem wyprzedzania tego statku)",
    ["zmiany kursu w prawo",
     "zmniejszenia prędkości",
     "włączenia świateł pozycyjnych i sygnałów mgłowych"],
    CR + "Prawidło 19(d)")
add(BN, "Statek o napędzie mechanicznym w drodze, który zmienia kurs w lewo (Prawidło 34 COLREG), daje sygnał dźwiękowy:",
    "dwa krótkie dźwięki",
    ["jeden krótki dźwięk", "trzy krótkie dźwięki", "jeden długi dźwięk"],
    CR + "Prawidło 34(a)")
add(BN, "Pięć krótkich i szybko następujących po sobie dźwięków gwizdka statku (Prawidło 34 COLREG) oznacza:",
    "wątpliwość co do zamiarów drugiego statku lub brak pewności, że podejmuje on dostateczne działanie w celu uniknięcia zderzenia (sygnał ostrzegawczy)",
    ["zmieniam kurs w prawo", "moje maszyny pracują wstecz", "pragnę Cię wyprzedzić z prawej burty"],
    CR + "Prawidło 34(d)")

# ---------------------------------------------------------------- UNCLOS
UN = "UNCLOS 1982, "
add(PM, "Wyłączna strefa ekonomiczna (EEZ) wg Konwencji o prawie morza (UNCLOS) to:",
    "obszar poza morzem terytorialnym i do niego przylegający, sięgający do 200 mil morskich od linii podstawowych, w którym państwo nadbrzeżne ma prawa suwerenne do zasobów naturalnych, a inne państwa korzystają ze swobody żeglugi i przelotu",
    ["obszar sięgający do 12 mil morskich od linii podstawowych, w którym państwo nadbrzeżne sprawuje pełną suwerenność",
     "obszar sięgający do 24 mil morskich od linii podstawowych, w którym państwo może wykonywać kontrolę celną i sanitarną",
     "obszar morza otwartego poza jurysdykcją jakiegokolwiek państwa, sięgający do 350 mil morskich"],
    UN + "art. 55–57")
add(PM, "Morze terytorialne wg Konwencji o prawie morza (UNCLOS) to:",
    "pas morza przylegający do wybrzeża, o szerokości do 12 mil morskich od linii podstawowych, w którym państwo nadbrzeżne sprawuje suwerenność z zachowaniem prawa nieszkodliwego przepływu",
    ["pas morza o szerokości do 200 mil morskich z prawami suwerennymi do zasobów naturalnych",
     "pas morza o szerokości do 24 mil morskich, w którym państwo sprawuje wyłącznie kontrolę celną i sanitarną",
     "pas morza o szerokości do 3 mil morskich, w którym obce statki nie mają prawa przepływu"],
    UN + "art. 2–3, 17")
add(PM, "Strefa przyległa wg Konwencji o prawie morza (UNCLOS) to:",
    "strefa przylegająca do morza terytorialnego, sięgająca do 24 mil morskich od linii podstawowych, w której państwo nadbrzeżne może sprawować kontrolę niezbędną do zapobiegania naruszeniom przepisów celnych, fiskalnych, imigracyjnych i sanitarnych",
    ["strefa do 12 mil morskich, w której państwo sprawuje pełną suwerenność jak na lądzie",
     "strefa do 200 mil morskich z wyłącznym prawem do zasobów żywych i nieożywionych",
     "strefa morza pełnego, w której obowiązuje wyłącznie prawo bandery statku"],
    UN + "art. 33")

# ---------------------------------------------------------------- meteorologia, żyrokompas
add(NAW, "Front zokludowany (okluzji) powstaje, gdy:",
    "front chłodny doganiający front ciepły zamyka sektor ciepły i wypiera ciepłe powietrze ku górze",
    ["chłodna i ciepła masa powietrza pozostają w miejscu, a front prawie się nie przemieszcza",
     "ciepłe powietrze powoli wypiera zimne i wślizguje się nad nie na całej długości frontu",
     "chłodne powietrze napływa znad lądu na ciepłe morze w ciągu dnia i powoduje bryzę"],
    "Meteorologia morska (The Admiralty Manual of Seamanship / Marine Observer's Handbook)")
add(URZ, "Jakich poprawek wymaga żyrokompas?",
    "poprawki żyrokompasu (określanej okresowo względem namiaru ciała niebieskiego lub znaku) oraz uwzględnienia błędów: prędkościowego (zależnego od kursu, prędkości statku i szerokości geograficznej) i balistycznego (po zmianie prędkości lub kursu)",
    ["poprawki dewiacji magnetycznej i zmiany zboczenia magnetycznego w danym rejonie",
     "wyłącznie poprawki na rosnące zanurzenie statku i trym",
     "żadnych – żyrokompas wskazuje zawsze kierunek prawdziwy bez błędów"],
    "IMO A.424(XI) – Performance standards for gyro-compasses; instrukcje żyrokompasów (Anschütz, Sperry)")

# ---------------------------------------------------------------- MARPOL załączniki
MP = "MARPOL 73/78, Załącznik "
ANN = {
    "I": "zapobiegania zanieczyszczeniu olejami (ropa, paliwa, mieszaniny olejowe, wody zęzowe)",
    "II": "kontroli zanieczyszczenia szkodliwymi substancjami ciekłymi przewożonymi luzem (NLS)",
    "III": "zapobiegania zanieczyszczeniu substancjami szkodliwymi przewożonymi drogą morską w formie przesyłek (opakowania, kontenery, cysterny przenośne)",
    "IV": "zapobiegania zanieczyszczeniu ściekami ze statków",
    "V": "zapobiegania zanieczyszczeniu śmieciami ze statków",
    "VI": "zapobiegania zanieczyszczeniu powietrza przez statki (emisje SOx, NOx, substancje zubożające warstwę ozonową, efektywność energetyczna)",
}
for r, txt in ANN.items():
    wrong = [v for k, v in ANN.items() if k != r]
    random.Random("annex" + r).shuffle(wrong)
    add(BS, f"Załącznik {r} do Konwencji MARPOL dotyczy:", txt, wrong[:3], MP + r)

# ---------------------------------------------------------------- sygnały mgłowe (Prawidło 35)
FOG = CR + "Prawidło 35"
ONE_LONG_TWO_SHORT = "jeden dźwięk długi i dwa krótkie, nadawane w odstępach nie dłuższych niż 2 minuty"
add(BN, "Statek o napędzie mechanicznym w drodze, posuwający się po wodzie, przy ograniczonej widzialności podaje sygnał mgłowy:",
    "jeden dźwięk długi w odstępach nie dłuższych niż 2 minuty",
    ["dwa dźwięki długie w odstępach nie dłuższych niż 2 minuty",
     ONE_LONG_TWO_SHORT, "szybkie bicie w dzwon przez około 5 sekund co minutę"], FOG + "(a)")
add(BN, "Statek o napędzie mechanicznym w drodze, ale zatrzymany i niemający prędkości względem wody, podaje przy ograniczonej widzialności sygnał mgłowy:",
    "dwa dźwięki długie z przerwą około 2 sekund między nimi, w odstępach nie dłuższych niż 2 minuty",
    ["jeden dźwięk długi w odstępach nie dłuższych niż 2 minuty", ONE_LONG_TWO_SHORT, "trzy oddzielne uderzenia w dzwon co minutę"],
    FOG + "(b)")
for name in ("statek nieodpowiadający za swoje ruchy (NUC)", "statek o ograniczonej zdolności manewrowej (RAM)",
             "statek ograniczony swoim zanurzeniem (CBD)", "statek żaglowy w drodze", "statek zajęty połowem w drodze",
             "statek holujący lub pchający inny statek"):
    add(BN, f"Sygnał mgłowy podawany przez: {name} przy ograniczonej widzialności to:",
        ONE_LONG_TWO_SHORT,
        ["jeden dźwięk długi w odstępach nie dłuższych niż 2 minuty",
         "dwa dźwięki długie z przerwą około 2 sekund między nimi",
         "szybkie bicie w dzwon przez około 5 sekund co minutę"],
        FOG + "(c)")
add(BN, "Statek na kotwicy przy ograniczonej widzialności podaje sygnał:",
    "szybkie bicie w dzwon przez około 5 sekund w odstępach nie dłuższych niż 1 minuta (statek ≥ 100 m dodatkowo uderza w gong na rufie)",
    ["jeden dźwięk długi w odstępach nie dłuższych niż 2 minuty", ONE_LONG_TWO_SHORT,
     "dwa dźwięki długie z przerwą około 2 sekund między nimi"], FOG + "(g)")
add(BN, "Statek na mieliźnie przy ograniczonej widzialności podaje sygnał:",
    "sygnał jak statek na kotwicy (szybkie bicie w dzwon), poprzedzony i zakończony trzema oddzielnymi uderzeniami w dzwon",
    ["jeden dźwięk długi i dwa krótkie co 2 minuty", "wyłącznie dwa dźwięki długie co 2 minuty",
     "trzy dźwięki krótkie co minutę"], FOG + "(h)")
add(BN, "Ostatni statek holowany (jeśli jest obsadzony), przy ograniczonej widzialności, podaje sygnał mgłowy:",
    "jeden dźwięk długi i trzy krótkie, w odstępach nie dłuższych niż 2 minuty, jeśli to możliwe zaraz po sygnale statku holującego",
    ["jeden dźwięk długi w odstępach nie dłuższych niż 2 minuty",
     "dwa dźwięki długie z przerwą około 2 sekund między nimi",
     "szybkie bicie w dzwon przez około 5 sekund co minutę"], FOG + "(e)")
add(BN, "Statek pilotowy w służbie przy ograniczonej widzialności może dodatkowo podawać sygnał rozpoznawczy:",
    "cztery krótkie dźwięki",
    ["jeden dźwięk długi i trzy krótkie", "pięć krótkich dźwięków", "dwa dźwięki długie"], FOG + "(j)")
add(BN, "Statek o długości poniżej 12 m przy ograniczonej widzialności:",
    "nie musi podawać sygnałów z Prawidła 35, ale jeśli ich nie podaje, powinien podawać inny skuteczny sygnał dźwiękowy w odstępach nie dłuższych niż 2 minuty",
    ["nie ma obowiązku podawania żadnych sygnałów dźwiękowych",
     "musi podawać identyczne sygnały jak statek o długości powyżej 50 m",
     "podaje wyłącznie sygnały świetlne"], FOG + "(i)")

# ---------------------------------------------------------------- znaki dzienne (Prawidła 27, 28, 30, 24)
DAY = CR + "Prawidła 24, 26, 27, 30"
stem = "Statek pokazuje w dzień znak dzienny widoczny na rysunku. Jest to:"
DS = {
    "anchor": ("statek na kotwicy (jedna kula z przodu, w najlepiej widocznym miejscu)", "dzienny_kotwica.png"),
    "nuc": ("statek nieodpowiadający za swoje ruchy (dwie kule w pionie)", "dzienny_nuc.png"),
    "aground": ("statek na mieliźnie (trzy kule w pionie)", "dzienny_na_mieliznie.png"),
    "ram": ("statek o ograniczonej zdolności manewrowej (kula – romb – kula w pionie)", "dzienny_ram.png"),
    "cbd": ("statek ograniczony swoim zanurzeniem (cylinder)", "dzienny_cbd.png"),
    "sail": ("statek żaglowy idący jednocześnie z użyciem napędu mechanicznego (stożek wierzchołkiem w dół)", "dzienny_zagl_silnik.png"),
    "fish": ("statek zajęty połowem (dwa stożki zwrócone wierzchołkami do siebie)", "dzienny_rybacki.png"),
    "tow": ("statek holujący lub holowany, gdy długość holu przekracza 200 m (romb)", "dzienny_holowanie.png"),
}
for key in DS:
    wrong = [DS[k][0] for k in DS if k != key]
    random.Random("day" + key).shuffle(wrong)
    add(BN, stem, DS[key][0], wrong[:3], DAY, DS[key][1])

# ---------------------------------------------------------------- OWS i obszary specjalne
add(BS, "Zgodnie z Załącznikiem I MARPOL (reg. 14) separator wód zęzowych (oil filtering equipment) musi zapewniać, że mieszanina zrzucana za burtę ma zawartość oleju nie większą niż:",
    "15 ppm (15 części na milion)",
    ["5 ppm", "50 ppm", "100 ppm"], MP + "I, reg. 14; MEPC.107(49)")
add(BS, "Statki o pojemności brutto 400 GT i większej, zgodnie z Załącznikiem I MARPOL (reg. 14), muszą być wyposażone w:",
    "urządzenie do filtracji oleju (separator wód zęzowych 15 ppm) oraz zbiornik na pozostałości olejowe",
    ["wyłącznie zbiornik na wody zęzowe bez urządzenia do filtracji",
     "instalację do spalania wód zęzowych w kotle głównym i brak innych wymagań",
     "tylko ręczną pompę zęzową z zaworem zamykanym kapitańskim kluczem"],
    MP + "I, reg. 12, 14")
add(BS, "Statek o pojemności brutto 10 000 GT i większej musi mieć w systemie separatora wód zęzowych (Załącznik I MARPOL, reg. 14), poza filtracją do 15 ppm:",
    "miernik zawartości oleju z alarmem informującym, że poziom 15 ppm nie może być utrzymany, oraz urządzenie automatycznie zatrzymujące zrzut po przekroczeniu 15 ppm",
    ["wyłącznie ręczny zawór, który załoga zamyka po wykryciu zanieczyszczenia",
     "dodatkowy zbiornik na całą ilość wód zęzowych bez możliwości zrzutu za burtę",
     "kamerę do rejestracji koloru wody za burtą"],
    MP + "I, reg. 14; MEPC.107(49)")
add(BS, "Obszar specjalny (special area) w rozumieniu MARPOL to obszar morski, w którym:",
    "z uwagi na warunki oceanograficzne i ekologiczne oraz specyfikę ruchu przyjęto obowiązkowe, bardziej rygorystyczne metody zapobiegania zanieczyszczeniu z określonego załącznika",
    ["wolno wyłącznie statkom pod banderą państwa nadbrzeżnego",
     "obowiązuje całkowity zakaz żeglugi dla statków powyżej 400 GT",
     "zrzuty są dozwolone bez ograniczeń, jeśli statek ma ważne świadectwo IOPP"],
    "MARPOL 73/78, Załączniki I, II, V, VI")
add(BS, "Który z wymienionych obszarów jest obszarem specjalnym wg Załącznika V MARPOL (śmieci), ale NIE jest obszarem specjalnym wg Załącznika I (oleje)?",
    "Wider Caribbean Region (rejon Wielkiego Karaibów)",
    ["Morze Bałtyckie", "Morze Czarne", "Morze Śródziemne"], MP + "V, reg. 1; Załącznik I, reg. 1")
add(BS, "Jedynym obszarem specjalnym wg Załącznika II MARPOL (szkodliwe substancje ciekłe luzem) jest:",
    "obszar Antarktyki",
    ["Morze Bałtyckie", "Morze Czarne", "Morze Czerwone"], MP + "II, reg. 1")
add(BS, "Dopuszczalna zawartość siarki w paliwie okrętowym (Załącznik VI MARPOL) wynosi w obszarach kontroli emisji (ECA/SECA) nie więcej niż:",
    "0,10% m/m (poza ECA globalny limit wynosi 0,50% m/m)",
    ["0,50% m/m w ECA i 3,50% poza ECA", "1,00% m/m w ECA i 0,50% poza ECA", "0,05% m/m w ECA i 0,10% poza ECA"],
    MP + "VI, reg. 14")
add(BS, "Który z wymienionych obszarów jest od 1 maja 2025 r. obszarem kontroli emisji tlenków siarki (SOx ECA) wg Załącznika VI MARPOL?",
    "Morze Śródziemne",
    ["Morze Czerwone", "Morze Czarne", "Morze Arabskie"], MP + "VI, reg. 14 (poprawki MEPC.361(79))")

# ----------------------------------------------------------------------------- wstawienie
rng = random.Random(20261007)
items = []
for it in Q:
    order = list(range(4))
    rng.shuffle(order)
    items.append({**it, "opts": [it["opts"][i] for i in order], "key": "ABCD"[order.index(0)]})

for label, path in DBS.items():
    bak = (ROOT / "data" if label == "seed" else path.parent) / (path.name + f".bak_authored2_{time.strftime('%Y%m%d_%H%M%S')}")
    shutil.copy2(path, bak)
    db = sqlite3.connect(path)
    first = db.execute("SELECT MAX(id) FROM questions").fetchone()[0] + 1
    now = int(time.time() * 1000)
    for k, it in enumerate(items):
        qid = first + k
        a, b, c, d = it["opts"]
        db.execute(
            "INSERT INTO questions (id, kategoria, podkategoria, poziom, tematyka, nr_pytania, typ_pytania, pytanie, odp_a, odp_b, odp_c, odp_d,"
            " poprawna_odpowiedz, poprawna_odpowiedz_tekst, zrodlo_pliku, review_status, review_notes, study_hidden, ai_verified, image_path)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (qid, KAT, None, None, it["tem"], None, "testowe", it["q"], a, b, c, d, it["key"],
             dict(zip("ABCD", it["opts"]))[it["key"]], f"ai_authored:{it['src']}", "ok", f"ai_authored:{STAMP}", 0,
             f"ai_authored:{STAMP}", it["image"]))
        db.execute("INSERT INTO srs_cards (question_id, repetitions, interval_days, ease_factor, due_ms, lapses, state, step)"
                   " VALUES (?,?,?,?,?,?,?,?)", (qid, 0, 0, 2.5, now, 0, 0, 0))
    db.commit()
    n = db.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
    db.close()
    print(label, "dodano", len(items), "ID od", first, "razem pytan", n, bak.name)

lines = [f"# Nowe pytania Master (autorskie, zestaw 2) — WDROŻONE {STAMP}\n"]
for i, it in enumerate(items, 1):
    lines.append(f"## {i}. [{it['tem']}] {it['q']}" + (f"  _(rysunek: {it['image']})_" if it["image"] else ""))
    for l, o in zip("ABCD", it["opts"]):
        lines.append(f"- {'**' if l == it['key'] else ''}{l}) {o}{'** ✔' if l == it['key'] else ''}")
    lines.append(f"\nŹródło: {it['src']}\n")
(ROOT / "review" / f"Nowe_pytania_Master_{STAMP}.md").write_text("\n".join(lines), encoding="utf-8")
print("pytań:", len(items), "rozkład kluczy:", dict(collections.Counter(i["key"] for i in items)))
