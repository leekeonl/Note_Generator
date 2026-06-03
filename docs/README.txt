================================================================================
                            RELEASE NOTES TOOL
================================================================================

A desktop GUI that automates an internal release-notes workflow I used to do
by hand at work. Built to solve a real, recurring pain point - generating
customer-facing release notes from raw developer check-in notes - and to
explore design patterns around safe file mutation, preview-before-commit,
pluggable data sources, and modern Python GUI work.

VERSION 1.2.0 - adds automatic note fetching from a commit-tracking system
and a merge mode for re-building existing patches.


--------------------------------------------------------------------------------
PROBLEM
--------------------------------------------------------------------------------

Every patch release at work required manually:

    1. Tracking down 50+ developer check-ins from a commit system, one by one
    2. Pasting them into a Notes.txt file
    3. Filtering them by check-in ID
    4. Stripping internal-only metadata (Developer:, Timestamp:, auto-merge
       blocks, etc.)
    5. Reformatting each section to match the customer-facing template
    6. Inserting the new patch block in the correct location of DevNotes.txt
    7. Re-generating the customer-facing ReleaseNotes.txt

The work took roughly 30 minutes per release and was error-prone. A single
typo in a check-in ID would silently exclude that fix from the released
notes, and there was no easy way to catch it until a customer noticed.


--------------------------------------------------------------------------------
SOLUTION
--------------------------------------------------------------------------------

                                      Before              After
    -------------------------------- ------------------- ----------------------
    Time per release                 ~30 min             ~30 sec
    Manual reformatting steps        50+                 0
    Manual note collection           Copy-paste each     Fetched by PR number
    Silent omissions on typo'd IDs   Possible            Flagged in preview
    Rollback if something is wrong   Manual undo         Auto backup
    Adding PR to an existing patch   Hand-edit file      Merge mode


--------------------------------------------------------------------------------
KEY FEATURES
--------------------------------------------------------------------------------

Auto-Generate (v1.2)
    Skip the Notes.txt collection step entirely. Type a list of PR numbers
    or check-in IDs, and the tool fetches commit notes directly from your
    configured commit-tracking system, normalizes them, and runs the full
    pipeline. Branch is auto-detected from "Base Version:" in DevNotes.

Merge into existing patch (v1.2)
    For when you finish a patch and need to add one more PR. Pick the
    existing patch label, fetch the new check-ins, resolve any conflicts
    per-id (keep existing or replace with new), and the tool rebuilds the
    patch block sorted descending.

Preview-before-write
    Every run opens a modal preview window with three tabs (Check-in IDs /
    DevNotes preview / ReleaseNotes preview) so you can verify exactly
    what will change before any file is touched.

Missing-ID detection
    If a check-in ID appears in your input but not in the fetched data,
    the preview flags it with a yellow warning before commit.

Automatic timestamped backups
    Every commit writes DevNotes.YYYYMMDD_HHMMSS.bak.txt before modifying
    the original, so multiple runs in the same day never overwrite each
    other.

Flexible patch labels
    Patch, LabPatch, HomeMade, or any custom prefix, with integer (10) or
    decimal (5.1) numbers.

Format normalization
    Handles two real-world note formats developers use (section header on
    its own line vs. inline with content) without breaking either.

Standalone helper pages
    Run just one stage of the pipeline if that's all you need.


--------------------------------------------------------------------------------
DESIGN DECISIONS
--------------------------------------------------------------------------------

Two-stage pipeline (build_preview + commit_preview)
    Previewing is a pure read-only operation that touches no files.
    Committing is the only place that mutates disk. This separation makes
    the preview trustworthy and made it easy to add the modal preview
    window without duplicating logic.

Pluggable note sources
    Each data source implements a small NoteSource interface. The
    priority merger walks them in order with fallback semantics. Adding
    a new tracker means writing a ~100-line class and dropping it into
    sources/ - no changes to the pipeline or UI.

Self-contained merge pipeline
    Re-building an existing patch is its own pipeline (merge_pipeline.py)
    instead of being grafted onto the primary one. Same preview-then-
    commit shape but its own preview type. Keeps both paths easy to
    reason about.

Timestamped backups instead of a single .bak
    Multiple runs per day never clobber each other. Naming pattern is
    sortable.

