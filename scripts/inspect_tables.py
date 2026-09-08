import zipfile
import io
from pathlib import Path
from docx import Document

fixed_buf = io.BytesIO()
with zipfile.ZipFile(r"C:\Users\Atharv\Desktop\SecureMask_Research_Paper_Draft (5).docx", "r") as zin:
    with zipfile.ZipFile(fixed_buf, "w", compression=zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            content = zin.read(item.filename)
            if item.filename == "[Content_Types].xml":
                content = content.decode("utf-8").replace(
                    '<Default ContentType="image/png" Extension="png"/>',
                    '<Default ContentType="image/png" Extension="png"/><Default ContentType="image/png" Extension="undefined"/>'
                ).encode("utf-8")
            zout.writestr(item, content)

fixed_buf.seek(0)
doc = Document(fixed_buf)

for idx, table in enumerate(doc.tables):
    print(f"\n--- TABLE {idx+1} ({len(table.rows)} rows, {len(table.columns)} cols) ---")
    for r_idx in range(min(5, len(table.rows))):
        row_txt = [c.text.strip().replace('\n', ' ') for c in table.rows[r_idx].cells]
        print(f"  Row {r_idx}: {row_txt[:4]}")
