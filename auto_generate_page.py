"""
Auto-Generate page for the Release Notes Tool.

Two modes:

  New patch (default):
    Fetch notes for the requested PRs/check-ins from Phabricator and write
    them as a brand-new patch block in DevNotes.

  Merge into existing patch:
    Pick an existing patch label (e.g. "Patch2") from the DevNotes file.
    Fetch notes for the requested PRs/check-ins. Re-build the entire patch
    block: existing + new check-ins, sorted by check-in ID descending. If
    any check-in IDs collide, prompt the user per-id: keep existing or
    replace with new.

Degrades gracefully if PHAB_ACCESS_TOKEN / PHAB_URL / PHAB_REPO_PHID env
vars are missing.
"""

from __future__ import annotations
from pathlib import Path
from tkinter import messagebox
import os
import re
import tempfile

import customtkinter as ctk

# NOTE: We do NOT import ReleaseNotesTool_UI_ctk at module top level —
# it imports us back, causing a circular import. Defer to inside methods.

from branch_detector import extract_branch_from_devnotes
from sources.base import NoteSource
from sources.file_source import FileSource
from merger.priority_merger import merge_with_priority_fallback
from devnotes_parser import list_patch_labels

# PhabSource imported lazily inside _build_sources so this file loads even
# when requests is missing.

FALLBACK_BRANCH = "Development"

PR_RE = re.compile(r'\bPR-\d+(?:-\d+)?\b', re.IGNORECASE)
CHECKIN_ID_RE = re.compile(r'\b\d+\.\d+\b')