Generalized patch regex
    ^[A-Za-z]+\d+(?:\.\d+)?$ covers Patch10, LabPatch3, HomeMade5.1, and
    arbitrary user-defined prefixes - matching how teams actually label
    patches in practice.

In-memory text transforms with thin file-IO wrappers
    All the parsing and reformatting is pure-function on strings; only a
    small set of functions read or write files. Makes the core logic easy
    to test.

Lazy imports for circular-import safety
    The Auto-Generate page and the main UI module import each other.
    Module-level imports would deadlock; deferring imports into method
    bodies fixes it without splitting the modules artificially.

customtkinter for the GUI
    Native-looking widgets, modern theming, no platform-specific drawing.
    Single-file build with PyInstaller.


--------------------------------------------------------------------------------
SCREENSHOTS
--------------------------------------------------------------------------------

(Add screenshots here. The Auto-Generate page, the Preview dialog, and
the conflict-resolution dialog are the three views worth showing.)


--------------------------------------------------------------------------------
REQUIREMENTS
--------------------------------------------------------------------------------

- Python 3.10 or newer
- customtkinter
- requests (only needed for Auto-Generate; Manual-Generate works without)

    pip install customtkinter requests


--------------------------------------------------------------------------------
USAGE
--------------------------------------------------------------------------------

    python ReleaseNotesTool_UI_ctk.py


