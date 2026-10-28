"""
Klient OpenRouter Vision — ekstrakcja strukturalna pytania z obrazu PDF.
"""
import base64
import json
import os
import re
import time

import httpx
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

SYSTEM_PROMPT = """Jesteś asystentem OCR dla polskich pytań egzaminacyjnych morskich w formie tabel PDF.
Odczytaj DOKŁADNIE treść z obrazu. Zwróć WYŁĄCZNIE poprawny JSON (bez markdown, bez komentarzy).

Format:
{
  "pytanie": "treść pytania",
  "odp_a": "..." lub null,
  "odp_b": "..." lub null,
  "odp_c": "..." lub null,
  "odp_d": "..." lub null,
  "poprawna_odpowiedz": "A"|"B"|"C"|"D"|null,
  "typ_pytania": "testowe"|"otwarte",
  "poprawna_odpowiedz_tekst": "..." lub null
}

Zasady:
- Zachowaj polskie znaki i interpunkcję.
- Nie wymyślaj brakujących opcji — użyj null jeśli nie widać na obrazie.
- Dla fiszek (otwarte): wypełnij pytanie i poprawna_odpowiedz_tekst jeśli widoczne.
- poprawna_odpowiedz to tylko jedna litera A/B/C/D gdy widać oznaczenie poprawnej odpowiedzi.
"""

SYSTEM_PROMPT_KAPITAN_PAGE = """Jesteś asystentem OCR dla polskich pytań egzaminacyjnych morskich (Kapitan żeglugi wielkiej).
Otrzymujesz pełną stronę (lub dwie kolejne strony) skanu tabeli PDF.

Układ tabeli:
- Lewa kolumna: numer pytania (np. 15. lub 16.)
- Środek: treść pytania oraz opcje a, b, c (czasem d)
- Prawa kolumna: litera poprawnej odpowiedzi (A, B, C lub D)

Odczytaj DOKŁĄDNIE jedno wskazane pytanie. Zwróć WYŁĄCZNIE poprawny JSON (bez markdown).

Format:
{
  "pytanie": "treść pytania",
  "odp_a": "..." lub null,
  "odp_b": "..." lub null,
  "odp_c": "..." lub null,
  "odp_d": "..." lub null,
  "poprawna_odpowiedz": "A"|"B"|"C"|"D"|null,
  "typ_pytania": "testowe"|"otwarte",
  "poprawna_odpowiedz_tekst": "..." lub null
}

Zasady:
- Identyfikuj wiersz po numerze w lewej kolumnie ORAZ fragmencie treści z bazy (jeśli podany).
- Przy dwóch obrazach: drugi to kontynuacja tego samego pytania na następnej stronie.
- Nie wymyślaj opcji — null gdy brak na stronie.
- Zachowaj polskie znaki.
"""

SYSTEM_PROMPT_FORMAT1_PAGE = """Jesteś asystentem OCR dla pytań egzaminacyjnych morskich w tabeli PDF.
Otrzymujesz pełną stronę (lub dwie kolejne strony) skanu tabeli.

Typowy układ (format 1 — Dział pokładowy / Angielski):
- Kolumna Lp: numer pytania
- Kolumna O/T: flaga (opcjonalnie)
- Kolumna Pytanie: treść pytania oraz opcje a), b), c) (czasem d))
- Ostatnia kolumna: litera poprawnej odpowiedzi (A, B, C lub D)

Odczytaj DOKŁADNIE jeden wskazany wiersz (numer Lp). Zwróć WYŁĄCZNIE poprawny JSON (bez markdown).

Format:
{
  "pytanie": "treść pytania",
  "odp_a": "..." lub null,
  "odp_b": "..." lub null,
  "odp_c": "..." lub null,
  "odp_d": "..." lub null,
  "poprawna_odpowiedz": "A"|"B"|"C"|"D"|null,
  "typ_pytania": "testowe"|"otwarte",
  "poprawna_odpowiedz_tekst": "..." lub null
}

Zasady:
- Identyfikuj wiersz po numerze Lp ORAZ fragmencie treści z bazy (jeśli podany).
- Zachowaj język źródła (polski lub angielski) — nie tłumacz.
- Przy dwóch obrazach: drugi to kontynuacja tego samego pytania na następnej stronie.
- Nie wymyślaj opcji — null gdy brak w wierszu.
"""


def _get_config():
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    model = os.getenv("OPENROUTER_MODEL", "google/gemini-2.0-flash-001").strip()
    base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY nie ustawiony w .env")
    return api_key, model, base_url


def _extract_json(text):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def extract_question_from_image(png_bytes, nr_pytania=None, max_retries=2):
    """
    Wyślij obraz do OpenRouter i zwróć sparsowany dict.

    Raises:
        ValueError, httpx.HTTPError
    """
    api_key, model, base_url = _get_config()
    b64 = base64.standard_b64encode(png_bytes).decode("ascii")
    data_url = f"data:image/png;base64,{b64}"

    hint = ""
    if nr_pytania is not None:
        hint = f" Szukaj pytania numer {nr_pytania} na obrazie."

    user_text = (
        f"Odczytaj pytanie egzaminacyjne z tego wycinka tabeli PDF.{hint} "
        "Zwróć wyłącznie JSON zgodny ze schematem."
    )

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_text},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            },
        ],
        "temperature": 0.1,
        "max_tokens": 2048,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/local/master-exam-mnemonic",
        "X-Title": "Master Exam Mnemonic Vision Fix",
    }

    url = f"{base_url}/chat/completions"
    last_err = None

    for attempt in range(max_retries + 1):
        try:
            with httpx.Client(timeout=120.0) as client:
                resp = client.post(url, json=payload, headers=headers)
                if resp.status_code == 429 or resp.status_code >= 500:
                    if attempt < max_retries:
                        time.sleep(2 ** attempt)
                        continue
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                parsed = _extract_json(content)
                parsed["_model"] = model
                parsed["_usage"] = data.get("usage")
                return parsed
        except (httpx.HTTPError, json.JSONDecodeError, KeyError) as e:
            last_err = e
            if attempt < max_retries:
                time.sleep(2 ** attempt)
                continue
            raise

    raise last_err


