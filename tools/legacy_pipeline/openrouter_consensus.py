"""
OpenRouter — konsensus modeli na pytaniach testowych (tylko tekst, litera A-D).
Domyślnie 3 modele (3/3); opcjonalnie 5 modeli z regułą większości 3/5.
"""
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

SYSTEM_PROMPT = (
    "Jesteś egzaminatorem pytań egzaminacyjnych morskich (test wielokrotnego wyboru). "
    "Wybierz jedną poprawną odpowiedź na podstawie treści pytania i podanych opcji. "
    "Odpowiedz WYŁĄCZNIE jedną wielką literą: A, B, C lub D. Bez uzasadnienia, bez innych znaków."
)

LETTER_RE = re.compile(r"\b([ABCD])\b", re.IGNORECASE)

DEFAULT_MODELS_3 = [
    "google/gemini-2.0-flash-001",
    "qwen/qwen-2.5-72b-instruct",
    "deepseek/deepseek-chat",
]

# Tanie, szybkie (bez trybu „thinking”)
DEFAULT_MODELS_5 = DEFAULT_MODELS_3 + [
    "mistralai/mistral-small-3.1-24b-instruct",
    "google/gemini-2.5-flash-lite",
]

DEFAULT_MODELS = DEFAULT_MODELS_3


def _get_api_config():
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY nie ustawiony w .env")
    return api_key, base_url


def get_consensus_models(n=3):
    """n=3 — stare skrypty (3/3); n=5 — większość 3/5."""
    models = []
    for i in range(1, 11):
        m = os.getenv(f"CONSENSUS_MODEL_{i}", "").strip()
        if m:
            models.append(m)
    defaults = DEFAULT_MODELS_5 if n >= 5 else DEFAULT_MODELS_3
    if len(models) < n:
        for m in defaults:
            if m not in models:
                models.append(m)
            if len(models) >= n:
                break
    return models[:n]


def build_prompt(pytanie, odp_a, odp_b, odp_c, odp_d):
    lines = [f"Pytanie:\n{pytanie.strip()}", "", "Opcje:"]
    for letter, text in zip("ABCD", (odp_a, odp_b, odp_c, odp_d)):
        if text and str(text).strip():
            lines.append(f"{letter}: {str(text).strip()}")
    lines.append("")
    lines.append("Odpowiedz jedną literą (A, B, C lub D):")
    return "\n".join(lines)


def parse_letter(raw):
    if not raw:
        return None
    text = raw.strip()
    if len(text) == 1 and text.upper() in "ABCD":
        return text.upper()
    m = LETTER_RE.search(text)
    if m:
        return m.group(1).upper()
    return None


def _chat_completion(model, user_text, max_retries=2):
    api_key, base_url = _get_api_config()
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
        "temperature": 0,
        "max_tokens": 16,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/local/master-exam-mnemonic",
        "X-Title": "Master Exam Mnemonic Consensus",
    }
    url = f"{base_url}/chat/completions"
    last_err = None

    for attempt in range(max_retries + 1):
        try:
            with httpx.Client(timeout=60.0) as client:
                resp = client.post(url, json=payload, headers=headers)
                if resp.status_code in (429, 500, 502, 503) and attempt < max_retries:
                    time.sleep(2 ** attempt)
                    continue
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            last_err = e
            if attempt < max_retries:
                time.sleep(2 ** attempt)
                continue
            raise last_err
    raise last_err


def ask_one_model(model, user_text):
    raw = _chat_completion(model, user_text)
    letter = parse_letter(raw)
    return {"model": model, "raw": raw, "letter": letter}


def ask_all_models(pytanie, odp_a, odp_b, odp_c, odp_d, models=None):
    """
    Zwraca listę dict: {model, raw, letter} dla każdego modelu (równolegle).
    """
    models = models or get_consensus_models()
    user_text = build_prompt(pytanie, odp_a, odp_b, odp_c, odp_d)
    results = []

    workers = min(len(models), 8)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(ask_one_model, m, user_text): m for m in models}
        for fut in as_completed(futures):
            try:
                results.append(fut.result())
            except Exception as e:
                results.append({
                    "model": futures[fut],
                    "raw": None,
                    "letter": None,
                    "error": str(e),
                })

    order = {m: i for i, m in enumerate(models)}
    results.sort(key=lambda r: order.get(r["model"], 99))
    return results


def evaluate_consensus(votes, db_letter):
    """
    Zwraca (action, consensus_letter, detail).
    action: AUTO_OK | NO_CONSENSUS | MISMATCH_DB | INVALID_VOTES
    """
    letters = [v.get("letter") for v in votes if v.get("letter")]
    if len(letters) != 3:
        return "NO_CONSENSUS", None, f"votes={letters}"

    if len(set(letters)) != 1:
        return "NO_CONSENSUS", None, f"split={letters}"

    consensus = letters[0]
    db = (db_letter or "").strip().upper()
    if not db or db not in "ABCD":
        return "INVALID_VOTES", consensus, "no db letter"

    if consensus != db:
        return "MISMATCH_DB", consensus, f"consensus={consensus} db={db}"

    return "AUTO_OK", consensus, f"unanimous={consensus}"


def evaluate_consensus_majority(votes, db_letter, min_agree=3):
    """
    AUTO_OK gdy >= min_agree modeli (z N głosów) zgadza się z literą w bazie.
    Zwraca (action, letter, detail).
    """
    db = (db_letter or "").strip().upper()
    if db not in "ABCD":
        return "INVALID_DB", None, "no db letter"

    letters = [v.get("letter") for v in votes]
    valid = [x for x in letters if x]
    agree_db = sum(1 for x in valid if x == db)
    n_asked = len(votes)

    if agree_db >= min_agree:
        return (
            "AUTO_OK",
            db,
            f"{agree_db}/{n_asked} agree db={db} votes={letters}",
        )

    if len(valid) < min_agree:
        return "NO_CONSENSUS", None, f"valid<{min_agree} votes={letters}"

    return (
        "NO_MAJORITY",
        None,
        f"agree_db={agree_db}/{n_asked} need>={min_agree} votes={letters}",
    )
