"""BookShelf GUI — a tkinter companion to the CLI.

Launch with:
    python -m sample_app.ui
    bookshelf-gui          (if installed via pip/uv)
"""

from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from sample_app.goodreads import import_goodreads
from sample_app.loc import fetch_marc_by_lccn, search_loc
from sample_app.store import Collection, make_record

DEFAULT_COLLECTION = "bookshelf.mrc"


class BookShelfApp(tk.Tk):
    def __init__(self, collection_path: str = DEFAULT_COLLECTION) -> None:
        super().__init__()
        self.title("BookShelf")
        self.geometry("960x620")
        self.minsize(760, 480)

        self.collection_path = collection_path
        self.collection = Collection(collection_path)

        self._build_menu()
        self._build_toolbar()
        self._build_main()
        self._build_status_bar()
        self._refresh_table()

    # ── Menu ─────────────────────────────────────────────────────────────

    def _build_menu(self) -> None:
        menubar = tk.Menu(self)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Open Collection...", command=self._open_collection)
        file_menu.add_command(label="New Collection...", command=self._new_collection)
        file_menu.add_separator()
        file_menu.add_command(label="Import Goodreads CSV...", command=self._import_goodreads)
        file_menu.add_command(label="Import MARC file...", command=self._import_marc)
        file_menu.add_separator()
        file_menu.add_command(label="Export as JSON...", command=lambda: self._export("json"))
        file_menu.add_command(label="Export as XML...", command=lambda: self._export("xml"))
        file_menu.add_command(label="Export as Text...", command=lambda: self._export("text"))
        file_menu.add_separator()
        file_menu.add_command(label="Quit", command=self.destroy)
        menubar.add_cascade(label="File", menu=file_menu)

        book_menu = tk.Menu(menubar, tearoff=0)
        book_menu.add_command(label="Add Book...", command=self._add_book)
        book_menu.add_command(label="Delete Selected", command=self._delete_selected)
        book_menu.add_separator()
        book_menu.add_command(label="Search LOC...", command=self._search_loc)
        menubar.add_cascade(label="Books", menu=book_menu)

        self.config(menu=menubar)

    # ── Toolbar / filter bar ─────────────────────────────────────────────

    def _build_toolbar(self) -> None:
        toolbar = ttk.Frame(self, padding=4)
        toolbar.pack(side=tk.TOP, fill=tk.X)

        ttk.Label(toolbar, text="Filter:").pack(side=tk.LEFT, padx=(0, 4))
        self._filter_var = tk.StringVar()
        self._filter_var.trace_add("write", lambda *_: self._refresh_table())
        filter_entry = ttk.Entry(toolbar, textvariable=self._filter_var, width=30)
        filter_entry.pack(side=tk.LEFT, padx=(0, 8))

        ttk.Button(toolbar, text="Add Book", command=self._add_book).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Import CSV", command=self._import_goodreads).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Search LOC", command=self._search_loc).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Delete", command=self._delete_selected).pack(side=tk.LEFT, padx=2)

    # ── Main area: table + detail pane ───────────────────────────────────

    def _build_main(self) -> None:
        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # Left: table
        table_frame = ttk.Frame(paned)
        paned.add(table_frame, weight=3)

        columns = ("idx", "title", "author", "isbn", "year", "publisher")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")
        self.tree.heading("idx", text="#")
        self.tree.heading("title", text="Title")
        self.tree.heading("author", text="Author")
        self.tree.heading("isbn", text="ISBN")
        self.tree.heading("year", text="Year")
        self.tree.heading("publisher", text="Publisher")

        self.tree.column("idx", width=40, stretch=False)
        self.tree.column("title", width=250)
        self.tree.column("author", width=160)
        self.tree.column("isbn", width=120)
        self.tree.column("year", width=50, stretch=False)
        self.tree.column("publisher", width=140)

        vsb = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        # Right: detail pane
        detail_frame = ttk.LabelFrame(paned, text="Details", padding=8)
        paned.add(detail_frame, weight=2)

        self._detail_text = tk.Text(detail_frame, wrap=tk.WORD, state=tk.DISABLED, font=("Consolas", 10))
        detail_vsb = ttk.Scrollbar(detail_frame, orient=tk.VERTICAL, command=self._detail_text.yview)
        self._detail_text.configure(yscrollcommand=detail_vsb.set)
        self._detail_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        detail_vsb.pack(side=tk.RIGHT, fill=tk.Y)

    # ── Status bar ───────────────────────────────────────────────────────

    def _build_status_bar(self) -> None:
        self._status_var = tk.StringVar(value="Ready")
        bar = ttk.Label(self, textvariable=self._status_var, relief=tk.SUNKEN, anchor=tk.W, padding=2)
        bar.pack(side=tk.BOTTOM, fill=tk.X)

    def _set_status(self, msg: str) -> None:
        self._status_var.set(msg)
        self.update_idletasks()

    # ── Table refresh ────────────────────────────────────────────────────

    def _refresh_table(self) -> None:
        self.tree.delete(*self.tree.get_children())
        filter_text = self._filter_var.get().lower()

        for i, rec in enumerate(self.collection.records):
            title = rec.title or ""
            author = rec.author or ""
            isbn = rec.isbn or ""
            year = rec.pubyear or ""
            publisher = rec.publisher or ""

            if filter_text:
                haystack = f"{title} {author} {isbn} {year} {publisher}".lower()
                if filter_text not in haystack:
                    continue

            self.tree.insert("", tk.END, iid=str(i), values=(i, title, author, isbn, year, publisher))

        count = len(self.tree.get_children())
        total = len(self.collection)
        if filter_text:
            self._set_status(f"Showing {count} of {total} books (filtered)")
        else:
            self._set_status(f"{total} books in {self.collection_path}")

    # ── Selection / detail ───────────────────────────────────────────────

    def _on_select(self, _event: object) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        detail = self.collection.report_detail(idx)
        self._detail_text.configure(state=tk.NORMAL)
        self._detail_text.delete("1.0", tk.END)
        self._detail_text.insert(tk.END, detail)
        self._detail_text.configure(state=tk.DISABLED)

    # ── Actions ──────────────────────────────────────────────────────────

    def _open_collection(self) -> None:
        path = filedialog.askopenfilename(
            title="Open Collection",
            filetypes=[("MARC files", "*.mrc"), ("All files", "*.*")],
        )
        if path:
            self.collection_path = path
            self.collection = Collection(path)
            self._refresh_table()

    def _new_collection(self) -> None:
        path = filedialog.asksaveasfilename(
            title="New Collection",
            defaultextension=".mrc",
            filetypes=[("MARC files", "*.mrc")],
        )
        if path:
            self.collection_path = path
            self.collection = Collection(path)
            self._refresh_table()

    def _import_goodreads(self) -> None:
        path = filedialog.askopenfilename(
            title="Import Goodreads CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return

        enrich = messagebox.askyesno(
            "LOC Enrichment",
            "Attempt to fetch full MARC records from the Library of Congress?\n\n"
            "This makes network requests and will take a while for large libraries.",
        )

        self._set_status("Importing Goodreads CSV...")

        def do_import() -> None:
            def on_progress(current: int, total: int, title: str) -> None:
                self.after(0, self._set_status, f"Importing [{current}/{total}]: {title}")

            try:
                count = import_goodreads(path, self.collection, enrich=enrich, on_progress=on_progress)
                self.after(0, self._finish_import, count)
            except Exception as exc:
                self.after(0, messagebox.showerror, "Import Error", str(exc))
                self.after(0, self._set_status, "Import failed.")

        threading.Thread(target=do_import, daemon=True).start()

    def _finish_import(self, count: int) -> None:
        self._refresh_table()
        self._set_status(f"Imported {count} books from Goodreads CSV.")
        messagebox.showinfo("Import Complete", f"Imported {count} book(s).")

    def _import_marc(self) -> None:
        path = filedialog.askopenfilename(
            title="Import MARC File",
            filetypes=[("MARC files", "*.mrc"), ("XML files", "*.xml"), ("All files", "*.*")],
        )
        if not path:
            return

        p = Path(path)
        if p.suffix.lower() == ".xml":
            count = self.collection.import_xml(p)
        else:
            count = self.collection.import_marc(p)

        self._refresh_table()
        self._set_status(f"Imported {count} records from {p.name}")

    def _export(self, fmt: str) -> None:
        ext_map = {"json": ".json", "xml": ".xml", "text": ".txt"}
        path = filedialog.asksaveasfilename(
            title=f"Export as {fmt.upper()}",
            defaultextension=ext_map.get(fmt, ""),
            filetypes=[(f"{fmt.upper()} files", f"*{ext_map.get(fmt, '')}"), ("All files", "*.*")],
        )
        if not path:
            return

        if fmt == "json":
            self.collection.export_json(path)
        elif fmt == "xml":
            self.collection.export_xml(path)
        elif fmt == "text":
            self.collection.export_text(path)

        self._set_status(f"Exported {len(self.collection)} records to {path}")

    def _add_book(self) -> None:
        dialog = AddBookDialog(self)
        self.wait_window(dialog)
        if dialog.result:
            record = make_record(**dialog.result)
            self.collection.add(record)
            self._refresh_table()
            self._set_status(f"Added: {dialog.result['title']}")

    def _delete_selected(self) -> None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Select a book to delete.")
            return
        idx = int(sel[0])
        rec = self.collection.get(idx)
        title = rec.title or "Untitled"
        if messagebox.askyesno("Confirm Delete", f"Delete '{title}'?"):
            self.collection.delete(idx)
            self._refresh_table()
            self._set_status(f"Deleted: {title}")

    def _search_loc(self) -> None:
        dialog = LocSearchDialog(self, self.collection)
        self.wait_window(dialog)
        if dialog.added:
            self._refresh_table()
            self._set_status(f"Added {dialog.added} book(s) from Library of Congress.")


# ── Dialogs ──────────────────────────────────────────────────────────────


class AddBookDialog(tk.Toplevel):
    """Simple dialog for adding a book manually."""

    result: dict | None = None

    def __init__(self, parent: tk.Tk) -> None:
        super().__init__(parent)
        self.title("Add Book")
        self.geometry("400x340")
        self.transient(parent)
        self.grab_set()

        fields = [
            ("Title*", "title"),
            ("Author*", "author"),
            ("ISBN", "isbn"),
            ("Publisher", "publisher"),
            ("Year", "year"),
            ("Subjects (;-separated)", "subjects"),
            ("Notes", "notes"),
            ("Location", "location"),
        ]
        self._entries: dict[str, ttk.Entry] = {}

        for i, (label, key) in enumerate(fields):
            ttk.Label(self, text=label).grid(row=i, column=0, sticky=tk.W, padx=8, pady=2)
            entry = ttk.Entry(self, width=36)
            entry.grid(row=i, column=1, padx=8, pady=2)
            self._entries[key] = entry

        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=len(fields), column=0, columnspan=2, pady=12)
        ttk.Button(btn_frame, text="Add", command=self._on_add).pack(side=tk.LEFT, padx=8)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side=tk.LEFT, padx=8)

        self._entries["title"].focus_set()

    def _on_add(self) -> None:
        title = self._entries["title"].get().strip()
        author = self._entries["author"].get().strip()
        if not title or not author:
            messagebox.showwarning("Required Fields", "Title and Author are required.", parent=self)
            return

        subjects_raw = self._entries["subjects"].get().strip()
        subjects = [s.strip() for s in subjects_raw.split(";")] if subjects_raw else []

        self.result = {
            "title": title,
            "author": author,
            "isbn": self._entries["isbn"].get().strip(),
            "publisher": self._entries["publisher"].get().strip(),
            "year": self._entries["year"].get().strip(),
            "subjects": subjects,
            "notes": self._entries["notes"].get().strip(),
            "location": self._entries["location"].get().strip(),
        }
        self.destroy()


