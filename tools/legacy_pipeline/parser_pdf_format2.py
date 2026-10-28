"""
Parsiuje PDFy w formacie 2 (Kapitan żeglugi wielkiej).

Układ: wielokolumnowa tabela. Używa klastrowania labeli odpowiedzi.
"""
import fitz
import re
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
from init_db import get_connection, insert_questions, mark_file_parsed, is_file_parsed


def normalize(text):
    return re.sub(r"\s+", " ", text.strip())


def extract_blocks_with_positions(filepath):
    doc = fitz.open(filepath)
    blocks = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        text_dict = page.get_text("dict")
        for block in text_dict["blocks"]:
            if "lines" not in block:
                continue
            for line in block["lines"]:
                text_parts = []
                for span in line["spans"]:
                    text_parts.append(span["text"])
                full_text = "".join(text_parts).strip()
                if full_text:
                    bbox = line["bbox"]
                    blocks.append((page_num, bbox[1], bbox[0], normalize(full_text)))
    doc.close()
    return blocks


def parse_kapitan(filepath, kategoria, tematyka):
    blocks = extract_blocks_with_positions(filepath)

    # Extract all elements
    all_qnums = []     # (page, y, qnum)
    all_qtexts = []    # (page, y, text)
    ans_labels = []    # (page, y, letter)
    ans_texts = []     # (page, y, x, text)
    corrects = []      # (page, y, letter)

    for block in blocks:
        page_num, y, x, text = block

        if re.match(r"^\d{1,3}\.?$", text) and x < 100:
            qnum = int(re.match(r"(\d+)", text).group(1))
            all_qnums.append((page_num, y, qnum))

        elif re.match(r"^[a-dA-D][\)\.]?$", text) and 80 <= x <= 95:
            letter = text[0].upper()
            ans_labels.append((page_num, y, letter))

        elif re.match(r"^[A-D]$", text) and x > 400:
            corrects.append((page_num, y, text))

        elif 65 <= x <= 90 and len(text) > 3:
            if not re.match(r"^\d{1,3}\.?$", text) and not re.match(r"^[a-dA-D][\)\.]?$", text):
                all_qtexts.append((page_num, y, text))

        elif 95 <= x <= 350:
            ans_texts.append((page_num, y, x, text))

    # Sort everything globally
    all_qnums.sort(key=lambda b: (b[0], b[1]))
    all_qtexts.sort(key=lambda b: (b[0], b[1]))
    ans_labels.sort(key=lambda b: (b[0], b[1]))
    ans_texts.sort(key=lambda b: (b[0], b[1]))
    corrects.sort(key=lambda b: (b[0], b[1]))

    # Merge consecutive clusters that span page boundaries
    # A cluster ending with just "A" on page N, and next page starts with "B", "C" — they're the same question
    def merge_cross_page_clusters(clusters):
        if len(clusters) <= 1:
            return clusters
        merged = []
        i = 0
        while i < len(clusters):
            current = list(clusters[i])
            # Check if the last label in current is not the last letter (A, B, C, D)
            # and the next cluster starts on a different page with remaining letters
            if i + 1 < len(clusters):
                next_cluster = clusters[i + 1]
                if current[0][0] != next_cluster[0][0]:
                    # Cross-page: merge if next cluster continues the alphabet
                    last_letters = {l[2] for l in current}
                    next_letters = {l[2] for l in next_cluster}
                    # Merge if there's no letter overlap
                    if not last_letters.intersection(next_letters):
                        current.extend(next_cluster)
                        i += 1  # skip next cluster
            merged.append(current)
            i += 1
        return merged

    # Build label clusters
    CLUSTER_GAP = 40
    label_clusters = []
    current_cluster = []

    for ap, ay, letter in ans_labels:
        if current_cluster:
            last = current_cluster[-1]
            if ap == last[0] and ay - last[1] < CLUSTER_GAP:
                current_cluster.append((ap, ay, letter))
            else:
                if current_cluster:
                    label_clusters.append(current_cluster)
                current_cluster = [(ap, ay, letter)]
        else:
            current_cluster = [(ap, ay, letter)]

    if current_cluster:
        label_clusters.append(current_cluster)

    # Merge cross-page clusters
    label_clusters = merge_cross_page_clusters(label_clusters)

    # For each cluster, find the associated question number and text
    questions = []

    for cluster in label_clusters:
        cluster_page = cluster[0][0]
        cluster_y_min = min(l[1] for l in cluster)
        cluster_y_max = max(l[1] for l in cluster)

        # Find qnum: closest to cluster, on same page, preferably above labels
        best_qnum = None
        best_qdist = float("inf")
        for qp, qy, qnum in all_qnums:
            if qp == cluster_page:
                dist = abs(qy - cluster_y_min)
                if dist < best_qdist and dist < 200:
                    best_qdist = dist
                    best_qnum = qnum

        # Find qtext: closest to cluster_y_min, on same page, prefer above
        best_qtext = ""
        best_tdist = float("inf")
        for tp, ty, txt in all_qtexts:
            if tp == cluster_page:
                dist = abs(ty - cluster_y_min)
                if dist < best_tdist and dist < 300:
                    best_tdist = dist
                    best_qtext = txt

        if not best_qnum or not best_qtext:
            continue

        # Validation: require at least 1 answer label and valid question text
        if len(cluster) < 1:
            continue
        if not best_qtext or len(best_qtext.strip()) < 3:
            continue

        # Collect answer texts assigned to labels in this cluster
        ans_dict = {}
        for _, _, letter in cluster:
            ans_dict[letter] = ""

        # Get all pages in cluster
        cluster_pages = set(l[0] for l in cluster)

        for ap, ay, ax, text in ans_texts:
            if ap not in cluster_pages:
                continue
            # Find the nearest label in cluster
            best_letter = None
            best_dist = float("inf")
            for lp, ly, letter in cluster:
                if lp == ap and ly <= ay:
                    dist = ay - ly
                    if dist < best_dist and dist < 30:
                        best_dist = dist
                        best_letter = letter
                elif lp < ap and best_letter is None:
                    # Cross-page: text on next page, label on previous
                    best_letter = letter

            if best_letter and best_letter in ans_dict:
                existing = ans_dict[best_letter]
                if existing:
                    ans_dict[best_letter] = existing + " " + text
                else:
                    ans_dict[best_letter] = text

        # Find correct answer (check all pages in cluster)
        correct = None
        best_dist = float("inf")
        for cp, cy, letter in corrects:
            if cp in cluster_pages:
                for lp, ly, _ in cluster:
                    if lp == cp:
                        dist = abs(cy - ly)
                        if dist < best_dist and dist < 100:
                            best_dist = dist
                            correct = letter

        q = {
            "kategoria": kategoria,
            "podkategoria": None,
            "poziom": None,
            "tematyka": tematyka,
            "nr_pytania": best_qnum,
            "typ_pytania": "testowe",
            "pytanie": best_qtext,
            "odp_a": ans_dict.get("A"),
            "odp_b": ans_dict.get("B"),
            "odp_c": ans_dict.get("C"),
            "odp_d": ans_dict.get("D"),
            "poprawna_odpowiedz": correct,
            "poprawna_odpowiedz_tekst": ans_dict.get(correct) if correct else None,
            "zrodlo_pliku": filepath,
        }
        questions.append(q)

    return questions


