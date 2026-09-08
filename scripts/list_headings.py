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

for i, p in enumerate(doc.paragraphs):
    txt = p.text.strip().encode("ascii", "replace").decode("ascii")
    if any(h in txt for h in ["III.", "IV.", "V.", "VI.", "VII.", "VIII.", "IX.", "Algorithm 1", "TABLE", "raw_score", "Fig."]):
        print(f"P[{i}]: {txt[:80]}")
