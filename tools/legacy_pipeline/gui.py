"""
GUI do przeglądania, edycji, dodawania i usuwania pytań z bazy questions.db.
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
import os
import shutil

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "questions.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


class QuestionBrowser:
    def __init__(self, root):
        self.root = root
        self.root.title("Przeglądarka Pytań Egzaminacyjnych")
        self.root.geometry("1400x850")
        self.root.minsize(1100, 600)

        self.conn = get_connection()
        self.current_id = None
        self.editing = False
        self.all_data = []

        self._build_ui()
        self._load_filters()
        self._refresh_list()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        # Styles
        style = ttk.Style()
        style.configure("Header.TLabel", font=("", 11, "bold"))
        style.configure("Answer.TLabel", font=("", 10))

        # Main paned window
        paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left panel - filters + list
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=1)

        # Filters
        filter_frame = ttk.LabelFrame(left_frame, text="Filtry", padding=5)
        filter_frame.pack(fill=tk.X, padx=2, pady=2)

        # Row 1: Kategoria + Podkategoria
        row1 = ttk.Frame(filter_frame)
        row1.pack(fill=tk.X, pady=2)
        ttk.Label(row1, text="Kategoria:", width=12).pack(side=tk.LEFT)
        self.filter_kat = ttk.Combobox(row1, state="readonly", width=25)
        self.filter_kat.pack(side=tk.LEFT, padx=(0, 10))
        self.filter_kat.bind("<<ComboboxSelected>>", self._on_filter_change)
        ttk.Label(row1, text="Podkategoria:", width=12).pack(side=tk.LEFT)
        self.filter_pod = ttk.Combobox(row1, state="readonly", width=25)
        self.filter_pod.pack(side=tk.LEFT)
        self.filter_pod.bind("<<ComboboxSelected>>", self._on_filter_change)

        # Row 2: Tematyka + Szukaj
        row2 = ttk.Frame(filter_frame)
        row2.pack(fill=tk.X, pady=2)
        ttk.Label(row2, text="Tematyka:", width=12).pack(side=tk.LEFT)
        self.filter_tem = ttk.Combobox(row2, state="readonly", width=25)
        self.filter_tem.pack(side=tk.LEFT, padx=(0, 10))
        self.filter_tem.bind("<<ComboboxSelected>>", self._on_filter_change)
        ttk.Label(row2, text="Szukaj:", width=12).pack(side=tk.LEFT)
        self.filter_search = ttk.Entry(row2, width=28)
        self.filter_search.pack(side=tk.LEFT)
        self.filter_search.bind("<Return>", lambda e: self._refresh_list())
        ttk.Button(row2, text="Szukaj", command=self._refresh_list, width=8).pack(side=tk.LEFT, padx=5)

        # Row 3: Clear + counter
        row3 = ttk.Frame(filter_frame)
        row3.pack(fill=tk.X, pady=2)
        ttk.Button(row3, text="Wyczyść filtry", command=self._clear_filters).pack(side=tk.LEFT, padx=2)
        self.lbl_count = ttk.Label(row3, text="")
        self.lbl_count.pack(side=tk.RIGHT, padx=5)

        # Question list
        list_frame = ttk.Frame(left_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        columns = ("id", "nr", "kat", "podkat", "temat", "pytanie", "typ")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings",
                                 selectmode="extended")
        self.tree.heading("id", text="ID", command=lambda: self._sort_by("id"))
        self.tree.heading("nr", text="Nr", command=lambda: self._sort_by("nr"))
        self.tree.heading("kat", text="Kategoria")
        self.tree.heading("podkat", text="Podkategoria")
        self.tree.heading("temat", text="Tematyka")
        self.tree.heading("pytanie", text="Pytanie")
        self.tree.heading("typ", text="Typ")
        self.tree.column("id", width=40, stretch=False)
        self.tree.column("nr", width=35, stretch=False)
        self.tree.column("kat", width=100, stretch=False)
        self.tree.column("podkat", width=100, stretch=False)
        self.tree.column("temat", width=120, stretch=False)
        self.tree.column("pytanie", width=270)
        self.tree.column("typ", width=60, stretch=False)

        vsb = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        hsb = ttk.Scrollbar(list_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)

        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        # Right panel - detail
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=1)

        # Detail header
        detail_header = ttk.Frame(right_frame)
        detail_header.pack(fill=tk.X, padx=2, pady=(2, 5))
        self.lbl_detail_title = ttk.Label(detail_header, text="Szczegóły pytania",
                                          font=("", 12, "bold"))
        self.lbl_detail_title.pack(side=tk.LEFT)
        self.lbl_detail_id = ttk.Label(detail_header, text="", font=("", 10))
        self.lbl_detail_id.pack(side=tk.RIGHT)

        # Scrollable detail area
        detail_canvas = tk.Canvas(right_frame, highlightthickness=0)
        detail_scroll = ttk.Scrollbar(right_frame, orient=tk.VERTICAL, command=detail_canvas.yview)
        self.detail_frame = ttk.Frame(detail_canvas)
        self.detail_frame.bind("<Configure>",
                               lambda e: detail_canvas.configure(scrollregion=detail_canvas.bbox("all")))
        detail_canvas.create_window((0, 0), window=self.detail_frame, anchor="nw",
                                    tags="detail_frame")
        detail_canvas.configure(yscrollcommand=detail_scroll.set)
        detail_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        detail_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        def _on_mousewheel(event):
            detail_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        detail_canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # Bind canvas resize
        def _resize_canvas(event):
            detail_canvas.itemconfig("detail_frame", width=event.width)

        detail_canvas.bind("<Configure>", _resize_canvas)

        # Detail fields
        self.detail_widgets = {}
        self._build_detail_fields()

        # Bottom buttons
        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)

        self.btn_edit = ttk.Button(btn_frame, text="Edytuj", command=self._start_edit)
        self.btn_edit.pack(side=tk.LEFT, padx=3)
        self.btn_save = ttk.Button(btn_frame, text="Zapisz", command=self._save_question, state=tk.DISABLED)
        self.btn_save.pack(side=tk.LEFT, padx=3)
        self.btn_cancel = ttk.Button(btn_frame, text="Anuluj", command=self._cancel_edit, state=tk.DISABLED)
        self.btn_cancel.pack(side=tk.LEFT, padx=3)
        ttk.Separator(btn_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, padx=8, fill=tk.Y)
        self.btn_add = ttk.Button(btn_frame, text="Dodaj nowe", command=self._add_new)
        self.btn_add.pack(side=tk.LEFT, padx=3)
        self.btn_delete = ttk.Button(btn_frame, text="Usuń", command=self._delete_question)
        self.btn_delete.pack(side=tk.LEFT, padx=3)
        ttk.Separator(btn_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, padx=8, fill=tk.Y)
        self.btn_export = ttk.Button(btn_frame, text="Eksportuj bazę", command=self._export_db)
        self.btn_export.pack(side=tk.LEFT, padx=3)

        status_frame = ttk.Frame(self.root)
        status_frame.pack(fill=tk.X, padx=10, pady=(0, 5))
        self.lbl_status = ttk.Label(status_frame, text="Gotowe.", foreground="gray")
        self.lbl_status.pack(side=tk.LEFT)

    def _build_detail_fields(self):
        """Build the detail form fields."""
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

        # Separator
        ttk.Separator(self.detail_frame, orient=tk.HORIZONTAL).grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=5)
        row += 1

        # Question text
        ttk.Label(self.detail_frame, text="Pytanie:", font=("", 10, "bold")).grid(
            row=row, column=0, columnspan=2, sticky="w", padx=5, pady=(5, 2))
        row += 1

        self.var_pytanie = tk.StringVar()
        self.txt_pytanie = tk.Text(self.detail_frame, height=5, wrap=tk.WORD, state=tk.DISABLED,
                                   font=("", 10))
        self.txt_pytanie.grid(row=row, column=0, columnspan=2, sticky="ew",
                              padx=5, pady=(0, 5))
        row += 1

        # Answer options
        ttk.Label(self.detail_frame, text="Odpowiedzi:", font=("", 10, "bold")).grid(
            row=row, column=0, columnspan=2, sticky="w", padx=5, pady=(5, 2))
        row += 1

        self.answer_vars = {}
        self.answer_widgets = {}
        for letter in ["A", "B", "C", "D"]:
            ttk.Label(self.detail_frame, text=f"  {letter}:", font=("", 9, "bold")).grid(
                row=row, column=0, sticky="ne", padx=5, pady=1)
            self.answer_widgets[letter] = tk.Text(self.detail_frame, height=3, wrap=tk.WORD,
                                                  state=tk.DISABLED, font=("", 10))
            self.answer_widgets[letter].grid(row=row, column=1, sticky="ew",
                                             padx=(2, 10), pady=1)
            row += 1

        # Correct answer
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

        # Flashcard answer (for otwarte questions)
        self.flashcard_frame = ttk.Frame(self.detail_frame)
        self.flashcard_frame.grid(row=row+1, column=0, columnspan=2, sticky="ew", padx=5, pady=(10, 5))
        ttk.Label(self.flashcard_frame, text="Odpowiedź (fiszka):", font=("", 10, "bold")).pack(anchor="w")
        self.txt_flashcard_answer = tk.Text(self.detail_frame, height=5, wrap=tk.WORD,
                                            state=tk.DISABLED, font=("", 10))
        self.txt_flashcard_answer.grid(row=row+2, column=0, columnspan=2, sticky="ew", padx=5, pady=(0, 5))

        self.detail_frame.columnconfigure(1, weight=1)

    def _load_filters(self):
        """Load filter combobox values from DB."""
        c = self.conn.cursor()
        c.execute("SELECT DISTINCT kategoria FROM questions ORDER BY kategoria")
        kat = [r[0] for r in c.fetchall()]
        self.filter_kat["values"] = [""] + kat

        c.execute("SELECT DISTINCT podkategoria FROM questions WHERE podkategoria IS NOT NULL ORDER BY podkategoria")
        pod = [r[0] for r in c.fetchall()]
        self.filter_pod["values"] = [""] + pod

        c.execute("SELECT DISTINCT tematyka FROM questions ORDER BY tematyka")
        tem = [r[0] for r in c.fetchall()]
        self.filter_tem["values"] = [""] + tem

    def _get_filter_sql(self):
        """Build WHERE clause from current filters."""
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
        if self.filter_search.get():
            conditions.append("(pytanie LIKE ? OR odp_a LIKE ? OR odp_b LIKE ? OR odp_c LIKE ? OR odp_d LIKE ?)")
            s = f"%{self.filter_search.get()}%"
            params.extend([s, s, s, s, s])

        if conditions:
            return "WHERE " + " AND ".join(conditions), params
        return "", []

    def _refresh_list(self):
        """Refresh the question list from DB."""
        self.tree.delete(*self.tree.get_children())
        where, params = self._get_filter_sql()
        sql = f"SELECT id, nr_pytania, kategoria, podkategoria, tematyka, pytanie, typ_pytania FROM questions {where} ORDER BY COALESCE(nr_pytania, id), id"
        c = self.conn.cursor()
        c.execute(sql, params)
        self.all_data = c.fetchall()
        for row in self.all_data:
            q = row["pytanie"] or ""
            if len(q) > 80:
                q = q[:80] + "..."
            self.tree.insert("", tk.END, values=(
                row["id"], row["nr_pytania"] or "", row["kategoria"] or "", row["podkategoria"] or "",
                row["tematyka"] or "", q, row["typ_pytania"] or ""
            ))
        self.lbl_count.config(text=f"Znaleziono: {len(self.all_data)}")

    def _on_filter_change(self, event=None):
        self._refresh_list()

    def _clear_filters(self):
        self.filter_kat.set("")
        self.filter_pod.set("")
        self.filter_tem.set("")
        self.filter_search.delete(0, tk.END)
        self._refresh_list()

    def _sort_by(self, col):
        """Sort treeview by column."""
        mapping = {"id": "id", "nr": "nr_pytania", "kat": "kategoria", "podkat": "podkategoria",
                   "temat": "tematyka", "pytanie": "pytanie", "typ": "typ_pytania"}
        dbcol = mapping.get(col, "id")
        reverse = False
        self.all_data = sorted(self.all_data, key=lambda r: (r[dbcol] or "").lower()
                               if isinstance(r[dbcol], str) else r[dbcol] or 0, reverse=reverse)
        self.tree.delete(*self.tree.get_children())
        for row in self.all_data:
            q = row["pytanie"] or ""
            if len(q) > 80:
                q = q[:80] + "..."
            self.tree.insert("", tk.END, values=(
                row["id"], row["nr_pytania"] or "", row["kategoria"] or "", row["podkategoria"] or "",
                row["tematyka"] or "", q, row["typ_pytania"] or ""
            ))

    def _on_select(self, event):
        """Handle question selection from list."""
        sel = self.tree.selection()
        if not sel:
            return

        if len(sel) > 1:
            # Multiple selection - update button states but don't load detail
            self._update_button_states()
            self.lbl_status.config(text=f"Zaznaczono {len(sel)} pytań.", foreground="blue")
            return

        if self.editing:
            if not messagebox.askyesno("Niezapisane zmiany",
                                       "Masz niezapisane zmiany. Porzucić je?"):
                return
            self._cancel_edit()

        item = self.tree.item(sel[0])
        qid = item["values"][0]
        self._load_question(qid)

    def _load_question(self, qid):
        """Load question details into the form."""
        self.current_id = qid
        c = self.conn.cursor()
        c.execute("SELECT * FROM questions WHERE id = ?", (qid,))
        row = c.fetchone()
        if not row:
            return

        self.lbl_detail_title.config(text="Szczegóły pytania")
        self.lbl_detail_id.config(text=f"ID: {qid}")

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
            val = row[key] or ""
            w.insert("1.0", val)
            w.config(state=tk.DISABLED)

        self.var_correct.set(row["poprawna_odpowiedz"] or "")
        self._update_correct_text()

        # Flashcard answer
        self.txt_flashcard_answer.config(state=tk.NORMAL)
        self.txt_flashcard_answer.delete("1.0", tk.END)
        if row["typ_pytania"] == "otwarte":
            self.txt_flashcard_answer.insert("1.0", row["poprawna_odpowiedz_tekst"] or "")
            self.flashcard_frame.grid()
            self.txt_flashcard_answer.grid()
        else:
            self.flashcard_frame.grid_remove()
            self.txt_flashcard_answer.grid_remove()
        self.txt_flashcard_answer.config(state=tk.DISABLED)

        self._set_fields_enabled(False)
        self._update_button_states()

    def _update_correct_text(self):
        """Update the correct answer preview text."""
        letter = self.var_correct.get()
        if letter and letter in self.answer_widgets:
            text = self.answer_widgets[letter].get("1.0", "end-1c").strip()
            preview = text[:80] + ("..." if len(text) > 80 else "")
            self.lbl_correct_text.config(text=preview)
        else:
            self.lbl_correct_text.config(text="")

    def _set_fields_enabled(self, enabled):
        """Toggle read-only vs editable state for all fields."""
        state = "normal" if enabled else "readonly"
        for w in self.field_widgets.values():
            w.config(state=state)
        self.txt_pytanie.config(state=tk.NORMAL if enabled else tk.DISABLED)
        for w in self.answer_widgets.values():
            w.config(state=tk.NORMAL if enabled else tk.DISABLED)
        self.correct_combo.config(state="readonly" if enabled else tk.DISABLED)
        self.txt_flashcard_answer.config(state=tk.NORMAL if enabled else tk.DISABLED)

    def _update_button_states(self):
        """Update button states based on current mode."""
        sel_count = len(self.tree.selection())
        if self.editing:
            self.btn_edit.config(state=tk.DISABLED)
            self.btn_save.config(state=tk.NORMAL)
            self.btn_cancel.config(state=tk.NORMAL)
            self.btn_add.config(state=tk.DISABLED)
            self.btn_delete.config(state=tk.DISABLED)
            self.lbl_status.config(text="Tryb edycji - wprowadź zmiany i zapisz lub anuluj",
                                   foreground="blue")
        else:
            self.btn_edit.config(state=tk.NORMAL if self.current_id else tk.DISABLED)
            self.btn_save.config(state=tk.DISABLED)
            self.btn_cancel.config(state=tk.DISABLED)
            self.btn_add.config(state=tk.NORMAL)
            self.btn_delete.config(state=tk.NORMAL if (self.current_id or sel_count > 1) else tk.DISABLED)
            self.lbl_status.config(text="Gotowe.", foreground="gray")

    def _start_edit(self):
        if not self.current_id:
            return
        self.editing = True
        self._set_fields_enabled(True)
        self.flashcard_frame.grid()
        self.txt_flashcard_answer.grid()
        self._update_button_states()
        self.lbl_detail_title.config(text="Szczegóły pytania [EDYCJA]")

    def _cancel_edit(self):
        self.editing = False
        if self.current_id:
            self._load_question(self.current_id)
        else:
            self._clear_detail()
        self._update_button_states()

    def _save_question(self):
        """Save question (new or existing) to DB."""
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
            "poprawna_odpowiedz_tekst": self.txt_flashcard_answer.get("1.0", "end-1c").strip() or None,
            "zrodlo_pliku": self.field_vars["zrodlo_pliku"].get().strip() or "gui",
        }

        letter = data["poprawna_odpowiedz"]
        if data["typ_pytania"] == "testowe" and letter and letter.upper() in ["A", "B", "C", "D"]:
            key = f"odp_{letter.lower()}"
            data["poprawna_odpowiedz_tekst"] = data.get(key)

        c = self.conn.cursor()

        if self.current_id:
            c.execute("""
                UPDATE questions SET
                    kategoria=?, podkategoria=?, poziom=?, tematyka=?,
                    nr_pytania=?, typ_pytania=?, pytanie=?,
                    odp_a=?, odp_b=?, odp_c=?, odp_d=?,
                    poprawna_odpowiedz=?, poprawna_odpowiedz_tekst=?, zrodlo_pliku=?
                WHERE id=?
            """, (
                data["kategoria"], data["podkategoria"], data["poziom"], data["tematyka"],
                data["nr_pytania"], data["typ_pytania"], data["pytanie"],
                data["odp_a"], data["odp_b"], data["odp_c"], data["odp_d"],
                data["poprawna_odpowiedz"], data["poprawna_odpowiedz_tekst"],
                data["zrodlo_pliku"], self.current_id
            ))
            self.conn.commit()
            msg = f"Zapisano pytanie ID={self.current_id}."
        else:
            c.execute("""
                INSERT INTO questions
                    (kategoria, podkategoria, poziom, tematyka, nr_pytania,
                     typ_pytania, pytanie, odp_a, odp_b, odp_c, odp_d,
                     poprawna_odpowiedz, poprawna_odpowiedz_tekst, zrodlo_pliku)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data["kategoria"], data["podkategoria"], data["poziom"],
                data["tematyka"], data["nr_pytania"],
                data["typ_pytania"], data["pytanie"],
                data["odp_a"], data["odp_b"], data["odp_c"], data["odp_d"],
                data["poprawna_odpowiedz"], data["poprawna_odpowiedz_tekst"],
                data["zrodlo_pliku"]
            ))
            self.conn.commit()
            self.current_id = c.lastrowid
            self.lbl_detail_id.config(text=f"ID: {self.current_id}")
            msg = f"Dodano nowe pytanie ID={self.current_id}."

        self.editing = False
        self._set_fields_enabled(False)
        self.lbl_detail_title.config(text="Szczegóły pytania")
        self.lbl_status.config(text=msg, foreground="green")
        self._refresh_list()
        self._load_filters()
        self._update_button_states()

    def _add_new(self):
        """Clear form and prepare for adding a new question."""
        if self.editing:
            self._cancel_edit()

        self.current_id = None
        self.lbl_detail_title.config(text="Nowe pytanie")
        self.lbl_detail_id.config(text="")

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
        self.txt_flashcard_answer.config(state=tk.NORMAL)
        self.txt_flashcard_answer.delete("1.0", tk.END)
        self.txt_flashcard_answer.config(state=tk.DISABLED)
        self.flashcard_frame.grid()
        self.txt_flashcard_answer.grid()

        self.editing = True
        self._set_fields_enabled(True)
        self._update_button_states()

    def _delete_question(self):
        sel = self.tree.selection()
        if not sel:
            return

        if len(sel) > 1:
            ids = [self.tree.item(s)["values"][0] for s in sel]
            if not messagebox.askyesno("Potwierdzenie",
                                       f"Na pewno usunąć {len(ids)} zaznaczonych pytań?\n"
                                       f"Ta operacja jest nieodwracalna."):
                return
            c = self.conn.cursor()
            for qid in ids:
                c.execute("DELETE FROM questions WHERE id = ?", (qid,))
            self.conn.commit()
            self.current_id = None
            self._clear_detail()
            self.lbl_status.config(text=f"Usunięto {len(ids)} pytań.", foreground="red")
            self._refresh_list()
            self._update_button_states()
            return

        qid = self.tree.item(sel[0])["values"][0]
        if not messagebox.askyesno("Potwierdzenie",
                                   f"Na pewno usunąć pytanie ID={qid}?\nTej operacji nie można cofnąć."):
            return

        c = self.conn.cursor()
        c.execute("DELETE FROM questions WHERE id = ?", (qid,))
        self.conn.commit()

        self.current_id = None
        self._clear_detail()
        self.lbl_status.config(text=f"Usunięto pytanie ID={qid}.", foreground="red")
        self._refresh_list()
        self._update_button_states()

    def _clear_detail(self):
        self.current_id = None
        self.lbl_detail_title.config(text="Szczegóły pytania")
        self.lbl_detail_id.config(text="")
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
        self.txt_flashcard_answer.config(state=tk.NORMAL)
        self.txt_flashcard_answer.delete("1.0", tk.END)
        self.txt_flashcard_answer.config(state=tk.DISABLED)
        self.flashcard_frame.grid_remove()
        self.txt_flashcard_answer.grid_remove()
        self._set_fields_enabled(False)

    def _export_db(self):
        """Export the database to a new file."""
        filename = filedialog.asksaveasfilename(
            title="Eksportuj bazę",
            defaultextension=".db",
            filetypes=[("SQLite Database", "*.db"), ("All files", "*.*")],
            initialfile="questions_export.db"
        )
        if not filename:
            return

        try:
            # Close current connection
            self.conn.close()
            # Copy the DB file
            shutil.copy2(DB_PATH, filename)
            # Reopen
            self.conn = get_connection()
            self.lbl_status.config(text=f"Baza wyeksportowana do: {filename}", foreground="green")
            messagebox.showinfo("Eksport", f"Baza zapisana jako:\n{filename}")
        except Exception as e:
            self.conn = get_connection()
            messagebox.showerror("Błąd eksportu", str(e))

    @staticmethod
    def _parse_int(val):
        try:
            return int(val.strip())
        except (ValueError, AttributeError):
            return None

    def _on_close(self):
        if self.editing:
            if not messagebox.askyesno("Niezapisane zmiany",
                                       "Masz niezapisane zmiany. Na pewno zamknąć?"):
                return
        self.conn.close()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = QuestionBrowser(root)
    root.mainloop()