def tematyka_z_nazwy(filename):
    base = os.path.splitext(filename)[0]
    base = re.sub(r"kapitan żeglugi wielkiej-", "", base, flags=re.IGNORECASE)
    parts = re.split(r"[-–]", base)
    if len(parts) >= 3:
        return parts[2].strip()
    return base


def run_format2(conn):
    base = BASE_DIR
    kapitan_path = os.path.join(base, "Kapitan_żeglugi_wielkiej_pytania")

    total = 0
    if os.path.isdir(kapitan_path):
        pdfs = []
        for root, dirs, files in os.walk(kapitan_path):
            for f in files:
                if f.lower().endswith(".pdf"):
                    pdfs.append(os.path.join(root, f))

        for pdf in sorted(pdfs):
            rel = os.path.relpath(pdf, base)
            if is_file_parsed(conn, rel):
                continue

            filename = os.path.basename(pdf)
            tematyka = tematyka_z_nazwy(filename)
            kategoria = "Kapitan żeglugi wielkiej"

            print(f"  Parsuję PDF: {rel}")
            questions = parse_kapitan(pdf, kategoria, tematyka)
            if questions:
                n = insert_questions(conn, questions)
                mark_file_parsed(conn, rel, "format2", n)
                total += n
                print(f"    → {n} pytań")
            else:
                print(f"    → 0 pytań (błąd parsowania?)")

    return total


if __name__ == "__main__":
    conn = get_connection()
    n = run_format2(conn)
    print(f"\nFormat 2: dodano {n} pytań")
    conn.close()
