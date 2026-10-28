"""Jednorazowo (2026-10-06): 13 autorskich pytan Master (po jednym na zagadnienie) -> baza aplikacji i seed.
Warianty sa losowo mieszane (seed 20261006) dla rownomiernego rozkladu kluczy. ai_verified = ai_authored:<data>.
Kopie *.bak_authored_* (seed w data/). Zapisuje tez wersje do przegladu: review/Nowe_pytania_Master_2026-10-06.md."""
import random
import shutil
import sqlite3
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
STAMP = "2026-10-06"
DBS = {"app": Path.home() / "Documents" / "memonic_app.db", "seed": ROOT / "app" / "assets" / "db" / "memonic_app_seed.db"}
KAT = "Kapitan żeglugi wielkiej"

# (zagadnienie, tematyka, pytanie, [poprawny, błędne...], źródło)
Q = [
    ("Pływy syzygijne", "nawigacja", "Pływy syzygijne (spring tides) występują, gdy:",
     ["Słońce, Ziemia i Księżyc leżą w przybliżeniu na jednej linii (nów i pełnia), a zakres pływu jest największy",
      "Słońce i Księżyc leżą względem Ziemi pod kątem prostym, a zakres pływu jest najmniejszy",
      "Księżyc znajduje się w największej odległości od Ziemi (apogeum), niezależnie od jego fazy",
      "Księżyc przechodzi przez płaszczyznę równika niebieskiego, a pływy mają nierówność dobową"],
     "IHO Hydrographic Dictionary (S-32), Admiralty Tide Tables"),
    ("Pływy kwadraturowe", "nawigacja", "Pływy kwadraturowe (neap tides) charakteryzują się tym, że:",
     ["występują przy pierwszej i trzeciej kwadrze Księżyca, gdy siły Słońca i Księżyca działają pod kątem ok. 90°, a zakres pływu jest najmniejszy",
      "występują w nowiu i pełni Księżyca, a wody wysokie są wyjątkowo wysokie",
      "występują wyłącznie w okresie równonocy wiosennej i jesiennej",
      "zakres pływu jest największy, a prądy pływowe osiągają największą prędkość"],
     "IHO S-32, Admiralty Tide Tables"),
    ("Gross Tonnage", "prawo morskie", "Gross Tonnage (GT), określona w Konwencji ITC 1969, jest:",
     ["bezwymiarową miarą całkowitej wielkości statku, wynikającą z objętości wszystkich jego zamkniętych przestrzeni; "
      "służy m.in. do ustalania wymagań konwencyjnych (np. SOLAS, MARPOL, STCW) i opłat",
      "masą ładunku, jaką statek może zabrać przy zanurzeniu do letniej linii ładunkowej",
      "wypornością statku w stanie lekkim, tj. bez ładunku, zapasów i załogi",
      "miarą wyłącznie użytkowej (ładunkowej i pasażerskiej) pojemności statku, będącą podstawą opłat portowych"],
     "ITC 1969, Annex I, reg. 3; International Tonnage Certificate"),
    ("Net Tonnage", "prawo morskie", "Net Tonnage (NT), określona w Konwencji ITC 1969, jest:",
     ["bezwymiarową miarą użytkowej pojemności statku, tj. jego zdolności do przewozu ładunku i pasażerów, "
      "często stosowaną jako podstawa opłat portowych i kanałowych; nie jest przyjmowana mniejsza niż 30% GT",
      "miarą całkowitej wielkości statku wynikającą z objętości wszystkich jego zamkniętych przestrzeni",
      "nośnością statku (DWT) pomniejszoną o masę załogi, zapasów i wyposażenia",
      "wypornością statku przy zanurzeniu do letniej linii ładunkowej"],
     "ITC 1969, Annex I, reg. 4"),
    ("GM (stateczność)", "bezpieczeństwo statku", "Początkowa wysokość metacentryczna GM jest to odległość między:",
     ["środkiem ciężkości G statku a metacentrum poprzecznym M (GM = KM − KG)",
      "środkiem wyporu B a środkiem ciężkości G statku",
      "kilem K a środkiem ciężkości G statku",
      "środkiem wyporu B a metacentrum poprzecznym M"],
     "IMO IS Code 2008, Part A (min. początkowa GM po poprawce na powierzchnie swobodne: 0,15 m)"),
    ("ECDIS Safety depth", "urządzenia nawigacyjne",
     "W ECDIS wartość „safety depth” (głębokość bezpieczna) ustawiona przez nawigatora służy do:",
     ["wyróżniania sondaży (spot soundings) o głębokości równej lub mniejszej od ustawionej wartości (czarne) względem głębszych (szare)",
      "wyznaczania izobaty, przy której ECDIS generuje alarm zbliżenia do niebezpieczeństwa na trasie",
      "automatycznego obliczania zapasu wody pod stępką na podstawie wskazań echosondy",
      "wyboru skali map ENC wyświetlanych na ekranie"],
     "IHO S-52 (Presentation Library), IMO MSC.232(82) / IEC 61174"),
    ("ECDIS Safety contour", "urządzenia nawigacyjne",
     "Jeżeli wartość „safety contour” wybrana przez nawigatora nie występuje w danych ENC, ECDIS:",
     ["użyje najbliższej głębszej izobaty i poinformuje o tym nawigatora",
      "użyje najbliższej płytszej izobaty i nie poinformuje o tym nawigatora",
      "wyłączy wyświetlanie izobat i alarmy antykolizyjne",
      "przyjmie wartość domyślną 10 m, niezależnie od wyboru nawigatora"],
     "IHO S-52 (domyślnie następna głębsza izobata), IMO MSC.232(82)"),
    ("Konosament", "prawo morskie", "Konosament wystawiany przez przewoźnika pełni jednocześnie funkcje:",
     ["pokwitowania przyjęcia ładunku do przewozu, dowodu zawarcia umowy przewozu oraz dokumentu legitymującego do odbioru ładunku w porcie przeznaczenia",
      "wyłącznie dokumentu celnego i deklaracji ładunku dla władz portu",
      "polisy ubezpieczeniowej ładunku oraz dowodu zapłaty frachtu",
      "listu przewozowego, który zawsze jest nieprzenoszalny i imienny"],
     "Reguły haskie / haskie-visbyjskie (art. III ust. 3), Kodeks morski"),
    ("Zabrudzony konosament", "prawo morskie", "Zabrudzony konosament (claused, „dirty” B/L) to konosament, który:",
     ["zawiera zastrzeżenia przewoźnika o widocznych wadach, uszkodzeniach lub niedostatkach ładunku albo opakowania stwierdzonych przy załadunku",
      "został wystawiony po upływie terminu przewidzianego w umowie przewozu",
      "jest wystawiony „na zlecenie”, a nie „imiennie”",
      "zawiera adnotację „freight prepaid” (fracht zapłacony)"],
     "Reguły haskie-visbyjskie, art. III ust. 3 i 4; UCP 600"),
    ("Indos", "prawo morskie", "Indos na konosamencie „na zlecenie” oznacza:",
     ["przeniesienie praw z konosamentu (a tym samym do ładunku) na inną osobę przez oświadczenie indosanta, zwykle podpis na odwrocie dokumentu (indos in blanco to sam podpis)",
      "potwierdzenie przez kapitana, że ładunek załadowano w stanie nieuszkodzonym",
      "zawiadomienie odbiorcy o przybyciu statku do portu wyładunku",
      "zwolnienie przewoźnika z odpowiedzialności za szkody w ładunku"],
     "Kodeks morski (konosament na zlecenie), praktyka handlu morskiego"),
    ("Dyspasza", "zarządzanie statkiem", "Dyspasza (despatch money) w umowie czarterowej to:",
     ["premia płacona przez armatora czarterującemu (załadowcy/odbiorcy) za skrócenie czasu przeładunku w stosunku do czasu dozwolonego (laytime), zwykle w wysokości połowy stawki demurrage",
      "kara umowna płacona przez czarterującego armatorowi za przekroczenie czasu przeznaczonego na załadunek lub wyładunek",
      "opłata portowa za korzystanie z nabrzeża poza godzinami pracy portu",
      "wynagrodzenie brokera za pośrednictwo w zawarciu czarteru"],
     "GENCON 94 / formularze BIMCO (laytime, demurrage, despatch)"),
    ("Kwit sternika", "zarządzanie statkiem", "Kwit sternika (Mate's Receipt) to dokument:",
     ["wystawiany przez oficera statku (zwykle I oficera) po przyjęciu ładunku na statek, potwierdzający jego ilość i stan oraz stanowiący podstawę do wystawienia konosamentu",
      "wystawiany przez agenta portowego jako dowód zapłaty opłat portowych",
      "wystawiany przez port jako zgoda na wyjście statku w morze",
      "będący dokumentem tytułu prawnego do ładunku, który można swobodnie przenosić przez indos"],
     "praktyka przewozu morskiego; reguły haskie art. III ust. 3"),
    ("Manifest ładunkowy", "prawo morskie", "Manifest ładunkowy (Cargo Declaration, formularz FAL 2) to:",
     ["wykaz (deklaracja) ładunku przewożonego na statku, przedstawiany władzom portu zgodnie z Konwencją FAL (ułatwienia w międzynarodowym ruchu morskim)",
      "wykaz załogi statku przedstawiany władzom portu przy wejściu i wyjściu",
      "plan rozmieszczenia ładunku na statku sporządzany przez I oficera na potrzeby obliczeń stateczności",
      "świadectwo wystawiane przez towarzystwo klasyfikacyjne po kontroli ładowni"],
     "IMO Convention FAL 1965 (FAL 2 Cargo Declaration); SOLAS rozdz. VII"),
]

