import streamlit as st
import re
import zipfile
import io
from pathlib import Path

st.set_page_config(page_title="Image Renamer", layout="wide")
st.title("📸 Image Renamer — (Upload → Auto Rename → Download Zip)")


# -------------------------------
# Detect ID from filename
# -------------------------------
def detect_id(filename: str):
    stem = Path(filename).stem

    # CASE 1 — Starts with digits
    m1 = re.match(r"^(\d+)", stem)
    if m1:
        return int(m1.group(1))

    # CASE 2 — Digits right before "Ultra"
    m2 = re.search(r"(\d+)(?=Ultra)", stem, flags=re.IGNORECASE)
    if m2:
        return int(m2.group(1))

    return None  # No ID found


# -------------------------------
# App UI
# -------------------------------
uploaded_files = st.file_uploader(
    "Upload images",
    type=["png", "jpg", "jpeg"],
    accept_multiple_files=True
)

if not uploaded_files:
    st.info("Upload your images to begin.")
    st.stop()


# -------------------------------
# Process uploaded files
# -------------------------------
results = []
used_numbers = set()

# First pass — detect IDs
for file in uploaded_files:
    file_id = detect_id(file.name)

    results.append({
        "file": file,
        "original": file.name,
        "id": file_id,
        "final_id": None,   # will fill in next
        "new_name": None,
    })

    if file_id is not None:
        used_numbers.add(file_id)

# Assign IDs for files that did not have any — lowest unused numbers
next_num = 1
while next_num in used_numbers:
    next_num += 1

for r in results:
    if r["id"] is not None:
        r["final_id"] = r["id"]
    else:
        r["final_id"] = next_num
        used_numbers.add(next_num)
        next_num += 1
        while next_num in used_numbers:
            next_num += 1

    # Format to 3 digits
    r["new_name"] = f"{r['final_id']:03d}" + Path(r["file"].name).suffix.lower()


# -------------------------------
# Show preview table
# -------------------------------
st.subheader("🔍 Rename Preview")
st.table([
    {
        "Original": r["original"],
        "Detected ID": r["id"],
        "Final ID": r["final_id"],
        "New filename": r["new_name"]
    }
    for r in results
])


# -------------------------------
# Create ZIP for download
# -------------------------------
zip_buffer = io.BytesIO()
with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
    for r in results:
        zipf.writestr(
            r["new_name"],
            r["file"].read()
        )

st.success("Images processed successfully!")

st.download_button(
    label="⬇ Download Renamed Images (ZIP)",
    data=zip_buffer.getvalue(),
    file_name="renamed_images.zip",
    mime="application/zip"
)
