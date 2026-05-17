"""
ReleaseNotesTool_UI_ctk.py

Modern UI for the Release Notes Tool in the Lam Research visual style:
  - Dark navy sidebar (#0b1426)
  - Green accent (#1d9e75) for active state and primary actions
  - White card surfaces in the main panel
  - Sidebar navigation (Home / All-in-One / Notes → For_DevNotes / DevNotes → ReleaseNotes)

Requires:  pip install customtkinter
Reuses backend modules:
  - full_pipeline.run_full_pipeline
  - notes_to_for_devnotes.generate_for_devnotes
  - ReleaseNotesCreatorv4.process_dev_notes
"""

from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from full_pipeline import build_preview, commit_preview, PipelinePreview
from notes_to_for_devnotes import generate_for_devnotes
from ReleaseNotesCreatorv4 import process_dev_notes


# =============================================================================
# Color palette (Lam Research-inspired)
# =============================================================================
NAVY        = "#0b1426"   # sidebar / top bar
NAVY_HOVER  = "#142036"   # sidebar nav hover
NAVY_LIGHT  = "#1a2740"   # subtle divider
GREEN       = "#1d9e75"   # active / primary
GREEN_HOVER = "#168865"   # primary hover
GREEN_LIGHT = "#e6f5ef"   # subtle green bg
BG          = "#f4f5f7"   # main canvas
CARD        = "#ffffff"   # card surface
BORDER      = "#e2e5ea"   # card border
TEXT        = "#0b1426"   # primary text
TEXT_MUTED  = "#5a6577"   # secondary text
TEXT_FAINT  = "#8895ab"   # tertiary text


# =============================================================================
# Reusable widgets
# =============================================================================
class LamLogo(ctk.CTkFrame):
    """
    The Lam Research mark + 'Lam RESEARCH' wordmark.

    The mark is a white triangle with a smaller triangular notch cut out at its
    base, mimicking the official Lam Research geometric logo. Since tkinter
    Canvas can't do real shape subtraction, we draw the outer white triangle
    then overlay a smaller triangle filled with the background (navy) color.
    """
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)

        import tkinter as tk
        W, H = 30, 26
        self.canvas = tk.Canvas(
            self, width=W, height=H,
            bg=NAVY, highlightthickness=0, bd=0,
        )

        # Outer white triangle (apex at top center)
        self.canvas.create_polygon(
            W / 2, 1,        # top apex
            W - 1, H - 1,    # bottom right
            1, H - 1,        # bottom left
            fill="white", outline="",
        )

        # Inner cutout triangle — same color as background, sits at the bottom
        # center, pointing up. This creates the notched-base effect of the
        # actual Lam mark.
        inner_h = H * 0.45
        inner_w = W * 0.42
        cx = W / 2
        base_y = H - 2
        self.canvas.create_polygon(
            cx, base_y - inner_h,            # inner apex (pointing up)
            cx + inner_w / 2, base_y,        # inner bottom right
            cx - inner_w / 2, base_y,        # inner bottom left
            fill=NAVY, outline="",
        )

        self.canvas.grid(row=0, column=0, padx=(0, 10))

        ctk.CTkLabel(
            self, text="Lam", text_color="white",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).grid(row=0, column=1, sticky="w")
        ctk.CTkLabel(
            self, text="RESEARCH", text_color="#c8d0dd",
            font=ctk.CTkFont(size=12, weight="normal"),
        ).grid(row=0, column=2, padx=(4, 0), sticky="w")


class NavItem(ctk.CTkButton):
    """A sidebar navigation row. Active = green, inactive = transparent on navy."""
    def __init__(self, master, text: str, icon: str, command, **kwargs):
        super().__init__(
            master,
            text=f"  {icon}   {text}",
            anchor="w",
            corner_radius=8,
            height=40,
            fg_color="transparent",
            hover_color=NAVY_HOVER,
            text_color="#c8d0dd",
            font=ctk.CTkFont(size=14),
            command=command,
            **kwargs,
        )

    def set_active(self, active: bool):
        if active:
            self.configure(
                fg_color=GREEN,
                hover_color=GREEN_HOVER,
                text_color="white",
                font=ctk.CTkFont(size=14, weight="bold"),
            )
        else:
            self.configure(
                fg_color="transparent",
                hover_color=NAVY_HOVER,
                text_color="#c8d0dd",
                font=ctk.CTkFont(size=14),
            )


