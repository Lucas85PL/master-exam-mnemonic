"""
Review tool - przeglądanie pytań z podglądem PDF.
Lewy panel: szczegóły pytania (edycja). Prawy panel: podgląd PDF.
Nawigacja: DALEJ/WSTECZ. Flagowanie: OK/BŁĄD. Usuwanie: przycisk / klawisz Delete.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import os
import re
import fitz
from PIL import Image, ImageTk

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "questions.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


class ReviewApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Review Pytań — weryfikacja z PDF")
        self.root.geometry("1600x900")
        self.root.minsize(1200, 600)

        self.conn = get_connection()
        self.current_id = None
        self.editing = False
        self.question_list = []
        self.current_index = -1

        # PDF state
        self.pdf_doc = None
        self.pdf_path = None
        self.pdf_page_num = 0
        self.pdf_zoom = 1.0
        self.pdf_offset_x = 0
        self.pdf_offset_y = 0
        self.pdf_highlight_rect = None
        self._drag_start = None

        self.selecting = False
        self.sel_start_x = None
        self.sel_start_y = None
        self.sel_rect_id = None
        self.selected_text = ""
        self.page_text_items = []

        self._build_ui()
        self._load_filters()
        self._refresh_list()
        self.root.bind("<Delete>", self._on_delete_key)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── UI ────────────────────────────────────────────

    def _build_ui(self):
        # Top bar: filters
        top = ttk.Frame(self.root, padding=5)
        top.pack(fill=tk.X)

        ttk.Label(top, text="Kategoria:").pack(side=tk.LEFT)
        self.filter_kat = ttk.Combobox(top, state="readonly", width=22)
        self.filter_kat.pack(side=tk.LEFT, padx=(2, 10))
        self.filter_kat.bind("<<ComboboxSelected>>", lambda e: self._refresh_list())

        ttk.Label(top, text="Podkategoria:").pack(side=tk.LEFT)
        self.filter_pod = ttk.Combobox(top, state="readonly", width=22)
        self.filter_pod.pack(side=tk.LEFT, padx=(2, 10))
        self.filter_pod.bind("<<ComboboxSelected>>", lambda e: self._refresh_list())

        self.var_anki = tk.BooleanVar(value=False)
        ttk.Checkbutton(top, text="Pokaż Anki", variable=self.var_anki,
                        command=self._refresh_list).pack(side=tk.LEFT, padx=(10, 20))

        ttk.Label(top, text="Tematyka:").pack(side=tk.LEFT)
        self.filter_tem = ttk.Combobox(top, state="readonly", width=18)
        self.filter_tem.pack(side=tk.LEFT, padx=(2, 10))
        self.filter_tem.bind("<<ComboboxSelected>>", lambda e: self._refresh_list())

        self.lbl_status = ttk.Label(top, text="", foreground="gray")
        self.lbl_status.pack(side=tk.RIGHT, padx=5)

        # Main area: left detail + right PDF
        paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))

        # --- LEFT PANEL (detail) ---
        left = ttk.Frame(paned)
        paned.add(left, weight=1)

        detail_canvas = tk.Canvas(left, highlightthickness=0)
        detail_scroll = ttk.Scrollbar(left, orient=tk.VERTICAL, command=detail_canvas.yview)
        self.detail_frame = ttk.Frame(detail_canvas)
        self.detail_frame.bind("<Configure>",
                               lambda e: detail_canvas.configure(scrollregion=detail_canvas.bbox("all")))
        detail_canvas.create_window((0, 0), window=self.detail_frame, anchor="nw", tags="df")
        detail_canvas.configure(yscrollcommand=detail_scroll.set)
        detail_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        detail_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        def _resize_canvas(event):
            detail_canvas.itemconfig("df", width=event.width)
        detail_canvas.bind("<Configure>", _resize_canvas)

        def _mousewheel(event):
            detail_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        detail_canvas.bind("<MouseWheel>", _mousewheel)

        self._build_detail_fields()

        # --- RIGHT PANEL (PDF) ---
        right = ttk.Frame(paned)
        paned.add(right, weight=1)

        self.pdf_canvas = tk.Canvas(right, bg="#333333", highlightthickness=0)
        self.pdf_canvas.pack(fill=tk.BOTH, expand=True)

        self.lbl_pdf_hint = ttk.Label(
            right,
            text="Scroll = zoom  |  Drag = przesuń  |  Ctrl+drag = zaznacz  |  Delete = usuń z bazy",
            foreground="gray",
            font=("", 8),
        )
        self.lbl_pdf_hint.pack(anchor="e", padx=5)

        self.pdf_canvas.bind("<MouseWheel>", self._pdf_zoom)
        self.pdf_canvas.bind("<ButtonPress-1>", self._pdf_drag_start)
        self.pdf_canvas.bind("<B1-Motion>", self._pdf_drag_move)
        self.pdf_canvas.bind("<ButtonRelease-1>", self._pdf_drag_end)
        self.pdf_canvas.bind("<Control-c>", self._copy_selection)
        self.pdf_canvas.bind("<Control-C>", self._copy_selection)

        # --- BOTTOM BAR ---
        bottom = ttk.Frame(self.root, padding=5)
        bottom.pack(fill=tk.X)

        self.btn_back = ttk.Button(bottom, text="◀  WSTECZ", command=lambda: self._navigate(-1))
        self.btn_back.pack(side=tk.LEFT, padx=3)

        ttk.Separator(bottom, orient=tk.VERTICAL).pack(side=tk.LEFT, padx=10, fill=tk.Y)

        self.btn_ok = ttk.Button(bottom, text="✔  OK", command=lambda: self._flag("ok"))
        self.btn_ok.pack(side=tk.LEFT, padx=3)

        self.btn_error = ttk.Button(bottom, text="✘  BŁĄD", command=lambda: self._flag("error"))
        self.btn_error.pack(side=tk.LEFT, padx=3)

        ttk.Separator(bottom, orient=tk.VERTICAL).pack(side=tk.LEFT, padx=10, fill=tk.Y)

        self.btn_delete = tk.Button(
            bottom,
            text="Usuń z Bazy",
            command=self._delete_question,
            bg="#c0392b",
            fg="white",
            activebackground="#922b21",
            activeforeground="white",
            font=("", 10, "bold"),
            padx=10,
            pady=2,
            cursor="hand2",
        )
        self.btn_delete.pack(side=tk.LEFT, padx=3)

        ttk.Separator(bottom, orient=tk.VERTICAL).pack(side=tk.LEFT, padx=10, fill=tk.Y)

        self.btn_next = ttk.Button(bottom, text="DALEJ  ▶", command=lambda: self._navigate(1))
        self.btn_next.pack(side=tk.LEFT, padx=3)

        self.lbl_nav = ttk.Label(bottom, text="", font=("", 9))
        self.lbl_nav.pack(side=tk.RIGHT, padx=10)

    def _build_detail_fields(self):
        fields = [
            ("Kategoria:", "kategoria", 40),
            ("Podkategoria:", "podkategoria", 40),
            ("Poziom:", "poziom", 40),
            ("Tematyka:", "tematyka", 40),
            ("Nr pytania:", "nr_pytania", 10),
            ("Typ pytania:", "typ_pytania", 15),
            ("Źródło:", "zrodlo_pliku", 60),
        ]
        self.field_vars = {}
        self.field_widgets = {}
        row = 0
        for label, key, width in fields:
            ttk.Label(self.detail_frame, text=label, font=("", 9, "bold")).grid(
                row=row, column=0, sticky="e", padx=(5, 2), pady=1)
            var = tk.StringVar()
            entry = ttk.Entry(self.detail_frame, textvariable=var, width=width, state="readonly")
            entry.grid(row=row, column=1, sticky="ew", padx=(2, 10), pady=1)
            self.field_vars[key] = var
            self.field_widgets[key] = entry
            row += 1

        ttk.Separator(self.detail_frame, orient=tk.HORIZONTAL).grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=5)
        row += 1

        ttk.Label(self.detail_frame, text="Pytanie:", font=("", 10, "bold")).grid(
            row=row, column=0, columnspan=2, sticky="w", padx=5, pady=(5, 2))
        row += 1

        self.txt_pytanie = tk.Text(self.detail_frame, height=5, wrap=tk.WORD,
                                   state=tk.DISABLED, font=("", 10))
        self.txt_pytanie.grid(row=row, column=0, columnspan=2, sticky="ew", padx=5, pady=(0, 5))
        row += 1

        ttk.Label(self.detail_frame, text="Odpowiedzi:", font=("", 10, "bold")).grid(
            row=row, column=0, columnspan=2, sticky="w", padx=5, pady=(5, 2))
        row += 1

        self.answer_widgets = {}
        for letter in ["A", "B", "C", "D"]:
            ttk.Label(self.detail_frame, text=f"  {letter}:", font=("", 9, "bold")).grid(
                row=row, column=0, sticky="ne", padx=5, pady=1)
            w = tk.Text(self.detail_frame, height=3, wrap=tk.WORD,
                        state=tk.DISABLED, font=("", 10))
            w.grid(row=row, column=1, sticky="ew", padx=(2, 10), pady=1)
            self.answer_widgets[letter] = w
            row += 1

        ttk.Separator(self.detail_frame, orient=tk.HORIZONTAL).grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=5)
        row += 1

        correct_frame = ttk.Frame(self.detail_frame)
        correct_frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
        ttk.Label(correct_frame, text="Poprawna odpowiedź:", font=("", 10, "bold")).pack(side=tk.LEFT)
        self.var_correct = tk.StringVar()
        self.correct_combo = ttk.Combobox(correct_frame, textvariable=self.var_correct,
                                          values=["A", "B", "C", "D"], state="readonly", width=5)
        self.correct_combo.pack(side=tk.LEFT, padx=10)
        self.lbl_correct_text = ttk.Label(correct_frame, text="", font=("", 9))
        self.lbl_correct_text.pack(side=tk.LEFT, padx=10)

        # Review status indicator
        row += 1
        self.lbl_review_status = ttk.Label(self.detail_frame, text="", font=("", 11, "bold"))
        self.lbl_review_status.grid(row=row, column=0, columnspan=2, sticky="ew", padx=5, pady=5)

        self.detail_frame.columnconfigure(1, weight=1)

        # Edit controls
        row += 1
        edit_frame = ttk.Frame(self.detail_frame)
        edit_frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
        self.btn_edit = ttk.Button(edit_frame, text="Edytuj", command=self._start_edit)
        self.btn_edit.pack(side=tk.LEFT, padx=3)
        self.btn_save = ttk.Button(edit_frame, text="Zapisz", command=self._save_question, state=tk.DISABLED)
        self.btn_save.pack(side=tk.LEFT, padx=3)
        self.btn_cancel = ttk.Button(edit_frame, text="Anuluj", command=self._cancel_edit, state=tk.DISABLED)
        self.btn_cancel.pack(side=tk.LEFT, padx=3)

    # ── FILTERS ──────────────────────────────────────

    def _load_filters(self):
        c = self.conn.cursor()
        c.execute("SELECT DISTINCT kategoria FROM questions WHERE kategoria != 'Chief Officer' ORDER BY kategoria")
        self.filter_kat["values"] = [""] + [r[0] for r in c.fetchall()]

        c.execute("SELECT DISTINCT podkategoria FROM questions WHERE podkategoria IS NOT NULL ORDER BY podkategoria")
        self.filter_pod["values"] = [""] + [r[0] for r in c.fetchall()]

        c.execute("SELECT DISTINCT tematyka FROM questions ORDER BY tematyka")
        self.filter_tem["values"] = [""] + [r[0] for r in c.fetchall()]

    def _get_filter_sql(self):
        conditions = []
        params = []
        if self.filter_kat.get():
            conditions.append("kategoria = ?")
            params.append(self.filter_kat.get())
        if self.filter_pod.get():
            conditions.append("podkategoria = ?")
            params.append(self.filter_pod.get())
        if self.filter_tem.get():
            conditions.append("tematyka = ?")
            params.append(self.filter_tem.get())
        if not self.var_anki.get():
            conditions.append("kategoria != 'Chief Officer'")
            conditions.append("zrodlo_pliku NOT LIKE '%colpkg%'")

        # Niezweryfikowane lub oznaczone błędem (bez OK)
        conditions.append(
            "(review_status IS NULL OR review_status = '' OR review_status = 'error')"
        )

        if conditions:
            return "WHERE " + " AND ".join(conditions), params
        return "", []

    def _refresh_list(self):
        where, params = self._get_filter_sql()
        sql = f"""SELECT id FROM questions {where}
                  ORDER BY COALESCE(nr_pytania, id), id"""
        c = self.conn.cursor()
        c.execute(sql, params)
        self.question_list = [r[0] for r in c.fetchall()]

        if self.question_list:
            self.current_index = 0
            self._load_current()
        else:
            self.current_index = -1
            self._clear_all()

    # ── NAVIGATION ───────────────────────────────────

    def _navigate(self, direction):
        if not self.question_list:
            return
        new_idx = self.current_index + direction
        if 0 <= new_idx < len(self.question_list):
            self.current_index = new_idx
            self._load_current()

    def _load_current(self):
        if not self.question_list or self.current_index < 0:
            return
        qid = self.question_list[self.current_index]
        self._load_question(qid)
        self._update_nav_label()

    def _update_nav_label(self):
        total = len(self.question_list)
        cur = self.current_index + 1 if self.current_index >= 0 else 0
        self.lbl_nav.config(text=f"{cur} / {total}")

        # Enable/disable nav buttons
        self.btn_back.config(state=tk.NORMAL if self.current_index > 0 else tk.DISABLED)
        self.btn_next.config(state=tk.NORMAL if self.current_index < total - 1 else tk.DISABLED)

    # ── QUESTION LOADING ─────────────────────────────

    def _load_question(self, qid):
        if self.editing:
            self._cancel_edit()

        self.current_id = qid
        c = self.conn.cursor()
        c.execute("SELECT * FROM questions WHERE id = ?", (qid,))
        row = c.fetchone()
        if not row:
            return

        # Left panel
        for key in ["kategoria", "podkategoria", "poziom", "tematyka",
                     "nr_pytania", "typ_pytania", "zrodlo_pliku"]:
            val = row[key]
            self.field_vars[key].set(str(val) if val is not None else "")

        self.txt_pytanie.config(state=tk.NORMAL)
        self.txt_pytanie.delete("1.0", tk.END)
        self.txt_pytanie.insert("1.0", row["pytanie"] or "")
        self.txt_pytanie.config(state=tk.DISABLED)

        for letter in ["A", "B", "C", "D"]:
            key = f"odp_{letter.lower()}"
            w = self.answer_widgets[letter]
            w.config(state=tk.NORMAL)
            w.delete("1.0", tk.END)
            w.insert("1.0", row[key] or "")
            w.config(state=tk.DISABLED)

        self.var_correct.set(row["poprawna_odpowiedz"] or "")
        self._update_correct_text()

        # Review status badge
        status = row["review_status"]
        if status == "ok":
            self.lbl_review_status.config(text="✔ ZWERYFIKOWANE", foreground="green")
        elif status == "error":
            self.lbl_review_status.config(text="✘ BŁĄD — do poprawy", foreground="red")
        else:
            self.lbl_review_status.config(text="● Niezweryfikowane", foreground="orange")

        self._set_fields_enabled(False)
        self._update_button_states()

        # Right panel: PDF
        self._load_pdf(row["pytanie"] or "", row["zrodlo_pliku"] or "")

    def _update_correct_text(self):
        letter = self.var_correct.get()
        if letter and letter in self.answer_widgets:
            text = self.answer_widgets[letter].get("1.0", "end-1c").strip()
            self.lbl_correct_text.config(text=text[:80] + ("..." if len(text) > 80 else ""))
        else:
            self.lbl_correct_text.config(text="")

    def _clear_all(self):
        self.current_id = None
        for key in self.field_vars:
            self.field_vars[key].set("")
        self.txt_pytanie.config(state=tk.NORMAL)
        self.txt_pytanie.delete("1.0", tk.END)
        self.txt_pytanie.config(state=tk.DISABLED)
        for w in self.answer_widgets.values():
            w.config(state=tk.NORMAL)
            w.delete("1.0", tk.END)
            w.config(state=tk.DISABLED)
        self.var_correct.set("")
        self.lbl_correct_text.config(text="")
        self.lbl_review_status.config(text="")
        self.pdf_canvas.delete("all")
        self.lbl_nav.config(text="0 / 0")

    # ── PDF ──────────────────────────────────────────

    @staticmethod
    def _clean_for_search(text):
        """Clean text for PDF search - remove special chars but keep content."""
        text = re.sub(r"[^\w\s\-.,:;!?()ąćęłńóśźżĄĆĘŁŃÓŚŹŻ]", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _load_pdf(self, question_text, pdf_path):
        self.pdf_canvas.delete("all")
        self.pdf_highlight_rect = None

        if not pdf_path or not os.path.isfile(pdf_path):
            self.pdf_canvas.create_text(400, 300, text="Brak PDF\n(pytanie z Anki lub plik nie istnieje)",
                                        fill="gray", font=("", 14), anchor="center")
            if self.pdf_doc:
                self.pdf_doc.close()
                self.pdf_doc = None
                self.pdf_path = None
            return

        # Open PDF if changed
        if self.pdf_path != pdf_path:
            if self.pdf_doc:
                self.pdf_doc.close()
            try:
                self.pdf_doc = fitz.open(pdf_path)
                self.pdf_path = pdf_path
            except Exception:
                self.pdf_canvas.create_text(400, 300, text="Nie można otworzyć PDF",
                                            fill="red", font=("", 14))
                return

        # Search for question text in PDF
        search_text = self._clean_for_search(question_text)
        found_page = 0
        found_rect = None

        if search_text and len(search_text) > 5:
            for pn in range(len(self.pdf_doc)):
                page = self.pdf_doc[pn]
                # Try full text first, then shorter fragments
                for fragment in [search_text[:80], search_text[:50], search_text[:30]]:
                    if len(fragment) < 5:
                        continue
                    results = page.search_for(fragment)
                    if results:
                        found_page = pn
                        found_rect = results[0]
                        break
                if found_rect:
                    break

        self.pdf_page_num = found_page
        self.pdf_zoom = 1.0
        self.pdf_offset_x = 0
        self.pdf_offset_y = 0
        self.pdf_highlight_rect = found_rect
        self._render_pdf_page()

    def _render_pdf_page(self):
        if not self.pdf_doc:
            return

        self.pdf_canvas.delete("all")
        self.sel_rect_id = None
        self.page_text_items = []
        page = self.pdf_doc[self.pdf_page_num]

        # Render at current zoom
        mat = fitz.Matrix(self.pdf_zoom, self.pdf_zoom)
        pix = page.get_pixmap(matrix=mat)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        self._pdf_image = ImageTk.PhotoImage(img)

        img_w = self._pdf_image.width()
        img_h = self._pdf_image.height()

        # Center in canvas with offset
        cx = (self.pdf_canvas.winfo_width() - img_w) // 2 + self.pdf_offset_x
        cy = (self.pdf_canvas.winfo_height() - img_h) // 2 + self.pdf_offset_y

        self.pdf_canvas.create_image(cx, cy, anchor=tk.NW, image=self._pdf_image,
                                     tags="pdf_img")

        # Draw highlight rectangle if found
        if self.pdf_highlight_rect:
            r = self.pdf_highlight_rect
            hr_x1 = cx + r.x0 * self.pdf_zoom
            hr_y1 = cy + r.y0 * self.pdf_zoom
            hr_x2 = cx + r.x1 * self.pdf_zoom
            hr_y2 = cy + r.y1 * self.pdf_zoom
            self.pdf_canvas.create_rectangle(hr_x1, hr_y1, hr_x2, hr_y2,
                                             outline="red", width=2, tags="highlight")
            # Scroll canvas to center the highlight
            target_y = hr_y1 - self.pdf_canvas.winfo_height() // 2
            self.pdf_canvas.yview_moveto(0)

        # Extract text positions for selection
        text_dict = page.get_text("dict")
        for block in text_dict.get("blocks", []):
            if "lines" not in block:
                continue
            for line in block["lines"]:
                line_text = "".join(s["text"] for s in line["spans"])
                if not line_text.strip():
                    continue
                bbox = line["bbox"]
                tx0 = cx + bbox[0] * self.pdf_zoom
                ty0 = cy + bbox[1] * self.pdf_zoom
                tx1 = cx + bbox[2] * self.pdf_zoom
                ty1 = cy + bbox[3] * self.pdf_zoom
                self.page_text_items.append((line_text, tx0, ty0, tx1, ty1))

        self.lbl_pdf_hint.config(
            text="Scroll = zoom  |  Drag = przesuń  |  Ctrl+drag = zaznacz",
            foreground="gray"
        )

    def _pdf_zoom(self, event):
        if not self.pdf_doc:
            return
        if event.delta > 0:
            self.pdf_zoom *= 1.15
        else:
            self.pdf_zoom /= 1.15
        self.pdf_zoom = max(0.3, min(5.0, self.pdf_zoom))
        self.selected_text = ""
        self.lbl_pdf_hint.config(
            text="Scroll = zoom  |  Drag = przesuń  |  Ctrl+drag = zaznacz",
            foreground="gray"
        )
        self._render_pdf_page()

    def _pdf_drag_start(self, event):
        if (event.state & 0x0004) and self.pdf_doc:
            self.selecting = True
            self.sel_start_x = event.x
            self.sel_start_y = event.y
        else:
            self._drag_start = (event.x, event.y)

    def _pdf_drag_move(self, event):
        if self.selecting:
            x = event.x
            y = event.y
            self._draw_selection_rect(self.sel_start_x, self.sel_start_y, x, y)
        elif self._drag_start and self.pdf_doc:
            dx = event.x - self._drag_start[0]
            dy = event.y - self._drag_start[1]
            self.pdf_offset_x += dx
            self.pdf_offset_y += dy
            self._drag_start = (event.x, event.y)
            self._render_pdf_page()

    def _pdf_drag_end(self, event):
        if self.selecting:
            self.selecting = False
            if self.sel_rect_id:
                text = self._text_from_rect(
                    self.sel_start_x, self.sel_start_y, event.x, event.y
                )
                if text:
                    self.root.clipboard_clear()
                    self.root.clipboard_append(text)
                    self.selected_text = text
                    lines = text.count("\n") + 1
                    self.lbl_pdf_hint.config(
                        text=f"Skopiowano {lines} linii do schowka",
                        foreground="green"
                    )
            return
        self._drag_start = None

    def _copy_selection(self, event=None):
        if self.selected_text:
            self.root.clipboard_clear()
            self.root.clipboard_append(self.selected_text)
            lines = self.selected_text.count("\n") + 1
            self.lbl_pdf_hint.config(
                text=f"Skopiowano {lines} linii do schowka",
                foreground="green"
            )

    def _draw_selection_rect(self, x0, y0, x1, y1):
        if self.sel_rect_id:
            self.pdf_canvas.delete(self.sel_rect_id)
        self.sel_rect_id = self.pdf_canvas.create_rectangle(
            x0, y0, x1, y1,
            outline="#3399ff", width=2, dash=(5, 3),
            fill="#3399ff", stipple="gray50", tags="selection"
        )

    def _text_from_rect(self, x0, y0, x1, y1):
        if x0 > x1:
            x0, x1 = x1, x0
        if y0 > y1:
            y0, y1 = y1, y0
        selected = []
        for text, tx0, ty0, tx1, ty1 in self.page_text_items:
            if tx0 >= x0 and tx1 <= x1 and ty0 >= y0 and ty1 <= y1:
                selected.append((ty0, text))
        selected.sort(key=lambda t: t[0])
        return "\n".join(t[1] for t in selected)

    # ── FLAGGING ─────────────────────────────────────

    def _flag(self, status):
        if not self.current_id:
            return
        c = self.conn.cursor()
        c.execute("UPDATE questions SET review_status = ? WHERE id = ?",
                  (status, self.current_id))
        self.conn.commit()

        color = "green" if status == "ok" else "red"
        text = "✔ ZWERYFIKOWANE" if status == "ok" else "✘ BŁĄD — do poprawy"
        self.lbl_review_status.config(text=text, foreground=color)
        self.lbl_status.config(text=f"Oflagowano jako {status.upper()}", foreground=color)

        # Auto-advance to next question
        if self.current_index < len(self.question_list) - 1:
            self._navigate(1)

    def _on_delete_key(self, event=None):
        if self.editing:
            return
        focus = self.root.focus_get()
        if isinstance(focus, tk.Text):
            return
        self._delete_question()
        return "break"

    def _delete_question(self):
        if not self.current_id:
            return
        if self.editing:
            messagebox.showwarning("Usuwanie", "Zakończ edycję przed usunięciem.")
            return

        qid = self.current_id
        nr = self.field_vars["nr_pytania"].get()
        preview = self.txt_pytanie.get("1.0", "end-1c").strip()[:80]
        msg = (
            f"Na pewno usunąć pytanie z bazy?\n\n"
            f"ID: {qid}\n"
            f"Nr: {nr or '—'}\n"
            f"{preview}…\n\n"
            f"Tej operacji nie można cofnąć."
        )
        if not messagebox.askyesno("Usuń z bazy", msg, icon="warning"):
            return

        c = self.conn.cursor()
        c.execute("DELETE FROM questions WHERE id = ?", (qid,))
        self.conn.commit()

        idx = self.current_index
        if 0 <= idx < len(self.question_list):
            self.question_list.pop(idx)

        self.lbl_status.config(
            text=f"Usunięto pytanie ID={qid} z bazy.",
            foreground="#c0392b",
        )

        if not self.question_list:
            self.current_index = -1
            self._clear_all()
            self._update_button_states()
            return

        if idx >= len(self.question_list):
            self.current_index = len(self.question_list) - 1
        else:
            self.current_index = idx
        self._load_current()

    # ── EDIT ─────────────────────────────────────────

    def _set_fields_enabled(self, enabled):
        state = "normal" if enabled else "readonly"
        for w in self.field_widgets.values():
            w.config(state=state)
        self.txt_pytanie.config(state=tk.NORMAL if enabled else tk.DISABLED)
        for w in self.answer_widgets.values():
            w.config(state=tk.NORMAL if enabled else tk.DISABLED)
        self.correct_combo.config(state="readonly" if enabled else tk.DISABLED)

    def _update_button_states(self):
        if self.editing:
            self.btn_edit.config(state=tk.DISABLED)
            self.btn_save.config(state=tk.NORMAL)
            self.btn_cancel.config(state=tk.NORMAL)
            self.btn_ok.config(state=tk.DISABLED)
            self.btn_error.config(state=tk.DISABLED)
            self.btn_delete.config(state=tk.DISABLED)
            self.btn_back.config(state=tk.DISABLED)
            self.btn_next.config(state=tk.DISABLED)
        else:
            has_q = self.current_id is not None
            self.btn_edit.config(state=tk.NORMAL if has_q else tk.DISABLED)
            self.btn_save.config(state=tk.DISABLED)
            self.btn_cancel.config(state=tk.DISABLED)
            self.btn_ok.config(state=tk.NORMAL if has_q else tk.DISABLED)
            self.btn_error.config(state=tk.NORMAL if has_q else tk.DISABLED)
            self.btn_delete.config(state=tk.NORMAL if has_q else tk.DISABLED)
            self._update_nav_label()

    def _start_edit(self):
        if not self.current_id:
            return
        self.editing = True
        self._set_fields_enabled(True)
        self._update_button_states()
        self.lbl_status.config(text="Tryb edycji", foreground="blue")

    def _cancel_edit(self):
        self.editing = False
        if self.current_id:
            self._load_question(self.current_id)
        self._update_button_states()
        self.lbl_status.config(text="", foreground="gray")

    def _save_question(self):
        pytanie = self.txt_pytanie.get("1.0", "end-1c").strip()
        if not pytanie:
            messagebox.showwarning("Brak pytania", "Treść pytania nie może być pusta.")
            return

        data = {
            "kategoria": self.field_vars["kategoria"].get().strip() or None,
            "podkategoria": self.field_vars["podkategoria"].get().strip() or None,
            "poziom": self.field_vars["poziom"].get().strip() or None,
            "tematyka": self.field_vars["tematyka"].get().strip() or "Inne",
            "nr_pytania": self._parse_int(self.field_vars["nr_pytania"].get()),
            "typ_pytania": self.field_vars["typ_pytania"].get().strip() or "testowe",
            "pytanie": pytanie,
            "odp_a": self.answer_widgets["A"].get("1.0", "end-1c").strip() or None,
            "odp_b": self.answer_widgets["B"].get("1.0", "end-1c").strip() or None,
            "odp_c": self.answer_widgets["C"].get("1.0", "end-1c").strip() or None,
            "odp_d": self.answer_widgets["D"].get("1.0", "end-1c").strip() or None,
            "poprawna_odpowiedz": self.var_correct.get().strip() or None,
            "poprawna_odpowiedz_tekst": None,
            "zrodlo_pliku": self.field_vars["zrodlo_pliku"].get().strip() or "gui",
        }

        letter = data["poprawna_odpowiedz"]
        if data["typ_pytania"] == "testowe" and letter and letter.upper() in ["A", "B", "C", "D"]:
            key = f"odp_{letter.lower()}"
            data["poprawna_odpowiedz_tekst"] = data.get(key)

        c = self.conn.cursor()
        c.execute("""UPDATE questions SET
            kategoria=?, podkategoria=?, poziom=?, tematyka=?,
            nr_pytania=?, typ_pytania=?, pytanie=?,
            odp_a=?, odp_b=?, odp_c=?, odp_d=?,
            poprawna_odpowiedz=?, poprawna_odpowiedz_tekst=?, zrodlo_pliku=?
            WHERE id=?""", (
            data["kategoria"], data["podkategoria"], data["poziom"], data["tematyka"],
            data["nr_pytania"], data["typ_pytania"], data["pytanie"],
            data["odp_a"], data["odp_b"], data["odp_c"], data["odp_d"],
            data["poprawna_odpowiedz"], data["poprawna_odpowiedz_tekst"],
            data["zrodlo_pliku"], self.current_id
        ))
        self.conn.commit()

        self.editing = False
        self._set_fields_enabled(False)
        self.lbl_status.config(text=f"Zapisano ID={self.current_id}", foreground="green")
        self._update_button_states()

    @staticmethod
    def _parse_int(val):
        try:
            return int(val.strip())
        except (ValueError, AttributeError):
            return None

    def _on_close(self):
        if self.editing:
            if not messagebox.askyesno("Niezapisane zmiany",
                                       "Masz niezapisane zmiany. Wyjść?"):
                return
        if self.pdf_doc:
            self.pdf_doc.close()
        self.conn.close()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = ReviewApp(root)
    root.mainloop()