Manual-Generate (the v1.0 flow):

    1. Select your existing DevNotes.txt.
    2. Pick the patch type and enter the patch number.
    3. Select checkinid.txt (the list of check-in IDs to include).
    4. Select Notes.txt (the raw developer notes you've collected).
    5. Click "Run Full Pipeline".
    6. Review the preview. If anything looks off, click "Cancel".
    7. Click "Confirm & Write Files".


Auto-Generate:

    1. Select your existing DevNotes.txt - branch is auto-detected and
       the existing-patch dropdown auto-populates.
    2. Choose "New patch" mode, pick the patch type, and enter the number.
    3. Type PR numbers and/or check-in IDs (one per line or comma-
       separated), or browse to a checkinid.txt file.
    4. Click "Fetch & Preview".
    5. Review the preview, then "Confirm & Write Files".


Auto-Generate - merge into existing patch:

    1. Select your existing DevNotes.txt.
    2. Choose "Merge into existing patch" mode and pick the patch from
       the dropdown.
    3. Type the new PR numbers / check-in IDs you want to add.
    4. Click "Fetch & Preview".
    5. If any check-in IDs collide, a conflict dialog opens - pick per-id
       whether to keep existing or replace with the newly fetched version.
    6. Review the merged preview and "Confirm & Write Files".


Patch label examples:

    Type       Number    Result
    -------    ------    -----------
    Patch      10        Patch10
    Patch      5.1       Patch5.1
    LabPatch   3         LabPatch3
    HomeMade   5         HomeMade5
    (custom)   2         HotFix2


--------------------------------------------------------------------------------
FILE STRUCTURE
--------------------------------------------------------------------------------

    NoteGenerator/
      ReleaseNotesTool_UI_ctk.py   - GUI entry point
      full_pipeline.py             - build_preview / commit_preview
      merge_pipeline.py            - build_merge_preview / commit_merge_preview
      auto_generate_page.py        - Auto-Generate page + conflict dialog
      branch_detector.py           - Parse "Base Version:" -> branch token
      devnotes_parser.py           - Read/edit existing patch blocks
      notes_to_for_devnotes.py     - Filter raw notes by check-in IDs
      ReleaseNotesCreatorv4.py     - Convert DevNotes.txt to ReleaseNotes.txt
      sources/
        base.py                    - NoteSource interface + FetchResult
        file_source.py             - Reads notes from a local file
      merger/
        priority_merger.py         - Walks sources with fallback semantics
      docs/                        - Plain-text versions of the README
      README.md


Pipeline architecture:

    New-patch flow:
      build_preview(devnotes, patch, checkinids, notes)
          -> PipelinePreview   (pure / read-only)
      commit_preview(preview, make_backup=True)
          -> writes files + creates backup

    Merge flow:
      build_merge_preview(devnotes, patch_label, new_notes, resolutions)
          -> MergePreview   (pure / read-only; exposes detected conflicts)
      commit_merge_preview(preview, make_backup=True)
          -> writes files + creates backup


Adding a new note source:

    1. Subclass NoteSource in sources/your_source.py
    2. Implement fetch(queries) returning a FetchResult with Notes.txt-
       style text
    3. Construct your source in auto_generate_page.py's _build_sources
       and add it to the priority chain

    The pipeline doesn't care where the notes come from as long as they
    match the expected text format.


--------------------------------------------------------------------------------
INPUT FILE FORMATS
--------------------------------------------------------------------------------

checkinid.txt
    Any text containing check-in version numbers (N.NNNN) or PR numbers
    (PR-NNNNNN), one per line or comma-separated. Names and other text
    are ignored - only numeric and PR patterns are matched.

        alice 0.4091
        bob 0.3968
        PR-214308
        0.4260


Notes.txt
    Raw developer notes (only needed for Manual-Generate). Each check-in
    block starts with "Checkin ID:" and is separated by 80-dash separator
    lines. The tool automatically strips internal-only headers
    (Developer:, Timestamp:, Release Notes Needed:, [Auto Merge Wizard]
    blocks, etc.) before inserting into DevNotes.


DevNotes.txt
    Must begin with a "Base Version: ..." line. New patches are inserted
    immediately below this line. Existing patches are listed below in
    newest-first order.


--------------------------------------------------------------------------------
BUILDING A STANDALONE EXECUTABLE
--------------------------------------------------------------------------------

macOS / Linux:

    pip install pyinstaller

    python3 -m PyInstaller --clean --onefile --windowed \
        --collect-all customtkinter --collect-all darkdetect \
        --collect-all requests \
        --hidden-import auto_generate_page \
        --hidden-import branch_detector \
        --hidden-import devnotes_parser \
        --hidden-import merge_pipeline \
        --hidden-import sources \
        --hidden-import sources.base \
        --hidden-import sources.file_source \
        --hidden-import merger \
        --hidden-import merger.priority_merger \
        --name ReleaseNotesTool ReleaseNotesTool_UI_ctk.py

Windows:

    Same flags, with "python" instead of "python3".


Output:
    macOS / Linux: dist/ReleaseNotesTool
    Windows:       dist/ReleaseNotesTool.exe

The --collect-all flags bundle library assets. The --hidden-import flags
are needed because the app uses lazy imports that PyInstaller's static
analysis can't always see.

NOTE: PyInstaller builds are platform-specific. Build on the OS you
intend to distribute to.


--------------------------------------------------------------------------------
RESTORING FROM A BACKUP
--------------------------------------------------------------------------------

Backups are saved next to DevNotes.txt with a timestamped filename:

    DevNotes.txt
    DevNotes.20260516_205412.bak.txt   <- backup from May 16, 8:54 PM
    DevNotes.20260603_091203.bak.txt   <- backup from Jun 3, 9:12 AM

To restore, rename the desired backup to DevNotes.txt (overwriting the
current one). An in-app "Restore from Backup" flow is on the roadmap.


--------------------------------------------------------------------------------
ROADMAP
--------------------------------------------------------------------------------

- In-app backup restoration UI
- Remember last-used file paths between sessions
- Auto-suggest next patch number from existing DevNotes
- Optional output preview pane inside the main window
- Side-by-side diff view in the conflict resolution dialog


--------------------------------------------------------------------------------
CHANGELOG
--------------------------------------------------------------------------------

1.2.0
    - New Auto-Generate workflow - fetch notes from a configured commit-
      tracking system.
    - New Merge into existing patch mode with per-conflict resolution.
    - New sources/ and merger/ packages - pluggable note sources with
      priority fallback.
    - Branch auto-detection from "Base Version:".
    - Sidebar reorganized: Auto-Generate primary, Manual-Generate backup.
    - Removed legacy ReleaseNotesTool_UI.py prototype.

1.1.0
    - Modal preview dialog with three tabs.
    - Missing-ID detection in preview.
    - Timestamped backups.
    - Flexible patch label dropdown.
    - Inline section header normalization.

1.0.0
    - Initial release.
