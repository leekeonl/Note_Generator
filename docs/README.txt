================================================================================
                            RELEASE NOTES TOOL
================================================================================

A desktop GUI that automates the process of generating internal DevNotes.txt
and customer-facing ReleaseNotes.txt files from raw developer check-in notes.

Built with customtkinter, styled to match the Lam Research visual identity
(navy + green).


--------------------------------------------------------------------------------
FEATURES
--------------------------------------------------------------------------------

- All-in-One pipeline
    Feed in DevNotes.txt, a patch label, checkinid.txt, and Notes.txt, and the
    tool produces an updated DevNotes.txt plus a freshly generated
    ReleaseNotes.txt in one click.

- Preview before write
    Every run opens a modal preview window with three tabs (Check-in IDs /
    DevNotes preview / ReleaseNotes preview) so you can verify exactly what
    will change before any file is touched.

- Missing-ID detection
    If an ID in checkinid.txt does not appear in Notes.txt, the preview flags
    it with a yellow warning so you can fix the input before committing.

- Automatic timestamped backups
    Every commit writes DevNotes.YYYYMMDD_HHMMSS.bak.txt before modifying the
    original, so multiple runs in the same day never overwrite each other.

- Flexible patch labels
    Patch, LabPatch, HomeMade, or any custom prefix, with integer (10) or
    decimal (5.1) numbers.

- Standalone helper pages
    Run just one stage if you only need Notes -> For_DevNotes filtering or
    DevNotes -> ReleaseNotes regeneration.


--------------------------------------------------------------------------------
SCREENSHOT
--------------------------------------------------------------------------------

(Add a screenshot here once available - the All-in-One page and the Preview
dialog are the two views worth showing.)


--------------------------------------------------------------------------------
REQUIREMENTS
--------------------------------------------------------------------------------

- Python 3.10 or newer
- customtkinter

Install dependencies:

    pip install customtkinter


--------------------------------------------------------------------------------
USAGE
--------------------------------------------------------------------------------

Clone the repo and run:

    python ReleaseNotesTool_UI_ctk.py


All-in-One workflow:

    1. Select your existing DevNotes.txt.
    2. Pick the patch type from the dropdown (Patch, LabPatch, HomeMade, or
       type your own) and enter the patch number (e.g. 10 or 5.1).
    3. Select checkinid.txt (the list of check-in IDs to include).
    4. Select Notes.txt (the raw developer notes).
    5. Click "Run Full Pipeline".
    6. Review the Preview dialog. If anything looks off, click "Cancel".
    7. Click "Confirm & Write Files" to apply the changes.

The tool will:

    - Insert a new patch block (label + today's date + filtered check-ins)
      into DevNotes.txt directly below the "Base Version:" line.
    - Generate a fresh ReleaseNotes.txt in the same folder.
    - Save a timestamped backup of the original DevNotes.txt.


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

    ReleaseNotesTool/
      ReleaseNotesTool_UI_ctk.py   - Main GUI entry point
      full_pipeline.py             - build_preview / commit_preview / run_full_pipeline
      notes_to_for_devnotes.py     - Filter raw Notes.txt by check-in IDs
      ReleaseNotesCreatorv4.py     - Convert DevNotes.txt to ReleaseNotes.txt
      README.md


Pipeline architecture:

The backend is split so that previewing has no side effects.

    build_preview(devnotes, patch, checkinids, notes)
        -> PipelinePreview   (pure / read-only)

    commit_preview(preview, make_backup=True)
        -> writes files + creates backup

    run_full_pipeline(...)   # backward-compatible one-shot wrapper
        = commit_preview(build_preview(...))


--------------------------------------------------------------------------------
INPUT FILE FORMATS
--------------------------------------------------------------------------------

checkinid.txt
    Any text containing check-in version numbers in N.NNNN format. Names are
    optional; only the numeric part is used for matching.

        alice 0.4091
        bob 0.3968
        0.4260


Notes.txt
    Standard internal notes format. Each check-in block starts with
    "Checkin ID:" and is separated by 80-dash separator lines. The tool
    automatically strips out internal-only headers (Developer:, Timestamp:,
    Release Notes Needed:, [Auto Merge Wizard] blocks, etc.) before inserting
    into DevNotes.


DevNotes.txt
    Must begin with a "Base Version: ..." line. New patches are inserted
    immediately below this line.


--------------------------------------------------------------------------------
BUILDING A STANDALONE EXECUTABLE
--------------------------------------------------------------------------------

To package the app as a single .exe (Windows) or binary (macOS/Linux):

    pip install pyinstaller

    python -m PyInstaller \
        --clean \
        --onefile \
        --windowed \
        --collect-all customtkinter \
        --collect-all darkdetect \
        --name ReleaseNotesTool \
        ReleaseNotesTool_UI_ctk.py

The result is in dist/ReleaseNotesTool.exe. The --collect-all flags are
required so that customtkinter's theme and font assets are bundled inside
the executable.

NOTE: PyInstaller builds are platform-specific. To distribute to Windows
users, build on Windows; to distribute to macOS users, build on macOS.


--------------------------------------------------------------------------------
RESTORING FROM A BACKUP
--------------------------------------------------------------------------------

Backups are saved next to DevNotes.txt with a timestamped filename:

    DevNotes.txt
    DevNotes.20260516_205412.bak.txt   <- backup from May 16, 8:54 PM
    DevNotes.20260517_091203.bak.txt   <- backup from May 17, 9:12 AM

To restore, manually rename the desired backup to DevNotes.txt (overwriting
the current one). A "Restore from Backup" UI flow is planned for a future
release.


--------------------------------------------------------------------------------
LICENSE
--------------------------------------------------------------------------------

(Add your preferred license here, e.g. MIT, Apache 2.0, or "Internal use
only".)


--------------------------------------------------------------------------------
AUTHOR
--------------------------------------------------------------------------------

Written by Matthew Lee.