class LocSearchDialog(tk.Toplevel):
    """Dialog to search Library of Congress and add results to the collection."""

    added: int = 0

    def __init__(self, parent: tk.Tk, collection: Collection) -> None:
        super().__init__(parent)
        self.title("Search Library of Congress")
        self.geometry("620x420")
        self.transient(parent)
        self.grab_set()

        self._collection = collection
        self._results: list[dict] = []

        # Search bar
        top = ttk.Frame(self, padding=8)
        top.pack(fill=tk.X)
        ttk.Label(top, text="Query:").pack(side=tk.LEFT)
        self._query_var = tk.StringVar()
        entry = ttk.Entry(top, textvariable=self._query_var, width=40)
        entry.pack(side=tk.LEFT, padx=4)
        entry.bind("<Return>", lambda _: self._do_search())
        ttk.Button(top, text="Search", command=self._do_search).pack(side=tk.LEFT, padx=4)

        # Results list
        cols = ("title", "author", "date", "lccn")
        self._result_tree = ttk.Treeview(self, columns=cols, show="headings", selectmode="browse")
        self._result_tree.heading("title", text="Title")
        self._result_tree.heading("author", text="Author")
        self._result_tree.heading("date", text="Date")
        self._result_tree.heading("lccn", text="LCCN")
        self._result_tree.column("title", width=240)
        self._result_tree.column("author", width=140)
        self._result_tree.column("date", width=60, stretch=False)
        self._result_tree.column("lccn", width=100)
        self._result_tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        # Buttons
        btn_frame = ttk.Frame(self, padding=8)
        btn_frame.pack(fill=tk.X)
        ttk.Button(btn_frame, text="Fetch & Add Selected", command=self._fetch_selected).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frame, text="Close", command=self.destroy).pack(side=tk.RIGHT, padx=4)

        self._status_var = tk.StringVar(value="Enter a search query.")
        ttk.Label(self, textvariable=self._status_var, relief=tk.SUNKEN, padding=2).pack(fill=tk.X)

        entry.focus_set()

    def _do_search(self) -> None:
        query = self._query_var.get().strip()
        if not query:
            return

        self._status_var.set("Searching...")
        self.update_idletasks()

        def search_thread() -> None:
            try:
                results = search_loc(query, max_results=10)
                self.after(0, self._show_results, results)
            except ConnectionError as exc:
                self.after(0, self._status_var.set, f"Error: {exc}")

        threading.Thread(target=search_thread, daemon=True).start()

    def _show_results(self, results: list[dict]) -> None:
        self._results = results
        self._result_tree.delete(*self._result_tree.get_children())
        for i, r in enumerate(results):
            self._result_tree.insert(
                "", tk.END, iid=str(i), values=(r["title"], r["author"], r["date"], r["lccn"])
            )
        self._status_var.set(f"Found {len(results)} result(s).")

    def _fetch_selected(self) -> None:
        sel = self._result_tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Select a result first.", parent=self)
            return

        idx = int(sel[0])
        lccn = self._results[idx].get("lccn", "")
        if not lccn:
            messagebox.showwarning("No LCCN", "This result has no LCCN — cannot fetch MARC record.", parent=self)
            return

        self._status_var.set(f"Fetching MARC record for LCCN {lccn}...")
        self.update_idletasks()

        def fetch_thread() -> None:
            try:
                record = fetch_marc_by_lccn(lccn)
                self.after(0, self._on_fetched, record, lccn)
            except ConnectionError as exc:
                self.after(0, self._status_var.set, f"Error: {exc}")

        threading.Thread(target=fetch_thread, daemon=True).start()

    def _on_fetched(self, record: object, lccn: str) -> None:
        if record is None:
            self._status_var.set(f"No MARC record found for LCCN {lccn}.")
            return

        self._collection.add(record)
        self.added += 1
        title = getattr(record, "title", None) or "Unknown"
        self._status_var.set(f"Added: {title}")


def main() -> None:
    app = BookShelfApp()
    app.mainloop()


if __name__ == "__main__":
    main()