class AutoGeneratePage(ctk.CTkFrame):
    """Sidebar page that automates the Notes.txt fetch step."""

    def __init__(self, master, app):
        from ReleaseNotesTool_UI_ctk import BG as _BG
        super().__init__(master, fg_color=_BG, corner_radius=0)
        self.app = app
        self._detected_branch: str | None = None
        self._build()

    # ==================================================================
    # Layout
    # ==================================================================
    def _build(self):
        from ReleaseNotesTool_UI_ctk import (
            CARD, BG, BORDER, NAVY, GREEN, GREEN_HOVER, GREEN_LIGHT,
            TEXT, TEXT_MUTED, TEXT_FAINT,
            FileField, PatchTypeNumberField,
        )
        # Stash for helper methods
        self._CARD = CARD; self._BG = BG; self._BORDER = BORDER
        self._GREEN = GREEN; self._GREEN_HOVER = GREEN_HOVER
        self._TEXT = TEXT; self._TEXT_MUTED = TEXT_MUTED; self._TEXT_FAINT = TEXT_FAINT

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=32, pady=(28, 8))
        ctk.CTkLabel(
            header, text="Auto-Generate",
            text_color=TEXT, font=ctk.CTkFont(size=24, weight="bold"),
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            header,
            text=("Fetch check-in notes from Phabricator and run the full "
                  "pipeline.  No Notes.txt needed — fetched automatically."),
            text_color=TEXT_MUTED, font=ctk.CTkFont(size=13),
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=32, pady=(8, 24))
        body.grid_columnconfigure(0, weight=1)

        # --- Card 1: DevNotes + Mode + Patch number ---
        card1 = self._card(body, row=0)
        ctk.CTkLabel(
            card1, text="Step 1 — Patch target",
            text_color=TEXT, font=ctk.CTkFont(size=15, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=20, pady=(18, 6), columnspan=2)

        self.devnotes_field = FileField(card1, "DevNotes.txt",
                                        "Existing dev notes file to update")
        self.devnotes_field.grid(row=1, column=0, sticky="ew", padx=20, pady=8, columnspan=2)
        # FileField's StringVar is self.var
        self.devnotes_field.var.trace_add("write", self._on_devnotes_change)

        # Mode radio: new patch vs merge into existing
        mode_frame = ctk.CTkFrame(card1, fg_color="transparent")
        mode_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=(4, 4), columnspan=2)
        self.mode_var = ctk.StringVar(value="new")
        ctk.CTkRadioButton(
            mode_frame, text="New patch",
            variable=self.mode_var, value="new",
            fg_color=GREEN, hover_color=GREEN_HOVER,
            command=self._update_mode,
        ).grid(row=0, column=0, sticky="w", padx=(0, 16))
        ctk.CTkRadioButton(
            mode_frame, text="Merge into existing patch",
            variable=self.mode_var, value="merge",
            fg_color=GREEN, hover_color=GREEN_HOVER,
            command=self._update_mode,
        ).grid(row=0, column=1, sticky="w")

        # New-patch input: PatchTypeNumberField
        self.new_patch_frame = ctk.CTkFrame(card1, fg_color="transparent")
        self.new_patch_frame.grid_columnconfigure(0, weight=1)
        self.patch_field = PatchTypeNumberField(self.new_patch_frame)
        self.patch_field.grid(row=0, column=0, sticky="ew")

        # Merge input: dropdown of existing patch labels in chosen DevNotes
        self.merge_frame = ctk.CTkFrame(card1, fg_color="transparent")
        self.merge_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            self.merge_frame, text="Existing patch:",
            text_color=TEXT, font=ctk.CTkFont(size=13),
            width=120, anchor="w",
        ).grid(row=0, column=0, sticky="w")
        self.merge_patch_var = ctk.StringVar(value="(select DevNotes file first)")
        self.merge_patch_menu = ctk.CTkOptionMenu(
            self.merge_frame, variable=self.merge_patch_var,
            values=["(select DevNotes file first)"],
            fg_color="white", text_color=TEXT,
            button_color=GREEN, button_hover_color=GREEN_HOVER,
            dropdown_fg_color="white", dropdown_text_color=TEXT,
            height=34,
        )
        self.merge_patch_menu.grid(row=0, column=1, sticky="ew", padx=(10, 0))

        self._update_mode()

        # --- Card 2: Branch ---
        card2 = self._card(body, row=1)
        ctk.CTkLabel(
            card2, text="Step 2 — Branch",
            text_color=TEXT, font=ctk.CTkFont(size=15, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=20, pady=(18, 4), columnspan=2)
        ctk.CTkLabel(
            card2,
            text=(f"Auto-detected from the DevNotes 'Base Version:' line. "
                  f"Edit to override. {FALLBACK_BRANCH} is always tried as "
                  f"the ultimate fallback."),
            text_color=TEXT_MUTED, font=ctk.CTkFont(size=12),
            wraplength=620, justify="left", anchor="w",
        ).grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 10), columnspan=2)

        branch_row = ctk.CTkFrame(card2, fg_color="transparent")
        branch_row.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 8), columnspan=2)
        branch_row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(branch_row, text="Branch:", text_color=TEXT,
                     font=ctk.CTkFont(size=13), width=80, anchor="w"
                     ).grid(row=0, column=0, sticky="w")
        self.branch_var = ctk.StringVar()
        self.branch_entry = ctk.CTkEntry(
            branch_row, textvariable=self.branch_var,
            placeholder_text="(auto-detect from DevNotes)",
            height=34, fg_color="white", border_color=BORDER,
        )
        self.branch_entry.grid(row=0, column=1, sticky="ew", padx=(10, 0))

        self.branch_status = ctk.CTkLabel(
            card2, text="", text_color=TEXT_FAINT,
            font=ctk.CTkFont(size=11), anchor="w",
        )
        self.branch_status.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 18), columnspan=2)

        # --- Card 3: Query source ---
        card3 = self._card(body, row=2)
        ctk.CTkLabel(
            card3, text="Step 3 — What to fetch",
            text_color=TEXT, font=ctk.CTkFont(size=15, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=20, pady=(18, 4), columnspan=2)
        ctk.CTkLabel(
            card3, text="Choose how to specify which check-ins / PRs to fetch.",
            text_color=TEXT_MUTED, font=ctk.CTkFont(size=12),
            wraplength=620, justify="left", anchor="w",
        ).grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 10), columnspan=2)

        self.input_mode = ctk.StringVar(value="paste")
        mode_row = ctk.CTkFrame(card3, fg_color="transparent")
        mode_row.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 10), columnspan=2)
        ctk.CTkRadioButton(
            mode_row, text="Type PR numbers / check-in IDs",
            variable=self.input_mode, value="paste",
            fg_color=GREEN, hover_color=GREEN_HOVER,
            command=self._update_input_mode,
        ).grid(row=0, column=0, sticky="w", padx=(0, 16))
        ctk.CTkRadioButton(
            mode_row, text="Use checkinid.txt file",
            variable=self.input_mode, value="file",
            fg_color=GREEN, hover_color=GREEN_HOVER,
            command=self._update_input_mode,
        ).grid(row=0, column=1, sticky="w")

        self.paste_frame = ctk.CTkFrame(card3, fg_color="transparent")
        self.paste_frame.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 18), columnspan=2)
        self.paste_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            self.paste_frame,
            text="Enter PR numbers and/or check-in IDs (one per line or comma-separated):",
            text_color=TEXT_MUTED, font=ctk.CTkFont(size=11), anchor="w",
        ).grid(row=0, column=0, sticky="w", pady=(0, 4))
        self.paste_box = ctk.CTkTextbox(
            self.paste_frame, height=120, fg_color="white",
            border_color=BORDER, border_width=1,
            font=ctk.CTkFont(size=12, family="Courier"),
        )
        self.paste_box.grid(row=1, column=0, sticky="ew")

        self.file_frame = ctk.CTkFrame(card3, fg_color="transparent")
        self.file_frame.grid_columnconfigure(0, weight=1)
        self.checkinid_field = FileField(self.file_frame, "checkinid.txt",
                                          "Check-in IDs or PR numbers")
        self.checkinid_field.grid(row=0, column=0, sticky="ew")

        self._update_input_mode()

        # Action button
        action_row = ctk.CTkFrame(body, fg_color="transparent")
        action_row.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        action_row.grid_columnconfigure(0, weight=1)
        self.run_btn = ctk.CTkButton(
            action_row, text="Fetch & Preview",
            fg_color=GREEN, hover_color=GREEN_HOVER, text_color="white",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=44, command=self._on_run,
        )
        self.run_btn.grid(row=0, column=0, sticky="e")

        self.status_label = ctk.CTkLabel(
            body, text="", text_color=TEXT_MUTED,
            font=ctk.CTkFont(size=12), anchor="w",
        )
        self.status_label.grid(row=4, column=0, sticky="ew", pady=(12, 0))

    def _card(self, parent, row: int):
        card = ctk.CTkFrame(parent, fg_color=self._CARD, corner_radius=10,
                            border_width=1, border_color=self._BORDER)
        card.grid(row=row, column=0, sticky="ew", pady=(0, 14))
        card.grid_columnconfigure(0, weight=1)
        return card

    # ==================================================================
    # Reactivity
    # ==================================================================
    def _update_mode(self):
        if self.mode_var.get() == "new":
            self.merge_frame.grid_forget()
            self.new_patch_frame.grid(row=3, column=0, sticky="ew",
                                      padx=20, pady=(8, 20), columnspan=2)
        else:
            self.new_patch_frame.grid_forget()
            self.merge_frame.grid(row=3, column=0, sticky="ew",
                                  padx=20, pady=(8, 20), columnspan=2)

    def _update_input_mode(self):
        if self.input_mode.get() == "paste":
            self.file_frame.grid_forget()
            self.paste_frame.grid(row=3, column=0, sticky="ew",
                                  padx=20, pady=(0, 18), columnspan=2)
        else:
            self.paste_frame.grid_forget()
            self.file_frame.grid(row=3, column=0, sticky="ew",
                                 padx=20, pady=(0, 18), columnspan=2)

    def _on_devnotes_change(self, *_):
        path = self.devnotes_field.get()
        if not path:
            self._detected_branch = None
            self.branch_status.configure(text="")
            self.merge_patch_menu.configure(values=["(select DevNotes file first)"])
            self.merge_patch_var.set("(select DevNotes file first)")
            return

        # Branch auto-detect
        token = extract_branch_from_devnotes(path)
        self._detected_branch = token
        if token:
            if not self.branch_var.get():
                self.branch_var.set(token)
            self.branch_status.configure(
                text=f"Auto-detected: {token}  (you can edit above to override)",
                text_color=self._GREEN,
            )
        else:
            self.branch_status.configure(
                text=(f"Could not detect branch. Type one manually, or it "
                      f"will fall through directly to {FALLBACK_BRANCH}."),
                text_color="#a16207",
            )

        # Populate merge dropdown
        try:
            labels = list_patch_labels(path)
        except Exception:
            labels = []
        if labels:
            self.merge_patch_menu.configure(values=labels)
            self.merge_patch_var.set(labels[0])
        else:
            self.merge_patch_menu.configure(values=["(no patches found)"])
            self.merge_patch_var.set("(no patches found)")

    # ==================================================================
    # Run
    # ==================================================================
    def _gather_queries(self) -> list[str]:
        if self.input_mode.get() == "paste":
            raw = self.paste_box.get("1.0", "end")
        else:
            path = self.checkinid_field.get()
            if not path:
                return []
            try:
                raw = Path(path).read_text(encoding="utf-8", errors="ignore")
            except OSError:
                return []

        seen: set[str] = set()
        ordered: list[str] = []
        pr_spans = []
        for m in PR_RE.finditer(raw):
            value = "PR-" + m.group().split("-", 1)[1]
            if value not in seen:
                seen.add(value); ordered.append(value)
            pr_spans.append(m.span())
        masked = list(raw)
        for s, e in pr_spans:
            for i in range(s, e):
                masked[i] = " "
        for m in CHECKIN_ID_RE.finditer("".join(masked)):
            v = m.group()
            if v not in seen:
                seen.add(v); ordered.append(v)
        return ordered

    def _build_sources(self, primary_branch):
        try:
            from sources.phab_source import PhabSource
        except ImportError as e:
            return [], f"Could not load PhabSource module: {e}"
        probe = PhabSource(branch=primary_branch or FALLBACK_BRANCH)
        config_err = probe._config_error()
        if config_err:
            return [], (f"Phabricator is not configured.\n\n{config_err}\n\n"
                        f"Set the missing environment variable(s) and restart the app.")
        sources: list[NoteSource] = []
        if primary_branch and primary_branch.strip() and primary_branch != FALLBACK_BRANCH:
            sources.append(PhabSource(branch=primary_branch.strip(), priority=1))
        sources.append(PhabSource(branch=FALLBACK_BRANCH, priority=99))
        return sources, None

    def _on_run(self):
        devnotes = self.devnotes_field.get()
        if not devnotes:
            messagebox.showerror("Error", "Select a DevNotes file.")
            return

        mode = self.mode_var.get()
        if mode == "new":
            if not self.patch_field.type_var.get().strip():
                messagebox.showerror("Error", "Select or type a patch type.")
                return
            if not self.patch_field.num_var.get().strip():
                messagebox.showerror("Error", "Enter a patch number (e.g. 10 or 5.1).")
                return
            patch_label = self.patch_field.get()
        else:
            patch_label = self.merge_patch_var.get()
            if not patch_label or patch_label.startswith("("):
                messagebox.showerror("Error", "Select an existing patch from the dropdown.")
                return

        queries = self._gather_queries()
        if not queries:
            messagebox.showerror(
                "Error",
                "No PR numbers or check-in IDs provided.\n\n"
                "Type some in the box or select a checkinid.txt file."
            )
            return

        primary = self.branch_var.get().strip() or self._detected_branch
        sources, err = self._build_sources(primary)
        if err:
            messagebox.showerror("Configuration", err)
            return

        # Fetch
        self.status_label.configure(
            text=f"Fetching {len(queries)} item(s) from Phabricator…",
            text_color=self._TEXT_MUTED)
        self.run_btn.configure(state="disabled", text="Fetching…")
        self.update_idletasks()
        try:
            merged = merge_with_priority_fallback(sources, queries)
        except Exception as e:
            messagebox.showerror("Fetch error", f"{e}")
            self.run_btn.configure(state="normal", text="Fetch & Preview")
            self.status_label.configure(text="")
            return
        finally:
            self.run_btn.configure(state="normal", text="Fetch & Preview")

        if not merged.text:
            attempts_summary = ", ".join(
                f"{a['source']}(matched {a['matched_count']})" for a in merged.attempts)
            messagebox.showwarning(
                "No results",
                f"None of the {len(queries)} queries matched any branch.\n\n"
                f"Tried: {attempts_summary}\n\n"
                f"Verify the PR numbers exist and the branch names are correct."
            )
            self.status_label.configure(
                text=f"No matches across {len(merged.attempts)} branch(es) tried.",
                text_color="#a16207")
            return

        self.status_label.configure(
            text=(f"Fetched from {merged.chosen_source} "
                  f"(branch={merged.chosen_branch}). "
                  f"{len(merged.matched_queries)} of {len(queries)} matched."),
            text_color=self._GREEN)

        if mode == "new":
            self._handle_new_patch(devnotes, patch_label, queries, merged.text)
        else:
            self._handle_merge(devnotes, patch_label, merged.text)

    # ------------------------------------------------------------------
    # New patch (existing flow)
    # ------------------------------------------------------------------
    def _handle_new_patch(self, devnotes, patch_label, queries, notes_text):
        from full_pipeline import build_preview, commit_preview
        from ReleaseNotesTool_UI_ctk import PreviewDialog

        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".txt", delete=False,
            prefix="auto_notes_") as tmp:
            tmp.write(notes_text); notes_tmp = tmp.name
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".txt", delete=False,
            prefix="auto_checkinid_") as tmp:
            tmp.write("\n".join(queries)); checkinid_tmp = tmp.name

        try:
            preview = build_preview(
                devnotes_file=devnotes,
                patch_number=patch_label,
                checkinid_file=checkinid_tmp,
                notes_file=notes_tmp,
            )
        except Exception as e:
            messagebox.showerror("Pipeline error", f"Could not build preview:\n\n{e}")
            return
        finally:
            for p in (notes_tmp, checkinid_tmp):
                try: os.unlink(p)
                except OSError: pass

        dialog = PreviewDialog(self.app, preview)
        if not dialog.show():
            return
        try:
            dev, rel, bak = commit_preview(preview, make_backup=True)
        except Exception as e:
            messagebox.showerror("Error", f"Commit failed:\n{e}")
            return
        msg = f"Updated:\n{dev}\n\nCreated:\n{rel}"
        if bak: msg += f"\n\nBackup saved as:\n{bak}"
        messagebox.showinfo("Success", msg)

    # ------------------------------------------------------------------
    # Merge (new behavior)
    # ------------------------------------------------------------------
    def _handle_merge(self, devnotes, patch_label, notes_text):
        from merge_pipeline import build_merge_preview, commit_merge_preview
        from ReleaseNotesTool_UI_ctk import PreviewDialog

        # Find sibling ReleaseNotes path
        devnotes_path = Path(devnotes)
        releasenotes_path = devnotes_path.with_name(
            devnotes_path.name.replace("DevNotes", "ReleaseNotes"))

        # Step 1 — discover conflicts
        try:
            preview = build_merge_preview(
                devnotes_file=devnotes,
                releasenotes_file=str(releasenotes_path),
                patch_label=patch_label,
                new_notes_text=notes_text,
                resolutions=None,
            )
        except ValueError as e:
            messagebox.showerror("Merge error", str(e))
            return
        except Exception as e:
            messagebox.showerror("Merge error", f"Could not build merge preview:\n\n{e}")
            return

        # Step 2 — resolve conflicts if any
        if preview.conflicts:
            dialog = ConflictResolutionDialog(
                self.app, patch_label, preview.conflicts,
                colors=(self._GREEN, self._GREEN_HOVER, self._TEXT, self._TEXT_MUTED, self._BORDER),
            )
            resolutions = dialog.show()
            if resolutions is None:
                return
            try:
                preview = build_merge_preview(
                    devnotes_file=devnotes,
                    releasenotes_file=str(releasenotes_path),
                    patch_label=patch_label,
                    new_notes_text=notes_text,
                    resolutions=resolutions,
                )
            except Exception as e:
                messagebox.showerror("Merge error", f"{e}")
                return

        # Step 3 — show preview via the existing dialog
        try:
            adapter = _MergePreviewAdapter(preview)
            dialog = PreviewDialog(self.app, adapter)
        except Exception as e:
            messagebox.showerror("Preview error", f"Could not open preview:\n\n{e}")
            return

        if not dialog.show():
            return

        try:
            dev, rel, bak = commit_merge_preview(preview, make_backup=True)
        except Exception as e:
            messagebox.showerror("Error", f"Commit failed:\n{e}")
            return
        msg = (f"Merged into {patch_label}.\n\n"
               f"Updated:\n{dev}\n\nUpdated:\n{rel}")
        if bak: msg += f"\n\nBackup saved as:\n{bak}"
        messagebox.showinfo("Success", msg)


