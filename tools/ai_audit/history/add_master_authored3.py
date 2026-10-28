"""Jednorazowo (2026-10-08): autorskie pytania Master (zestaw 3: planowanie podrozy A.893, UKC/squat/Barrass, Letter of Protest,
Polar Code, klasy lodowe IACS PC1-PC7). Warianty mieszane (seed), ai_verified = ai_authored:<data>.
Kopie *.bak_authored3_* (seed w data/). Zapis do review/Nowe_pytania_Master_2026-10-08.md."""
import collections
import random
import shutil
import sqlite3
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
STAMP = "2026-10-08"
DBS = {"app": Path.home() / "Documents" / "memonic_app.db", "seed": ROOT / "app" / "assets" / "db" / "memonic_app_seed.db"}
KAT = "Kapitan żeglugi wielkiej"
NAW, PM, BS = "nawigacja", "prawo morskie", "bezpieczeństwo statku"

Q = []


def add(tem, q, correct, wrong, src, image=None):
    assert len(wrong) == 3, q
    Q.append({"tem": tem, "q": q, "opts": [correct] + wrong, "src": src, "image": image})


# ---------------------------------------------------------------- planowanie podróży (IMO A.893(21))
A893 = "IMO Res. A.893(21) Guidelines for Voyage Planning; SOLAS V/34"
add(NAW, "Zgodnie z Wytycznymi IMO dotyczącymi planowania podróży (A.893(21)) planowanie podróży obejmuje cztery fazy:",
    "zbieranie informacji (appraisal), planowanie (planning), realizację planu (execution) i monitorowanie postępów (monitoring)",
    ["przygotowanie statku, załadunek, rejs i wyładunek",
     "odprawę celną, wyjście w morze, rejs i przybycie do portu przeznaczenia",
     "analizę pogody, wybór trasy, zatwierdzenie przez armatora i podpis kapitana"],
    A893)
add(NAW, "Pierwszą fazą planowania podróży według Wytycznych IMO A.893(21) jest:",
    "zbieranie informacji (appraisal) — zgromadzenie wszystkich informacji istotnych dla planowanej podróży",
    ["realizacja planu (execution) — prowadzenie statku wzdłuż wyznaczonej trasy",
     "monitorowanie postępów (monitoring) — kontrola pozycji statku względem planu",
     "sporządzenie tabeli przejścia i naniesienie trasy na mapy bez analizy informacji"],
    A893)
add(NAW, "Zgodnie z Wytycznymi IMO A.893(21) plan podróży powinien obejmować podróż:",
    "od nabrzeża do nabrzeża (berth to berth), łącznie z obszarami, na których wymagana jest obecność pilota",
    ["wyłącznie od wyjścia z portu do wejścia do portu przeznaczenia, z pominięciem odcinków z pilotem",
     "tylko odcinki na akwenach otwartych, poza strefami o dużym natężeniu ruchu",
     "wyłącznie odcinki, na których statek podlega kontroli państwa portu"],
    A893)

# ---------------------------------------------------------------- UKC, osiadanie, wzór Barrassa
SQ = "Barrass, Ship Design and Performance for Masters and Mates (wzór Barrassa); praktyka UKC management"
add(NAW, "Zapas wody pod stępką (UKC — Under Keel Clearance) to:",
    "różnica między głębokością wody w danym miejscu (z uwzględnieniem pływu) a zanurzeniem statku powiększonym o osiadanie i inne poprawki (np. falowanie, przechył)",
    ["różnica między zanurzeniem dziobowym a rufowym statku (trym)",
     "odległość między dolną krawędzią stępki a poziomem wody w doku suchym",
     "różnica między głębokością z mapy (zero mapy) a średnim zanurzeniem w morzu letnim, bez poprawki na pływ"],
    SQ)
add(NAW, "Statek o zanurzeniu 10,2 m wchodzi na tor wodny, gdzie głębokość wody (z uwzględnieniem pływu) wynosi 12,0 m, a przewidywane osiadanie to 0,6 m. Zapas wody pod stępką (UKC) wynosi:",
    "1,2 m", ["1,8 m", "0,6 m", "2,4 m"], SQ)
add(NAW, "Uproszczony wzór Barrassa na maksymalne osiadanie statku na akwenie otwartym (Cb – współczynnik pełnotliwości, V – prędkość w węzłach) ma postać:",
    "osiadanie [m] = Cb · V² / 100",
    ["osiadanie [m] = Cb · V / 100", "osiadanie [m] = V² / (Cb · 100)", "osiadanie [m] = Cb · V² · 100"],
    SQ)