rng = random.Random(20261006)
items = []
for topic, tem, stem, opts, src in Q:
    order = list(range(4))
    rng.shuffle(order)
    shuffled = [opts[i] for i in order]
    items.append({"topic": topic, "tem": tem, "q": stem, "opts": shuffled, "key": "ABCD"[order.index(0)], "src": src})

for label, path in DBS.items():
    bak = (ROOT / "data" if label == "seed" else path.parent) / (path.name + f".bak_authored_{time.strftime('%Y%m%d_%H%M%S')}")
    shutil.copy2(path, bak)
    db = sqlite3.connect(path)
    first = db.execute("SELECT MAX(id) FROM questions").fetchone()[0] + 1
    now = int(time.time() * 1000)
    for k, it in enumerate(items):
        qid = first + k
        a, b, c, d = it["opts"]
        db.execute(
            "INSERT INTO questions (id, kategoria, podkategoria, poziom, tematyka, nr_pytania, typ_pytania, pytanie, odp_a, odp_b, odp_c, odp_d,"
            " poprawna_odpowiedz, poprawna_odpowiedz_tekst, zrodlo_pliku, review_status, review_notes, study_hidden, ai_verified)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (qid, KAT, None, None, it["tem"], None, "testowe", it["q"], a, b, c, d, it["key"],
             dict(zip("ABCD", it["opts"]))[it["key"]], f"ai_authored:{it['src']}", "ok", f"ai_authored:{STAMP}", 0, f"ai_authored:{STAMP}"))
        db.execute("INSERT INTO srs_cards (question_id, repetitions, interval_days, ease_factor, due_ms, lapses, state, step)"
                   " VALUES (?,?,?,?,?,?,?,?)", (qid, 0, 0, 2.5, now, 0, 0, 0))
    db.commit()
    n = db.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
    db.close()
    print(label, "dodano", len(items), "ID od", first, "razem pytan", n, bak.name)

lines = ["# Nowe pytania Master (autorskie) — WDROŻONE 2026-10-06\n",
         "Źródło: dokumenty morskie wg kolumny „Źródło”; `ai_verified = ai_authored:2026-10-06`. Kolejność wariantów wymieszana.\n"]
for it in items:
    lines.append(f"## {it['topic']} — tematyka: {it['tem']}\n**{it['q']}**")
    for l, o in zip("ABCD", it["opts"]):
        lines.append(f"- {'**' if l == it['key'] else ''}{l}) {o}{'** ✔' if l == it['key'] else ''}")
    lines.append(f"\nŹródło: {it['src']}\n")
(ROOT / "review" / "Nowe_pytania_Master_2026-10-06.md").write_text("\n".join(lines), encoding="utf-8")
import collections
print("rozkład kluczy:", dict(collections.Counter(i["key"] for i in items)))
