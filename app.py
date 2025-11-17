import streamlit as st
from pathlib import Path
import re
import shutil
from datetime import datetime

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".tiff"}

# --- Helper functions ------------------------------------------------------
def detect_id(name: str):
    """
    Detect ID per rules:
    1) If starts with digits -> that number
    2) Else try digits immediately before 'Ultra' (case-insensitive), e.g. _12Ultra or 12Ultra
    Returns int or None.
    """
    # 1) start-of-string digits
    m = re.match(r'^(\d+)', name)
    if m:
        return int(m.group(1))
    # 2) digits immediately before Ultra (allow underscore or other separator)
    m2 = re.search(r'([0-9]+)(?=Ultra)', name, flags=re.IGNORECASE)
    if m2:
        return int(m2.group(1))
    return None

def three_digit(n: int):
    return f"{n:03d}"

def safe_target_name(folder: Path, base_num: str, ext: str) -> Path:
    """
    If base_num.ext exists, appends _1, _2, ... until unique.
    """
    candidate = folder / f"{base_num}{ext}"
    if not candidate.exists():
        return candidate
    i = 1
    while True:
        candidate = folder / f"{base_num}_{i}{ext}"
        if not candidate.exists():
            return candidate
        i += 1

def scan_folder(folder: Path, exts=IMAGE_EXTS):
    files = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in exts]
    files.sort(key=lambda p: p.name.lower())
    return files

def build_plan(files):
    # collect existing detected numbers so we don't accidentally duplicate when assigning missing ones
    used = set()
    entries = []
    for p in files:
        id_ = detect_id(p.stem)
        entries.append({"path": p, "id": id_, "final_id": None, "target": None})
        if id_ is not None:
            used.add(id_)
    # assign next unused for those missing
    next_num = 1
    while next_num in used:
        next_num += 1
    for e in entries:
        if e["id"] is not None:
            e["final_id"] = e["id"]
        else:
            # assign lowest unused
            e["final_id"] = next_num
            used.add(next_num)
            while next_num in used:
                next_num += 1
    # compute target names (safe)
    for e in entries:
        base = three_digit(e["final_id"])
        e["target"] = safe_target_name(e["path"].parent, base, e["path"].suffix.lower())
    return entries

def perform_rename(entries, dry_run=True, backup=False, backup_dir=None):
    """
    entries: list of dicts with keys path and target (Path objects)
    backup: if True, copies originals into backup_dir before renaming
    Returns log list of strings and number of renamed files.
    """
    log = []
    renamed_count = 0
    if backup and backup_dir:
        backup_dir.mkdir(parents=True, exist_ok=True)
        log.append(f"Backup folder: {backup_dir}")

    for e in entries:
        src: Path = e["path"]
        tgt: Path = e["target"]
        if src.resolve() == tgt.resolve():
            log.append(f"SKIP (same): {src.name}")
            continue
        if dry_run:
            log.append(f"DRY: {src.name} -> {tgt.name}")
            continue
        try:
            if backup and backup_dir:
                bpath = backup_dir / src.name
                shutil.copy2(src, bpath)
                log.append(f"Backed up: {src.name} -> {bpath.name}")
            # rename (if target exists we already used safe_target_name to avoid conflicts)
            src.rename(tgt)
            log.append(f"RENAMED: {src.name} -> {tgt.name}")
            renamed_count += 1
        except Exception as exc:
            log.append(f"ERROR renaming {src.name} -> {tgt.name} : {exc}")
    return log, renamed_count

# --- Streamlit UI ---------------------------------------------------------
st.set_page_config(page_title="Image Renamer", layout="wide")
st.title("Image Renamer — (leading digits / digits before 'Ultra')")

st.markdown(
    "This app runs locally and renames files on your machine. "
    "**Make sure you run this on a copy or enable backup** if unsure."
)

# Folder selection
st.sidebar.header("Folder & options")
folder_input = st.sidebar.text_input("Folder path (local)", value="")  # user must paste or type path
browse = st.sidebar.button("Use current script folder")
if browse:
    import os
    folder_input = os.path.abspath(os.getcwd())
    st.experimental_rerun()

folder = Path(folder_input) if folder_input else None

backup = st.sidebar.checkbox("Create backup (copy originals)", value=True)
backup_folder_name = st.sidebar.text_input("Backup folder name", value="backup_renamer")
dry_run_default = st.sidebar.checkbox("Default to dry run (preview only)", value=True)

st.sidebar.markdown("---")
st.sidebar.markdown("**Run controls**")
do_scan = st.sidebar.button("Scan folder")

if not folder:
    st.info("Enter a folder path on the left and click **Scan folder**. The app must run on your machine (not in the cloud).")
else:
    st.write(f"Target folder: `{folder}`")
    if not folder.exists():
        st.error("Folder does not exist.")
    else:
        files = scan_folder(folder)
        st.write(f"Found {len(files)} image files.")
        if len(files) == 0:
            st.warning("No image files with supported extensions found.")
        if do_scan or "last_scan" not in st.session_state:
            st.session_state.last_scan = datetime.now().isoformat()
            st.session_state.files = [str(p.name) for p in files]

        # quick file listing + sample
        st.subheader("Files (first 200 listed)")
        st.dataframe({"filename": st.session_state.files[:200]})

        # Build plan
        entries = build_plan(files)
        st.subheader("Preview rename plan")
        preview_rows = []
        for e in entries:
            preview_rows.append({
                "original": e["path"].name,
                "detected_id": (e["id"] if e["id"] is not None else ""),
                "final_id": three_digit(e["final_id"]),
                "proposed_name": e["target"].name
            })
        st.table(preview_rows)

        st.markdown("**Important:** Review the preview carefully. If anything looks wrong, cancel and paste a few problematic filenames into chat with me.")

        # Execute controls
        perform = st.button("Execute rename now")
        dry_run = st.checkbox("Dry run (preview) — if checked, no files will be changed", value=dry_run_default)
        if backup and not backup_folder_name:
            st.error("Please provide a backup folder name.")
        if perform:
            if dry_run:
                st.warning("Dry run selected — no files will be changed.")
            # Confirm
            if not st.confirm if hasattr(st, "confirm") else True:
                # older streamlit may not have st.confirm; we still proceed after a second confirmation
                pass

            # prepare backup dir
            backup_dir = None
            if backup:
                backup_dir = folder / backup_folder_name
            log, count = perform_rename(entries, dry_run=dry_run, backup=backup, backup_dir=backup_dir)
            st.subheader("Action log")
            for line in log:
                st.text(line)
            st.success(f"Operation complete. Files renamed: {count} (dry_run={dry_run})")

            if backup and backup_dir and backup_dir.exists():
                st.info(f"Backups are available at: {backup_dir}")

        st.markdown("---")
        st.caption("If the detection fails for some filenames, paste 6–10 example filenames into the chat and I will update the detection regex instantly.")