add(NAW, "Statek o współczynniku pełnotliwości Cb = 0,80 idzie po akwenie otwartym z prędkością 10 węzłów. Maksymalne osiadanie według uproszczonego wzoru Barrassa (Cb·V²/100) wynosi:",
    "0,80 m", ["0,08 m", "8,0 m", "1,6 m"], SQ)
add(NAW, "Ten sam statek (Cb = 0,80, V = 10 węzłów) idzie wąskim, ograniczonym kanałem. Przyjmując, że w kanale ograniczonym osiadanie z uproszczonego wzoru Barrassa podwaja się, wynosi ono:",
    "1,60 m", ["0,80 m", "0,40 m", "3,20 m"], SQ)

# ---------------------------------------------------------------- osiadanie (squat)
add(NAW, "Osiadanie statku (squat) to:",
    "zwiększenie średniego zanurzenia statku w ruchu (często ze zmianą trymu) w porównaniu z zanurzeniem w spoczynku, wywołane spadkiem ciśnienia pod kadłubem i zwiększoną prędkością strumienia opływającego, zwłaszcza na wodzie płytkiej",
    ["przechył statku wywołany parciem wiatru na nadwodzie",
     "zwiększenie zanurzenia statku spowodowane wyłącznie zabraniem dodatkowego ładunku",
     "zmniejszenie wysokości burty wolnej spowodowane falowaniem morza"],
    SQ)
add(NAW, "Osiadanie statku jest tym większe, im:",
    "większa jest prędkość statku (w przybliżeniu proporcjonalnie do kwadratu prędkości), większa pełnotliwość kadłuba i mniejszy zapas wody (płytki, wąski akwen)",
    ["mniejsza jest prędkość statku, bo wolniej płynący statek mocniej zanurza się w wodzie",
     "mniejsza jest pełnotliwość kadłuba, a głębokość wody nie ma znaczenia",
     "większa jest głębokość wody pod stępką, niezależnie od prędkości statku"],
    SQ)
add(NAW, "Najskuteczniejszym sposobem ograniczenia osiadania statku na płytkiej wodzie jest:",
    "zmniejszenie prędkości statku",
    ["zwiększenie prędkości, aby statek szybciej opuścił płytki akwen",
     "zwiększenie zanurzenia przez zabranie balastu",
     "przejście z kursu na środek toru wodnego na kurs wzdłuż brzegu"],
    SQ)

# ---------------------------------------------------------------- Letter of Protest
LOP = "praktyka przewozu morskiego i czarterów (Letter of Protest, protest morski — Kodeks morski)"
add(PM, "Letter of Protest (LOP) to:",
    "pisemne zastrzeżenie (sprzeciw) kapitana lub armatora skierowane do strony trzeciej (np. czarterującego, terminala, odbiorcy) w sprawie okoliczności, które mogą rodzić odpowiedzialność statku, składane w celu zabezpieczenia jego praw i roszczeń",
    ["oświadczenie kapitana o zdarzeniu morskim składane przed sądem, konsulem lub notariuszem (protest morski)",
     "gwarancja odszkodowawcza (Letter of Indemnity) wystawiana przez czarterującego na rzecz przewoźnika",
     "zawiadomienie o gotowości statku do załadunku lub wyładunku (Notice of Readiness)"],
    LOP)
add(PM, "Czym Letter of Protest różni się od protestu morskiego?",
    "protest morski to oświadczenie kapitana o zdarzeniu lub szkodzie składane przed właściwym organem (np. sądem, konsulem), a Letter of Protest to pismo kapitana lub armatora do kontrahenta, zastrzegające prawa statku",
    ["Letter of Protest składa się zawsze przed sądem, a protest morski wysyła się do czarterującego",
     "oba dokumenty są tym samym, a różnią się wyłącznie językiem, w którym je sporządzono",
     "protest morski jest dokumentem celnym, a Letter of Protest — dokumentem ubezpieczeniowym"],
    LOP)

# ---------------------------------------------------------------- Polar Code, klasy IACS
PC = "IMO International Code for Ships Operating in Polar Waters (Polar Code), SOLAS XIV, MARPOL"
add(BS, "Obszar polarny w rozumieniu Kodeksu Polarnego (Polar Code) obejmuje:",
    "Antarktykę (obszar morski na południe od 60°S) oraz wody Arktyki określone w SOLAS XIV/1 (w przybliżeniu na północ od 60°N; dokładne współrzędne granicy podaje SOLAS XIV/1)",
    ["wyłącznie obszar morski na południe od 60°S",
     "wszystkie wody na północ od koła podbiegunowego północnego i na południe od koła podbiegunowego południowego, bez wyjątków",
     "wyłącznie obszary pokryte lodem przez cały rok, niezależnie od szerokości geograficznej"],
    PC)