class Card(ctk.CTkFrame):
    """A white surface card with a subtle border, used in the main canvas."""
    def __init__(self, master, **kwargs):
        super().__init__(
            master,
            fg_color=CARD,
            border_color=BORDER,
            border_width=1,
            corner_radius=12,
            **kwargs,
        )


class FileField(ctk.CTkFrame):
    """
    A labeled file picker row:  [label]  [entry]  [Browse]
    Use .get() to retrieve the chosen path.
    """
    def __init__(self, master, label: str, hint: str = "", **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            self, text=label, anchor="w", width=130,
            text_color=TEXT, font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=(0, 10), pady=6)

        self.var = ctk.StringVar()
        self.entry = ctk.CTkEntry(
            self, textvariable=self.var,
            height=36, border_color=BORDER, border_width=1,
            fg_color="white", text_color=TEXT, corner_radius=8,
            placeholder_text=hint,
        )
        self.entry.grid(row=0, column=1, sticky="ew", pady=6)

        ctk.CTkButton(
            self, text="Browse",
            width=90, height=36, corner_radius=8,
            fg_color="white", text_color=TEXT,
            border_color=BORDER, border_width=1,
            hover_color="#f0f1f4",
            command=self._browse,
        ).grid(row=0, column=2, padx=(10, 0), pady=6)

    def _browse(self):
        path = filedialog.askopenfilename(filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if path:
            self.var.set(path)

    def get(self) -> str:
        return self.var.get().strip()


class TextField(ctk.CTkFrame):
    """A simple labeled text input row."""
    def __init__(self, master, label: str, hint: str = "", **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            self, text=label, anchor="w", width=130,
            text_color=TEXT, font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=(0, 10), pady=6)

        self.var = ctk.StringVar()
        self.entry = ctk.CTkEntry(
            self, textvariable=self.var,
            height=36, border_color=BORDER, border_width=1,
            fg_color="white", text_color=TEXT, corner_radius=8,
            placeholder_text=hint,
        )
        self.entry.grid(row=0, column=1, sticky="ew", pady=6)

    def get(self) -> str:
        return self.var.get().strip()


class PatchTypeNumberField(ctk.CTkFrame):
    """
    Row that captures the full patch identifier in two parts:
      - patch type (combobox; editable, defaults to 'Patch', presets include
        'LabPatch' and 'HomeMade')
      - patch number (entry)

    Layout (single row):
        [Patch Number]  [type ▾]  [number]   →  PatchXX (live preview)

    .get() returns the concatenated string, e.g. "Patch10" or "LabPatch3".
    """
    PRESET_TYPES = ("Patch", "LabPatch", "HomeMade")

    def __init__(self, master, label: str = "Patch Number", **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.grid_columnconfigure(2, weight=1)
        self.grid_columnconfigure(3, weight=2)

        ctk.CTkLabel(
            self, text=label, anchor="w", width=130,
            text_color=TEXT, font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=(0, 10), pady=6)

        # Patch type combobox (editable so user can also type a custom prefix)
        self.type_var = ctk.StringVar(value="Patch")
        self.type_var.trace_add("write", self._update_preview)
        self.type_combo = ctk.CTkComboBox(
            self,
            values=list(self.PRESET_TYPES),
            variable=self.type_var,
            width=130, height=36, corner_radius=8,
            border_color=BORDER, border_width=1,
            fg_color="white", text_color=TEXT,
            button_color=NAVY, button_hover_color=NAVY_HOVER,
            dropdown_fg_color="white", dropdown_text_color=TEXT,
            dropdown_hover_color="#f0f1f4",
            command=self._on_type_change,
        )
        self.type_combo.grid(row=0, column=1, sticky="w", padx=(0, 8), pady=6)

        # Patch number entry (accepts integers or decimals: 10, 5.1, 3.2, etc.)
        self.num_var = ctk.StringVar()
        self.num_var.trace_add("write", self._update_preview)
        self.num_entry = ctk.CTkEntry(
            self, textvariable=self.num_var,
            height=36, border_color=BORDER, border_width=1,
            fg_color="white", text_color=TEXT, corner_radius=8,
            placeholder_text="e.g. 10 or 5.1",
        )
        self.num_entry.grid(row=0, column=2, sticky="ew", pady=6)

        # Live preview of the combined value
        self.preview = ctk.CTkLabel(
            self, text="→  Patch", anchor="w",
            text_color=GREEN, font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.preview.grid(row=0, column=3, sticky="w", padx=(12, 0), pady=6)

    def _on_type_change(self, _value):
        self._update_preview()

    def _update_preview(self, *_args):
        full = self.get()
        self.preview.configure(text=f"→  {full}" if full else "→  (empty)")

    def get(self) -> str:
        """Return the combined patch label, e.g. 'Patch10' or 'LabPatch3'."""
        ptype = self.type_var.get().strip()
        pnum = self.num_var.get().strip()
        return f"{ptype}{pnum}"


# =============================================================================
# Preview dialog
# =============================================================================
class PreviewDialog(ctk.CTkToplevel):
    """
    Modal preview window shown before any files are written.

    Tabs:
      - Check-in IDs   (counts + per-ID status, included/missing)
      - DevNotes       (full updated DevNotes preview, scrollable)
      - ReleaseNotes   (full generated ReleaseNotes preview, scrollable)

    .show() returns True if the user clicked "Confirm & Write", False otherwise.
    """
    def __init__(self, parent, preview: PipelinePreview):
        super().__init__(parent)
        self.preview = preview
        self.confirmed = False

        self.title(f"Preview — {preview.patch_label}   ·   {preview.patch_date}")
        self.geometry("900x640")
        self.minsize(820, 560)
        self.configure(fg_color=BG)

        # Make this window modal: capture focus, block parent until closed.
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._build_header()
        self._build_summary_bar()
        self._build_tabs()
        self._build_actions()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color=NAVY, corner_radius=0, height=56)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header,
            text=f"Preview  —  {self.preview.patch_label}  ·  {self.preview.patch_date}",
            text_color="white",
            font=ctk.CTkFont(size=15, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, padx=20, pady=14, sticky="w")

    def _build_summary_bar(self):
        bar = ctk.CTkFrame(self, fg_color=CARD, corner_radius=0, height=80)
        bar.grid(row=1, column=0, sticky="ew")
        bar.grid_propagate(False)
        bar.grid_columnconfigure(99, weight=1)  # right padding

        n_included = len(self.preview.included_checkin_ids)
        n_missing = len(self.preview.missing_checkin_ids)
        n_lines_added = len(self.preview.new_patch_block.splitlines())

        self._stat(bar, 0, str(n_included), "Check-ins included", GREEN)
        self._stat(bar, 1, str(n_missing),  "Missing from Notes.txt",
                   "#d97706" if n_missing else TEXT_FAINT)
        self._stat(bar, 2, f"+{n_lines_added}", "Lines added to DevNotes", TEXT)

        # Target paths (right side, small)
        paths = ctk.CTkFrame(bar, fg_color="transparent")
        paths.grid(row=0, column=99, padx=24, pady=14, sticky="e")
        ctk.CTkLabel(
            paths,
            text=f"DevNotes:     {self._shorten(str(self.preview.devnotes_path))}",
            text_color=TEXT_MUTED, font=ctk.CTkFont(size=11), anchor="e",
        ).pack(anchor="e")
        ctk.CTkLabel(
            paths,
            text=f"ReleaseNotes: {self._shorten(str(self.preview.releasenotes_path))}",
            text_color=TEXT_MUTED, font=ctk.CTkFont(size=11), anchor="e",
        ).pack(anchor="e")

    def _stat(self, parent, col: int, value: str, label: str, color: str):
        wrap = ctk.CTkFrame(parent, fg_color="transparent")
        wrap.grid(row=0, column=col, padx=(24 if col == 0 else 32, 0), pady=12, sticky="w")
        ctk.CTkLabel(
            wrap, text=value, text_color=color,
            font=ctk.CTkFont(size=24, weight="bold"), anchor="w",
        ).pack(anchor="w")
        ctk.CTkLabel(
            wrap, text=label, text_color=TEXT_FAINT,
            font=ctk.CTkFont(size=11), anchor="w",
        ).pack(anchor="w")

    @staticmethod
    def _shorten(path: str, max_len: int = 60) -> str:
        if len(path) <= max_len:
            return path
        return "…" + path[-(max_len - 1):]

    def _build_tabs(self):
        # CTkTabview gives us the segmented control look at top
        tabs = ctk.CTkTabview(
            self,
            fg_color=CARD,
            segmented_button_fg_color=BG,
            segmented_button_selected_color=GREEN,
            segmented_button_selected_hover_color=GREEN_HOVER,
            segmented_button_unselected_color=BG,
            segmented_button_unselected_hover_color="#e8eaee",
            text_color=TEXT,
            corner_radius=0,
            border_width=0,
        )
        tabs.grid(row=2, column=0, sticky="nsew", padx=0, pady=0)

        # ------- Tab 1: Check-in IDs -------
        t_ids = tabs.add("Check-in IDs")
        t_ids.grid_columnconfigure(0, weight=1)
        t_ids.grid_rowconfigure(0, weight=1)
        self._build_checkin_tab(t_ids)

        # ------- Tab 2: DevNotes preview -------
        t_dev = tabs.add("DevNotes preview")
        t_dev.grid_columnconfigure(0, weight=1)
        t_dev.grid_rowconfigure(0, weight=1)
        self._fill_text_tab(t_dev, self.preview.predicted_devnotes,
                            highlight=self.preview.new_patch_block)

        # ------- Tab 3: ReleaseNotes preview -------
        t_rel = tabs.add("ReleaseNotes preview")
        t_rel.grid_columnconfigure(0, weight=1)
        t_rel.grid_rowconfigure(0, weight=1)
        self._fill_text_tab(t_rel, self.preview.predicted_releasenotes)

        # Land on the most useful tab by default
        tabs.set("Check-in IDs" if self.preview.missing_checkin_ids else "DevNotes preview")

    def _build_checkin_tab(self, parent):
        wrap = ctk.CTkScrollableFrame(parent, fg_color=CARD, corner_radius=0)
        wrap.grid(row=0, column=0, sticky="nsew", padx=16, pady=12)
        wrap.grid_columnconfigure(0, weight=1)

        # Missing IDs section (highlighted if any)
        if self.preview.missing_checkin_ids:
            warn = ctk.CTkFrame(wrap, fg_color="#fef3c7", corner_radius=8)
            warn.grid(row=0, column=0, sticky="ew", pady=(0, 14))
            warn.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(
                warn,
                text=(
                    f"⚠ {len(self.preview.missing_checkin_ids)} ID(s) in checkinid.txt "
                    f"were NOT found in Notes.txt:"
                ),
                text_color="#78350f",
                font=ctk.CTkFont(size=13, weight="bold"),
                anchor="w", justify="left",
            ).grid(row=0, column=0, padx=14, pady=(10, 4), sticky="w")
            ctk.CTkLabel(
                warn,
                text=", ".join(self.preview.missing_checkin_ids),
                text_color="#78350f",
                font=ctk.CTkFont(size=12, family="Courier"),
                anchor="w", justify="left", wraplength=820,
            ).grid(row=1, column=0, padx=14, pady=(0, 10), sticky="w")

        # Included IDs section
        ctk.CTkLabel(
            wrap,
            text=f"Check-ins that will be added ({len(self.preview.included_checkin_ids)}):",
            text_color=TEXT, font=ctk.CTkFont(size=13, weight="bold"), anchor="w",
        ).grid(row=1, column=0, sticky="w", pady=(0, 8))

        if not self.preview.included_checkin_ids:
            ctk.CTkLabel(
                wrap, text="(none)", text_color=TEXT_FAINT,
                font=ctk.CTkFont(size=12), anchor="w",
            ).grid(row=2, column=0, sticky="w")
        else:
            for i, cid in enumerate(self.preview.included_checkin_ids, start=2):
                row = ctk.CTkFrame(wrap, fg_color=BG, corner_radius=6)
                row.grid(row=i, column=0, sticky="ew", pady=2)
                row.grid_columnconfigure(1, weight=1)
                ctk.CTkLabel(
                    row, text="✓", text_color=GREEN,
                    font=ctk.CTkFont(size=14, weight="bold"), width=24,
                ).grid(row=0, column=0, padx=(10, 4), pady=6)
                ctk.CTkLabel(
                    row, text=cid, text_color=TEXT,
                    font=ctk.CTkFont(size=12, family="Courier"), anchor="w",
                ).grid(row=0, column=1, padx=(0, 10), pady=6, sticky="w")

    def _fill_text_tab(self, parent, content: str, highlight: str = ""):
        """
        Render `content` in a read-only scrolling text widget. If `highlight` is
        provided, the substring is given a green background so the new patch
        block stands out in the DevNotes preview.
        """
        import tkinter as tk
        from tkinter import scrolledtext

        # CTkTextbox doesn't support tag-based highlighting as cleanly as
        # tk.Text, so we use a tk.Text with matching styling.
        text = scrolledtext.ScrolledText(
            parent,
            wrap="none",
            bg="#fafbfc", fg=TEXT,
            insertbackground=TEXT,
            relief="flat", borderwidth=0,
            font=("Courier", 11),
            padx=12, pady=10,
        )
        text.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)

        text.insert("1.0", content)

        # Highlight the new patch block (DevNotes tab) so it's easy to spot
        if highlight and highlight in content:
            start_idx = content.index(highlight)
            # Convert byte offset to tk text index using line/column
            line_start = content[:start_idx].count("\n") + 1
            col_start = start_idx - (content.rfind("\n", 0, start_idx) + 1)
            end_idx = start_idx + len(highlight)
            line_end = content[:end_idx].count("\n") + 1
            col_end = end_idx - (content.rfind("\n", 0, end_idx) + 1)
            text.tag_add("new", f"{line_start}.{col_start}", f"{line_end}.{col_end}")
            text.tag_config("new", background="#e6f5ef")

        text.configure(state="disabled")  # read-only

    def _build_actions(self):
        bar = ctk.CTkFrame(self, fg_color=CARD, corner_radius=0, height=64)
        bar.grid(row=3, column=0, sticky="ew")
        bar.grid_propagate(False)
        bar.grid_columnconfigure(0, weight=1)

        btns = ctk.CTkFrame(bar, fg_color="transparent")
        btns.grid(row=0, column=0, padx=20, pady=12, sticky="e")

        ctk.CTkButton(
            btns, text="Cancel",
            width=120, height=40, corner_radius=8,
            fg_color="white", text_color=TEXT,
            border_color=BORDER, border_width=1,
            hover_color="#f0f1f4",
            font=ctk.CTkFont(size=13),
            command=self._on_cancel,
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            btns, text="Confirm & Write Files",
            width=200, height=40, corner_radius=8,
            fg_color=GREEN, hover_color=GREEN_HOVER,
            text_color="white",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._on_confirm,
        ).pack(side="left")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def _on_confirm(self):
        self.confirmed = True
        self.grab_release()
        self.destroy()

    def _on_cancel(self):
        self.confirmed = False
        self.grab_release()
        self.destroy()

    def show(self) -> bool:
        """Block until the dialog is closed; return True if user confirmed."""
        self.wait_window()
        return self.confirmed


# =============================================================================
# Main application
# =============================================================================
class ReleaseNotesApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        ctk.set_appearance_mode("light")
        self.title("Release Notes Tool")
        self.geometry("1000x640")
        self.minsize(900, 580)
        self.configure(fg_color=BG)

        # ---- Layout: top bar | (sidebar + main) -----------------------------
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_topbar()

        body = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        body.grid(row=1, column=0, sticky="nsew")
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        self._build_sidebar(body)
        self._build_main(body)

        # Show home by default
        self.show_page("home")

    # ------------------------------------------------------------------
    # Top bar
    # ------------------------------------------------------------------
    def _build_topbar(self):
        bar = ctk.CTkFrame(self, fg_color=NAVY, corner_radius=0, height=56)
        bar.grid(row=0, column=0, sticky="ew")
        bar.grid_propagate(False)
        bar.grid_columnconfigure(2, weight=1)

        LamLogo(bar).grid(row=0, column=0, padx=20, pady=14, sticky="w")

        # Vertical divider + product name
        sep = ctk.CTkFrame(bar, fg_color=NAVY_LIGHT, width=1, height=24)
        sep.grid(row=0, column=1, padx=(0, 14), pady=16)

        ctk.CTkLabel(
            bar, text="Release Notes Tool",
            text_color="#c8d0dd", font=ctk.CTkFont(size=14),
        ).grid(row=0, column=2, sticky="w")

    # ------------------------------------------------------------------
    # Sidebar
    # ------------------------------------------------------------------
    def _build_sidebar(self, parent):
        side = ctk.CTkFrame(parent, fg_color=NAVY, corner_radius=0, width=240)
        side.grid(row=0, column=0, sticky="nsw")
        side.grid_propagate(False)
        side.grid_rowconfigure(99, weight=1)  # push version to bottom

        # Title block
        ctk.CTkLabel(
            side, text="Release Notes", text_color="white",
            font=ctk.CTkFont(size=16, weight="bold"), anchor="w",
        ).grid(row=0, column=0, padx=20, pady=(22, 2), sticky="w")
        ctk.CTkLabel(
            side, text="Fremont", text_color=TEXT_FAINT,
            font=ctk.CTkFont(size=12), anchor="w",
        ).grid(row=1, column=0, padx=20, pady=(0, 18), sticky="w")

        # Section label
        ctk.CTkLabel(
            side, text="WORKFLOW", text_color=TEXT_FAINT,
            font=ctk.CTkFont(size=11, weight="bold"), anchor="w",
        ).grid(row=2, column=0, padx=22, pady=(0, 6), sticky="w")

        # Nav items
        self.nav_items: dict[str, NavItem] = {}
        nav_def = [
            ("home",        "Home",                  "⌂"),
            ("all_in_one",  "All-in-One",            "▦"),
            ("for_devnotes","Notes → For_DevNotes",  "✎"),
            ("release",     "DevNotes → ReleaseNotes","↻"),
        ]
        for i, (key, label, icon) in enumerate(nav_def, start=3):
            item = NavItem(side, text=label, icon=icon,
                           command=lambda k=key: self.show_page(k))
            item.grid(row=i, column=0, padx=12, pady=2, sticky="ew")
            side.grid_columnconfigure(0, weight=1)
            self.nav_items[key] = item

        # Footer: author credit + version (row 99 is the spacer that pushes
        # these to the bottom of the sidebar)
        ctk.CTkLabel(
            side, text="Written by Matthew Lee", text_color=TEXT_FAINT,
            font=ctk.CTkFont(size=11),
        ).grid(row=100, column=0, padx=20, pady=(18, 0), sticky="w")
        ctk.CTkLabel(
            side, text="Version 1.0.0", text_color=TEXT_FAINT,
            font=ctk.CTkFont(size=11),
        ).grid(row=101, column=0, padx=20, pady=(2, 18), sticky="w")

    # ------------------------------------------------------------------
    # Main content area (one frame per page, stacked, raised on demand)
    # ------------------------------------------------------------------
    def _build_main(self, parent):
        self.main = ctk.CTkFrame(parent, fg_color=BG, corner_radius=0)
        self.main.grid(row=0, column=1, sticky="nsew")
        self.main.grid_rowconfigure(0, weight=1)
        self.main.grid_columnconfigure(0, weight=1)

        self.pages: dict[str, ctk.CTkFrame] = {}
        self.pages["home"]         = self._build_home()
        self.pages["all_in_one"]   = self._build_all_in_one()
        self.pages["for_devnotes"] = self._build_for_devnotes()
        self.pages["release"]      = self._build_release()

        for page in self.pages.values():
            page.grid(row=0, column=0, sticky="nsew")

    def show_page(self, key: str):
        for k, item in self.nav_items.items():
            item.set_active(k == key)
        self.pages[key].tkraise()

    # ------------------------------------------------------------------
    # Page header helper
    # ------------------------------------------------------------------
    def _page(self, title: str, subtitle: str) -> ctk.CTkFrame:
        page = ctk.CTkFrame(self.main, fg_color=BG)
        page.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            page, text=title, text_color=TEXT,
            font=ctk.CTkFont(size=24, weight="bold"), anchor="w",
        ).grid(row=0, column=0, padx=32, pady=(28, 2), sticky="w")
        ctk.CTkLabel(
            page, text=subtitle, text_color=TEXT_MUTED,
            font=ctk.CTkFont(size=13), anchor="w",
        ).grid(row=1, column=0, padx=32, pady=(0, 22), sticky="w")

        return page

    # ------------------------------------------------------------------
    # Home page (overview cards)
    # ------------------------------------------------------------------
    def _build_home(self):
        page = self._page(
            "Release Notes Tool",
            "Build DevNotes and ReleaseNotes from check-in lists.",
        )

        grid = ctk.CTkFrame(page, fg_color=BG)
        grid.grid(row=2, column=0, padx=32, pady=0, sticky="nsew")
        grid.grid_columnconfigure((0, 1), weight=1)

        cards = [
            ("all_in_one",   "▦", "Run Full Pipeline",
             "DevNotes + patch number + check-ins\n→ updated DevNotes and ReleaseNotes."),
            ("for_devnotes", "✎", "Notes → For_DevNotes",
             "Filter raw notes by check-in IDs\nand clean internal headers."),
            ("release",      "↻", "DevNotes → ReleaseNotes",
             "Regenerate ReleaseNotes.txt from\nan existing DevNotes file."),
            ("home",         "✓", "About",
             "Lam Research release notes\nautomation, v1.0.0."),
        ]
        for i, (target, icon, title, desc) in enumerate(cards):
            self._home_card(grid, i // 2, i % 2, icon, title, desc, target)

        return page

    def _home_card(self, parent, row, col, icon, title, desc, target):
        card = Card(parent)
        card.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")
        card.grid_columnconfigure(1, weight=1)

        # Icon tile
        tile = ctk.CTkFrame(card, fg_color=NAVY, corner_radius=10, width=48, height=48)
        tile.grid(row=0, column=0, padx=16, pady=16)
        tile.grid_propagate(False)
        ctk.CTkLabel(
            tile, text=icon, text_color="white",
            font=ctk.CTkFont(size=22),
        ).place(relx=0.5, rely=0.5, anchor="center")

        # Text
        text_wrap = ctk.CTkFrame(card, fg_color="transparent")
        text_wrap.grid(row=0, column=1, padx=(0, 16), pady=16, sticky="nsew")

        ctk.CTkLabel(
            text_wrap, text=title, text_color=TEXT,
            font=ctk.CTkFont(size=15, weight="bold"), anchor="w",
        ).pack(anchor="w")
        ctk.CTkLabel(
            text_wrap, text=desc, text_color=TEXT_MUTED,
            font=ctk.CTkFont(size=12), anchor="w", justify="left",
        ).pack(anchor="w", pady=(4, 0))

        # Make whole card clickable
        def click(_=None, t=target): self.show_page(t)
        for w in (card, tile, text_wrap, *text_wrap.winfo_children()):
            w.bind("<Button-1>", click)

    # ------------------------------------------------------------------
    # Page: All-in-One
    # ------------------------------------------------------------------
    def _build_all_in_one(self):
        page = self._page(
            "Run Full Pipeline",
            "Add a new patch to DevNotes and regenerate ReleaseNotes in one step.",
        )

        card = Card(page)
        card.grid(row=2, column=0, padx=32, pady=0, sticky="ew")
        card.grid_columnconfigure(0, weight=1)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.grid(row=0, column=0, padx=24, pady=20, sticky="ew")
        inner.grid_columnconfigure(0, weight=1)

        self.aio_devnotes  = FileField(inner, "DevNotes.txt",  "Select your existing DevNotes file")
        self.aio_patch     = PatchTypeNumberField(inner, "Patch Number")
        self.aio_checkinid = FileField(inner, "checkinid.txt", "List of check-in IDs to include")
        self.aio_notes     = FileField(inner, "Notes.txt",     "Raw developer notes")

        for i, w in enumerate((self.aio_devnotes, self.aio_patch,
                               self.aio_checkinid, self.aio_notes)):
            w.grid(row=i, column=0, sticky="ew")

        # Backup toggle
        self.aio_backup = ctk.BooleanVar(value=True)
        opt = ctk.CTkFrame(inner, fg_color="transparent")
        opt.grid(row=4, column=0, sticky="w", pady=(8, 0))
        ctk.CTkCheckBox(
            opt, text="Create timestamped backup of DevNotes.txt",
            variable=self.aio_backup,
            text_color=TEXT, font=ctk.CTkFont(size=12),
            fg_color=GREEN, hover_color=GREEN_HOVER,
            border_color=BORDER, border_width=1,
            checkmark_color="white",
        ).pack(side="left")

        # Run button
        ctk.CTkButton(
            inner, text="Run Full Pipeline",
            height=42, corner_radius=10,
            fg_color=GREEN, hover_color=GREEN_HOVER,
            text_color="white",
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._run_all_in_one,
        ).grid(row=5, column=0, pady=(18, 0), sticky="ew")

        return page

    def _run_all_in_one(self):
        if not self.aio_devnotes.get():
            messagebox.showerror("Error", "Select DevNotes.txt")
            return
        # Validate patch input: must have BOTH a type and a number, and the
        # number portion must not be empty (otherwise we'd insert "Patch" with
        # no version).
        if not self.aio_patch.type_var.get().strip():
            messagebox.showerror("Error", "Select or type a patch type (e.g. Patch, LabPatch, HomeMade)")
            return
        if not self.aio_patch.num_var.get().strip():
            messagebox.showerror("Error", "Enter a patch number (e.g. 10 or 5.1)")
            return
        if not self.aio_checkinid.get() or not self.aio_notes.get():
            messagebox.showerror("Error", "Select both checkinid.txt and Notes.txt")
            return

        try:
            preview = build_preview(
                devnotes_file=self.aio_devnotes.get(),
                patch_number=self.aio_patch.get(),
                checkinid_file=self.aio_checkinid.get(),
                notes_file=self.aio_notes.get(),
            )
        except Exception as e:
            messagebox.showerror("Error", f"Could not build preview:\n{e}")
            return

        # Show the preview dialog; it blocks until the user confirms or cancels.
        dialog = PreviewDialog(self, preview)
        confirmed = dialog.show()
        if not confirmed:
            return  # user cancelled — nothing was written

        try:
            dev, rel, bak = commit_preview(preview, make_backup=self.aio_backup.get())
        except Exception as e:
            messagebox.showerror("Error", f"Commit failed:\n{e}")
            return

        msg = f"Updated:\n{dev}\n\nCreated:\n{rel}"
        if bak is not None:
            msg += f"\n\nBackup saved as:\n{bak}"
        messagebox.showinfo("Success", msg)

    # ------------------------------------------------------------------
    # Page: Notes → For_DevNotes
    # ------------------------------------------------------------------
    def _build_for_devnotes(self):
        page = self._page(
            "Notes → For_DevNotes",
            "Filter raw developer notes by check-in IDs.",
        )

        card = Card(page)
        card.grid(row=2, column=0, padx=32, pady=0, sticky="ew")
        card.grid_columnconfigure(0, weight=1)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.grid(row=0, column=0, padx=24, pady=20, sticky="ew")
        inner.grid_columnconfigure(0, weight=1)

        self.fd_checkinid = FileField(inner, "checkinid.txt", "List of check-in IDs")
        self.fd_notes     = FileField(inner, "Notes.txt",     "Raw developer notes")

        self.fd_checkinid.grid(row=0, column=0, sticky="ew")
        self.fd_notes.grid(row=1, column=0, sticky="ew")

        ctk.CTkButton(
            inner, text="Generate For_DevNotes.txt",
            height=42, corner_radius=10,
            fg_color=GREEN, hover_color=GREEN_HOVER,
            text_color="white",
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._run_for_devnotes,
        ).grid(row=2, column=0, pady=(18, 0), sticky="ew")

        return page

    def _run_for_devnotes(self):
        if not self.fd_checkinid.get() or not self.fd_notes.get():
            messagebox.showerror("Error", "Select both checkinid.txt and Notes.txt")
            return

        out = Path(self.fd_notes.get()).parent / "For_DevNotes.txt"
        try:
            generate_for_devnotes(self.fd_checkinid.get(), self.fd_notes.get(), out)
        except Exception as e:
            messagebox.showerror("Error", f"Generation failed:\n{e}")
            return

        messagebox.showinfo("Success", f"Created:\n{out}")

    # ------------------------------------------------------------------
    # Page: DevNotes → ReleaseNotes
    # ------------------------------------------------------------------
    def _build_release(self):
        page = self._page(
            "DevNotes → ReleaseNotes",
            "Regenerate ReleaseNotes.txt from an existing DevNotes file.",
        )

        card = Card(page)
        card.grid(row=2, column=0, padx=32, pady=0, sticky="ew")
        card.grid_columnconfigure(0, weight=1)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.grid(row=0, column=0, padx=24, pady=20, sticky="ew")
        inner.grid_columnconfigure(0, weight=1)

        self.rn_devnotes = FileField(inner, "DevNotes.txt", "Select your DevNotes file")
        self.rn_devnotes.grid(row=0, column=0, sticky="ew")

        ctk.CTkButton(
            inner, text="Generate ReleaseNotes.txt",
            height=42, corner_radius=10,
            fg_color=GREEN, hover_color=GREEN_HOVER,
            text_color="white",
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._run_release,
        ).grid(row=1, column=0, pady=(18, 0), sticky="ew")

        return page

    def _run_release(self):
        if not self.rn_devnotes.get():
            messagebox.showerror("Error", "Select DevNotes.txt")
            return

        dev = Path(self.rn_devnotes.get())
        out = dev.parent / "ReleaseNotes.txt"
        try:
            process_dev_notes(str(dev), str(out))
        except Exception as e:
            messagebox.showerror("Error", f"Generation failed:\n{e}")
            return

        messagebox.showinfo("Success", f"Created:\n{out}")


if __name__ == "__main__":
    app = ReleaseNotesApp()
    app.mainloop()