class _MergePreviewAdapter:
    """Make a MergePreview look like PipelinePreview for PreviewDialog."""
    def __init__(self, mp):
        self._mp = mp
        self.devnotes_path = mp.devnotes_path
        self.releasenotes_path = mp.releasenotes_path
        self.patch_label = mp.patch_label
        self.patch_date = mp.patch_date
        self.new_patch_block = mp.rebuilt_patch_block
        self.predicted_devnotes = mp.predicted_devnotes
        self.predicted_releasenotes = mp.predicted_releasenotes
        self.requested_checkin_ids = list(mp.final_checkin_ids)
        self.included_checkin_ids  = list(mp.final_checkin_ids)
        self.missing_checkin_ids   = []


class ConflictResolutionDialog(ctk.CTkToplevel):
    """
    Modal dialog: per-conflict choice between "replace with new" (default)
    and "keep existing". show() returns dict[checkin_id, bool] or None.
    """
    def __init__(self, parent, patch_label, conflicts, colors):
        super().__init__(parent)
        green, green_hover, text, text_muted, border = colors
        self.title(f"Resolve conflicts — {patch_label}")
        self.geometry("520x440")
        self.transient(parent)
        self.grab_set()
        self.configure(fg_color="#f4f5f7")

        self._result: dict[str, bool] | None = None
        self._vars: dict[str, ctk.StringVar] = {}

        ctk.CTkLabel(
            self, text=f"{len(conflicts)} check-in(s) already exist in {patch_label}",
            text_color=text, font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(padx=20, pady=(20, 4), anchor="w")
        ctk.CTkLabel(
            self,
            text=("These check-ins are present both in the existing patch "
                  "and in the newly fetched data. Pick which version to "
                  "keep for each."),
            text_color=text_muted, font=ctk.CTkFont(size=12),
            wraplength=480, justify="left", anchor="w",
        ).pack(padx=20, pady=(0, 12), anchor="w")

        scroller = ctk.CTkScrollableFrame(self, fg_color="white",
                                           border_width=1, border_color=border,
                                           corner_radius=8)
        scroller.pack(padx=20, pady=(0, 12), fill="both", expand=True)

        for cid in conflicts:
            row = ctk.CTkFrame(scroller, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=6)
            ctk.CTkLabel(
                row, text=f"Check-in {cid}",
                text_color=text, font=ctk.CTkFont(size=13, weight="bold"),
                anchor="w",
            ).pack(side="left")
            var = ctk.StringVar(value="replace")
            self._vars[cid] = var
            opts = ctk.CTkFrame(row, fg_color="transparent")
            opts.pack(side="right")
            ctk.CTkRadioButton(
                opts, text="Replace with new", variable=var, value="replace",
                fg_color=green, hover_color=green_hover,
            ).pack(side="left", padx=(0, 12))
            ctk.CTkRadioButton(
                opts, text="Keep existing", variable=var, value="keep",
                fg_color=green, hover_color=green_hover,
            ).pack(side="left")

        bulk = ctk.CTkFrame(self, fg_color="transparent")
        bulk.pack(padx=20, pady=(0, 8), fill="x")
        ctk.CTkButton(
            bulk, text="Replace all", height=28,
            fg_color="white", text_color=text,
            border_width=1, border_color=border, hover_color="#f0f0f0",
            command=lambda: self._set_all("replace"),
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            bulk, text="Keep all existing", height=28,
            fg_color="white", text_color=text,
            border_width=1, border_color=border, hover_color="#f0f0f0",
            command=lambda: self._set_all("keep"),
        ).pack(side="left")

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(padx=20, pady=(0, 16), fill="x")
        ctk.CTkButton(
            actions, text="Cancel", height=36,
            fg_color="white", text_color=text,
            border_width=1, border_color=border, hover_color="#f0f0f0",
            command=self._on_cancel,
        ).pack(side="right", padx=(8, 0))
        ctk.CTkButton(
            actions, text="Apply", height=36,
            fg_color=green, hover_color=green_hover, text_color="white",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._on_apply,
        ).pack(side="right")

    def _set_all(self, value):
        for v in self._vars.values():
            v.set(value)

    def _on_apply(self):
        self._result = {cid: (v.get() == "replace") for cid, v in self._vars.items()}
        self.destroy()

    def _on_cancel(self):
        self._result = None
        self.destroy()

    def show(self) -> dict[str, bool] | None:
        self.wait_window()
        return self._result
