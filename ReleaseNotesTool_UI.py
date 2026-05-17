import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
from pathlib import Path

from ReleaseNotesCreatorv4 import process_dev_notes
from notes_to_for_devnotes import generate_for_devnotes
from full_pipeline import run_full_pipeline


class ReleaseNotesToolUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Release Notes Tool")
        self.geometry("760x340")
        self.resizable(False, False)

        tabs = ttk.Notebook(self)
        tabs.pack(fill="both", expand=True)

        # ✅ NEW: All-in-one tab
        self._tab_all_in_one(tabs)

        # ✅ FIRST TAB — Notes -> For_DevNotes
        self._tab_for_devnotes(tabs)

        # ✅ SECOND TAB — DevNotes -> ReleaseNotes
        self._tab_release_notes(tabs)

    # ==============================
    # Tab: All-in-One
    # Inputs: DevNotes.txt, Patch number, checkinid.txt, Notes.txt
    # Outputs: DevNotes.txt (updated in place) + ReleaseNotes.txt
    # ==============================
    def _tab_all_in_one(self, tabs):
        tab = ttk.Frame(tabs)
        tabs.add(tab, text="All-in-One")

        self.aio_devnotes = tk.StringVar()
        self.aio_patch = tk.StringVar()
        self.aio_checkinid = tk.StringVar()
        self.aio_notes = tk.StringVar()

        ttk.Label(tab, text="DevNotes.txt:").grid(row=0, column=0, padx=10, pady=8, sticky="w")
        ttk.Entry(tab, textvariable=self.aio_devnotes, width=70).grid(row=0, column=1, padx=10)
        ttk.Button(tab, text="Browse", command=self._aio_browse_devnotes).grid(row=0, column=2)

        ttk.Label(tab, text="Patch Number:").grid(row=1, column=0, padx=10, pady=8, sticky="w")
        ttk.Entry(tab, textvariable=self.aio_patch, width=70).grid(row=1, column=1, padx=10, sticky="w")
        ttk.Label(tab, text="(e.g. Patch10)").grid(row=1, column=2, sticky="w", padx=(0, 10))

        ttk.Label(tab, text="checkinid.txt:").grid(row=2, column=0, padx=10, pady=8, sticky="w")
        ttk.Entry(tab, textvariable=self.aio_checkinid, width=70).grid(row=2, column=1, padx=10)
        ttk.Button(tab, text="Browse", command=self._aio_browse_checkinid).grid(row=2, column=2)

        ttk.Label(tab, text="Notes.txt:").grid(row=3, column=0, padx=10, pady=8, sticky="w")
        ttk.Entry(tab, textvariable=self.aio_notes, width=70).grid(row=3, column=1, padx=10)
        ttk.Button(tab, text="Browse", command=self._aio_browse_notes).grid(row=3, column=2)

        ttk.Button(
            tab,
            text="Run Full Pipeline",
            command=self._aio_run
        ).grid(row=4, column=0, columnspan=3, pady=15)

    def _aio_browse_devnotes(self):
        path = filedialog.askopenfilename(filetypes=[("Text files", "*.txt")])
        if path:
            self.aio_devnotes.set(path)

    def _aio_browse_checkinid(self):
        path = filedialog.askopenfilename(filetypes=[("Text files", "*.txt")])
        if path:
            self.aio_checkinid.set(path)

    def _aio_browse_notes(self):
        path = filedialog.askopenfilename(filetypes=[("Text files", "*.txt")])
        if path:
            self.aio_notes.set(path)

    def _aio_run(self):
        if not self.aio_devnotes.get():
            messagebox.showerror("Error", "Select DevNotes.txt")
            return
        if not self.aio_patch.get().strip():
            messagebox.showerror("Error", "Enter a patch number (e.g. Patch10)")
            return
        if not self.aio_checkinid.get() or not self.aio_notes.get():
            messagebox.showerror("Error", "Select both checkinid.txt and Notes.txt")
            return

        try:
            devnotes_path, releasenotes_path, backup_path = run_full_pipeline(
                devnotes_file=self.aio_devnotes.get(),
                patch_number=self.aio_patch.get().strip(),
                checkinid_file=self.aio_checkinid.get(),
                notes_file=self.aio_notes.get(),
            )
        except Exception as e:
            messagebox.showerror("Error", f"Pipeline failed:\n{e}")
            return

        msg = (
            f"Updated:\n{devnotes_path}\n\n"
            f"Created:\n{releasenotes_path}"
        )
        if backup_path is not None:
            msg += f"\n\nBackup of original DevNotes saved as:\n{backup_path}"

        messagebox.showinfo("Success", msg)

    # ==============================
    # Tab 1: Notes -> For_DevNotes
    # ==============================
    def _tab_for_devnotes(self, tabs):
        tab = ttk.Frame(tabs)
        tabs.add(tab, text="Notes → For_DevNotes")

        self.checkinid = tk.StringVar()
        self.notes = tk.StringVar()

        ttk.Label(tab, text="checkinid.txt:").grid(row=0, column=0, padx=10, pady=8, sticky="w")
        ttk.Entry(tab, textvariable=self.checkinid, width=70).grid(row=0, column=1, padx=10)
        ttk.Button(tab, text="Browse", command=self._browse_checkinid).grid(row=0, column=2)

        ttk.Label(tab, text="Notes.txt:").grid(row=1, column=0, padx=10, pady=8, sticky="w")
        ttk.Entry(tab, textvariable=self.notes, width=70).grid(row=1, column=1, padx=10)
        ttk.Button(tab, text="Browse", command=self._browse_notes).grid(row=1, column=2)

        ttk.Button(
            tab,
            text="Generate For_DevNotes.txt",
            command=self._gen_for_devnotes
        ).grid(row=2, column=0, columnspan=3, pady=15)

    def _browse_checkinid(self):
        path = filedialog.askopenfilename(filetypes=[("Text files", "*.txt")])
        if path:
            self.checkinid.set(path)

    def _browse_notes(self):
        path = filedialog.askopenfilename(filetypes=[("Text files", "*.txt")])
        if path:
            self.notes.set(path)

    def _gen_for_devnotes(self):
        if not self.checkinid.get() or not self.notes.get():
            messagebox.showerror("Error", "Select both checkinid.txt and Notes.txt")
            return

        out = Path(self.notes.get()).parent / "For_DevNotes.txt"
        generate_for_devnotes(self.checkinid.get(), self.notes.get(), out)
        messagebox.showinfo("Success", f"Created:\n{out}")

    # ==============================
    # Tab 2: DevNotes -> ReleaseNotes
    # ==============================
    def _tab_release_notes(self, tabs):
        tab = ttk.Frame(tabs)
        tabs.add(tab, text="DevNotes → ReleaseNotes")

        self.devnotes = tk.StringVar()

        ttk.Label(tab, text="DevNotes File:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        ttk.Entry(tab, textvariable=self.devnotes, width=70).grid(row=0, column=1, padx=10)
        ttk.Button(tab, text="Browse", command=self._browse_devnotes).grid(row=0, column=2)

        ttk.Button(
            tab,
            text="Generate ReleaseNotes.txt",
            command=self._gen_release_notes
        ).grid(row=1, column=0, columnspan=3, pady=15)

    def _browse_devnotes(self):
        path = filedialog.askopenfilename(filetypes=[("Text files", "*.txt")])
        if path:
            self.devnotes.set(path)

    def _gen_release_notes(self):
        if not self.devnotes.get():
            messagebox.showerror("Error", "Select DevNotes.txt")
            return

        dev = Path(self.devnotes.get())
        out = dev.parent / "ReleaseNotes.txt"

        process_dev_notes(str(dev), str(out))
        messagebox.showinfo("Success", f"Created:\n{out}")


if __name__ == "__main__":
    app = ReleaseNotesToolUI()
    app.mainloop()