def _build_vision_request(content_parts, system_prompt, max_retries=2):
    api_key, model, base_url = _get_config()
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content_parts},
        ],
        "temperature": 0.1,
        "max_tokens": 2048,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/local/master-exam-mnemonic",
        "X-Title": "Master Exam Mnemonic Vision Kapitan",
    }
    url = f"{base_url}/chat/completions"
    last_err = None

    for attempt in range(max_retries + 1):
        try:
            with httpx.Client(timeout=180.0) as client:
                resp = client.post(url, json=payload, headers=headers)
                if resp.status_code == 429 or resp.status_code >= 500:
                    if attempt < max_retries:
                        time.sleep(2 ** attempt)
                        continue
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                parsed = _extract_json(content)
                parsed["_model"] = model
                parsed["_usage"] = data.get("usage")
                return parsed
        except (httpx.HTTPError, json.JSONDecodeError, KeyError) as e:
            last_err = e
            if attempt < max_retries:
                time.sleep(2 ** attempt)
                continue
            raise
    raise last_err


def extract_question_from_pages(
    png_list,
    nr_pytania=None,
    pytanie_hint=None,
    pdf_format="format2",
    max_retries=2,
):
    """
    Wyślij 1–2 pełne strony PDF i wyciągnij jedno pytanie po numerze.
    pdf_format: 'format1' (Dział/Angielski) lub 'format2' (Kapitan).
    """
    if not png_list:
        raise ValueError("png_list is empty")

    system = (
        SYSTEM_PROMPT_FORMAT1_PAGE
        if pdf_format == "format1"
        else SYSTEM_PROMPT_KAPITAN_PAGE
    )

    parts = []
    if pdf_format == "format1":
        nr_line = (
            f"Numer pytania (Lp) w tabeli: {nr_pytania}."
            if nr_pytania is not None
            else "Znajdź właściwy wiersz po fragmencie treści z bazy."
        )
    else:
        nr_line = (
            f"Numer pytania w lewej kolumnie PDF: {nr_pytania}."
            if nr_pytania is not None
            else "Znajdź właściwe pytanie po fragmencie treści z bazy."
        )
    hint = ""
    if pytanie_hint:
        hint = f" Fragment treści z bazy (pomoc identyfikacji): «{pytanie_hint[:120]}»."
    pages_note = (
        "Załączone są dwie kolejne strony — druga może zawierać kontynuację tego pytania."
        if len(png_list) > 1
        else "Załączona jest jedna pełna strona PDF."
    )
    parts.append({
        "type": "text",
        "text": (
            f"{pages_note} Wyciągnij wyłącznie to jedno pytanie. {nr_line}{hint} "
            "Zwróć wyłącznie JSON zgodny ze schematem."
        ),
    })
    for png in png_list:
        b64 = base64.standard_b64encode(png).decode("ascii")
        parts.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{b64}"},
        })

    return _build_vision_request(parts, system, max_retries=max_retries)


def validate_parsed(parsed):
    """
    Waliduj odpowiedź modelu. Zwraca (ok, normalized_dict, error_msg).
    """
    if not isinstance(parsed, dict):
        return False, None, "response is not a dict"

    pytanie = (parsed.get("pytanie") or "").strip()
    if not pytanie or len(pytanie) < 3:
        return False, None, "empty or too short pytanie"

    typ = (parsed.get("typ_pytania") or "testowe").strip().lower()
    if typ not in ("testowe", "otwarte"):
        typ = "testowe"

    letter = parsed.get("poprawna_odpowiedz")
    if letter:
        letter = str(letter).strip().upper()
        if letter not in ("A", "B", "C", "D"):
            letter = None
    else:
        letter = None

    def opt(key):
        v = parsed.get(key)
        if v is None:
            return None
        s = str(v).strip()
        return s if s else None

    result = {
        "pytanie": pytanie,
        "odp_a": opt("odp_a"),
        "odp_b": opt("odp_b"),
        "odp_c": opt("odp_c"),
        "odp_d": opt("odp_d"),
        "poprawna_odpowiedz": letter,
        "typ_pytania": typ,
        "poprawna_odpowiedz_tekst": opt("poprawna_odpowiedz_tekst"),
    }

    if typ == "testowe" and letter:
        key = f"odp_{letter.lower()}"
        result["poprawna_odpowiedz_tekst"] = result.get(key)

    if typ == "otwarte" and not result["poprawna_odpowiedz_tekst"]:
        result["poprawna_odpowiedz_tekst"] = opt("poprawna_odpowiedz_tekst")

    return True, result, ""