add(BS, "Kodeks Polarny (Polar Code) obowiązuje nowe statki objęte SOLAS w obszarach polarnych od:",
    "1 stycznia 2017 r.", ["1 stycznia 2010 r.", "1 lipca 2012 r.", "1 stycznia 2020 r."], PC)
add(BS, "Dokumentem wydawanym statkowi potwierdzającym zgodność z Kodeksem Polarnym jest:",
    "Polar Ship Certificate (Świadectwo statku polarnego)",
    ["Ice Navigation Certificate (Świadectwo żeglugi lodowej) wydawane wyłącznie przez państwo nadbrzeżne",
     "Document of Compliance (DOC) wydawany armatorowi w ramach ISM",
     "International Load Line Certificate dla statków pływających w lodzie"],
    PC)
CAT = {
    "A": "statek zaprojektowany do żeglugi w wodach polarnych w co najmniej średnim lodzie jednorocznym, który może zawierać wtrącenia lodu starego",
    "B": "statek niebędący statkiem kategorii A, zaprojektowany do żeglugi w wodach polarnych w co najmniej cienkim lodzie jednorocznym, który może zawierać wtrącenia lodu starego",
    "C": "statek zaprojektowany do żeglugi na wodach otwartych lub w warunkach lodowych łagodniejszych niż w kategoriach A i B",
}
for k, v in CAT.items():
    wrong = [CAT[x] for x in CAT if x != k]
    wrong.append("statek lodołamacz o napędzie jądrowym, niezależnie od projektowanej zdolności do żeglugi w lodzie")
    random.Random("cat" + k).shuffle(wrong)
    add(BS, f"Według Kodeksu Polarnego statek kategorii {k} to:", v, wrong[:3], PC)
PCLS = "IACS Unified Requirement UR I (Polar Class), tab. 1"
PCD = {
    1: "całoroczna żegluga we wszystkich wodach polarnych",
    2: "całoroczna żegluga w umiarkowanym lodzie wieloletnim",
    3: "całoroczna żegluga w lodzie dwuletnim, który może zawierać wtrącenia lodu wieloletniego",
    4: "całoroczna żegluga w grubym lodzie jednorocznym, który może zawierać wtrącenia lodu starego",
    5: "całoroczna żegluga w średnim lodzie jednorocznym, który może zawierać wtrącenia lodu starego",
    6: "żegluga latem i jesienią w średnim lodzie jednorocznym, który może zawierać wtrącenia lodu starego",
    7: "żegluga latem i jesienią w cienkim lodzie jednorocznym, który może zawierać wtrącenia lodu starego",
}
add(BS, "Klasy lodowe IACS Polar Class (PC) obejmują:",
    "siedem klas, od PC1 (najwyższa, całoroczna żegluga we wszystkich wodach polarnych) do PC7 (najniższa, żegluga latem i jesienią w cienkim lodzie jednorocznym)",
    ["trzy klasy: PC1, PC2 i PC3, odpowiadające kategoriom A, B i C Kodeksu Polarnego",
     "pięć klas, od PC1 (najniższa) do PC5 (najwyższa), wyłącznie dla lodołamaczy",
     "dziesięć klas, od PC0 do PC9, zależnych od mocy maszyny głównej"],
    PCLS)
for n, desc in PCD.items():
    others = [f"{v}" for k, v in PCD.items() if k != n]
    random.Random(f"pc{n}").shuffle(others)
    add(BS, f"Klasa lodowa IACS Polar Class PC{n} oznacza statek przeznaczony do:", desc, others[:3], PCLS)

# ----------------------------------------------------------------------------- wstawienie
rng = random.Random(20261008)
items = []
for it in Q:
    order = list(range(4))
    rng.shuffle(order)
    items.append({**it, "opts": [it["opts"][i] for i in order], "key": "ABCD"[order.index(0)]})

for label, path in DBS.items():
    bak = (ROOT / "data" if label == "seed" else path.parent) / (path.name + f".bak_authored3_{time.strftime('%Y%m%d_%H%M%S')}")
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

lines = [f"# Nowe pytania Master (autorskie, zestaw 3) — WDROŻONE {STAMP}\n"]
for i, it in enumerate(items, 1):
    lines.append(f"## {i}. [{it['tem']}] {it['q']}")
    for l, o in zip("ABCD", it["opts"]):
        lines.append(f"- {'**' if l == it['key'] else ''}{l}) {o}{'** ✔' if l == it['key'] else ''}")
    lines.append(f"\nŹródło: {it['src']}\n")
(ROOT / "review" / f"Nowe_pytania_Master_{STAMP}.md").write_text("\n".join(lines), encoding="utf-8")
print("pytań:", len(items), "rozkład kluczy:", dict(collections.Counter(i["key"] for i in items)))
