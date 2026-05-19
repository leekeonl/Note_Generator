# Release Notes Tool

A desktop GUI that automates an internal release-notes workflow I used to do
by hand at work. Built to solve a real, recurring pain point — generating
customer-facing release notes from raw developer check-in notes — and to
explore design patterns around safe file mutation, preview-before-commit, and
modern Python GUI work.

---

## Problem

Every patch release at work required manually:

1. Filtering 50+ developer check-ins by ID
2. Stripping internal-only metadata (`Developer:`, `Timestamp:`, auto-merge
   blocks, …)
3. Reformatting each section to match the customer-facing template
4. Inserting the new patch block in the correct location of `DevNotes.txt`
5. Re-generating the customer-facing `ReleaseNotes.txt`

The work took roughly 30 minutes per release and was error-prone. A single
typo in a check-in ID would silently exclude that fix from the released
notes, and there was no easy way to catch it until a customer noticed.

## Solution

|                                  | Before          | After             |
| -------------------------------- | --------------- | ----------------- |
| Time per release                 | ~30 min         | ~30 sec           |
| Manual reformatting steps        | 50+             | 0                 |
| Silent omissions on typo'd IDs   | Possible        | Flagged in preview|
| Rollback if something is wrong   | Manual undo     | Auto backup       |

---

## Key features

- **Preview-before-write** — every run opens a modal preview window with
  three tabs (Check-in IDs / DevNotes preview / ReleaseNotes preview) so I
  can verify exactly what will change before any file is touched.
- **Missing-ID detection** — if a check-in ID appears in `checkinid.txt` but
  not in `Notes.txt`, the preview flags it with a yellow warning before
  commit.
- **Automatic timestamped backups** — every commit writes
  `DevNotes.YYYYMMDD_HHMMSS.bak.txt` before modifying the original, so
  multiple runs in the same day never overwrite each other.
- **Flexible patch labels** — `Patch`, `LabPatch`, `HomeMade`, or any custom
  prefix, with integer (`10`) or decimal (`5.1`) numbers.
- **Format normalization** — handles two real-world note formats developers
  use (section header on its own line vs. inline with content) without
  breaking either.
- **Standalone helper pages** — run just one stage of the pipeline if that's
  all you need.

---

## Design decisions

A few choices worth calling out:

- **Two-stage pipeline (`build_preview` + `commit_preview`).** Previewing
  is a pure read-only operation that touches no files. Committing is
  the only place that mutates disk. This separation makes the preview
  trustworthy and made it easy to add the modal preview window without
  duplicating logic.
- **Timestamped backups instead of a single `.bak`.** Multiple runs per day
  never clobber each other. Naming pattern is sortable.
- **Generalized patch regex.** `^[A-Za-z]+\d+(?:\.\d+)?$` covers
  `Patch10`, `LabPatch3`, `HomeMade5.1`, and arbitrary user-defined
  prefixes — matching how teams actually label patches in practice.
- **In-memory text transforms with thin file-IO wrappers.** All the parsing
  and reformatting is pure-function on strings; only two small functions
  read or write files. Makes the core logic easy to test and reason about.
- **customtkinter for the GUI.** Native-looking widgets, modern theming,
  and no platform-specific drawing code. Single-file build with PyInstaller.

---

## Screenshots

*(Add screenshots here. The All-in-One page and the Preview dialog are the
two views worth showing.)*

---

## Requirements

- Python 3.10 or newer
- [customtkinter](https://pypi.org/project/customtkinter/)

```bash
pip install customtkinter
```

---

## Usage

```bash
python ReleaseNotesTool_UI_ctk.py
```

### All-in-One workflow

1. Select your existing `DevNotes.txt`.
2. Pick the patch type from the dropdown (`Patch`, `LabPatch`, `HomeMade`,
   or type your own) and enter the patch number (`10` or `5.1`).
3. Select `checkinid.txt` (the list of check-in IDs to include).
4. Select `Notes.txt` (the raw developer notes).
5. Click **Run Full Pipeline**.
6. Review the Preview dialog. If anything looks off, click **Cancel**.
7. Click **Confirm & Write Files** to apply the changes.

### Patch label examples

| Type      | Number | Result        |
| --------- | ------ | ------------- |
| Patch     | 10     | `Patch10`     |
| Patch     | 5.1    | `Patch5.1`    |
| LabPatch  | 3      | `LabPatch3`   |
| HomeMade  | 5      | `HomeMade5`   |
| *custom*  | 2      | `HotFix2`     |

---

## File structure

```
NoteGenerator/
├── ReleaseNotesTool_UI_ctk.py   # GUI entry point (customtkinter)
├── ReleaseNotesTool_UI.py       # Original tkinter prototype (kept for reference)
├── full_pipeline.py             # build_preview() + commit_preview() + run_full_pipeline()
├── notes_to_for_devnotes.py     # Filter raw Notes.txt by check-in IDs
├── ReleaseNotesCreatorv4.py     # Convert DevNotes.txt → ReleaseNotes.txt
├── docs/                        # Plain-text versions of the README
└── README.md
```

### Pipeline architecture

The backend is structured so that previewing is side-effect free:

```
build_preview(devnotes, patch, checkinids, notes)
    → PipelinePreview   (pure / read-only)

commit_preview(preview, make_backup=True)
    → writes files + creates backup

run_full_pipeline(...)   # backward-compatible one-shot wrapper
    = commit_preview(build_preview(...))
```

---

## Input file formats

### `checkinid.txt`

Any text containing check-in version numbers in `N.NNNN` format. Names are
optional; only the numeric part is used for matching.

```
alice 0.4091
bob 0.3968
0.4260
```

### `Notes.txt`

Raw developer notes. Each check-in block starts with `Checkin ID:` and is
separated by 80-dash separator lines. The tool automatically strips out
internal-only headers (`Developer:`, `Timestamp:`, `Release Notes Needed:`,
`[Auto Merge Wizard]` blocks, etc.) before inserting into DevNotes.

### `DevNotes.txt`

Must begin with a `Base Version: ...` line. New patches are inserted
immediately below this line.

---

## Building a standalone executable

### macOS / Linux

```bash
pip install pyinstaller

python3 -m PyInstaller --clean --onefile --windowed \
    --collect-all customtkinter --collect-all darkdetect \
    --name ReleaseNotesTool ReleaseNotesTool_UI_ctk.py
```

### Windows

```bat
pip install pyinstaller

python -m PyInstaller --clean --onefile --windowed --collect-all customtkinter --collect-all darkdetect --name ReleaseNotesTool ReleaseNotesTool_UI_ctk.py
```

Output:
- macOS / Linux: `dist/ReleaseNotesTool`
- Windows: `dist/ReleaseNotesTool.exe`

The `--collect-all` flags are required so that customtkinter's theme and
font assets are bundled inside the executable.

> **Note:** PyInstaller builds are platform-specific. Build on the OS you
> intend to distribute to.

---

## Restoring from a backup

Backups are saved next to `DevNotes.txt` with a timestamped filename:

```
DevNotes.txt
DevNotes.20260516_205412.bak.txt   ← backup from May 16, 8:54 PM
DevNotes.20260517_091203.bak.txt   ← backup from May 17, 9:12 AM
```

To restore, rename the desired backup to `DevNotes.txt` (overwriting the
current one). An in-app "Restore from Backup" flow is on the roadmap.

---

## Roadmap

- [ ] In-app backup restoration UI
- [ ] Remember last-used file paths between sessions
- [ ] Auto-suggest next patch number from existing DevNotes
- [ ] Optional output preview pane inside the main window

---

## Author

Written by Matthew Lee.
