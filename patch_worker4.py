import os

filepath = r"d:\TerraLegalAI\frontend\components\PdfFormPreview.tsx"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# Replace workerSrc
old_worker = "pdfjs.GlobalWorkerOptions.workerSrc = '/pdf.worker.min.mjs';"
new_worker = "pdfjs.GlobalWorkerOptions.workerSrc = '/pdf.worker.min.js';"

content = content.replace(old_worker, new_worker)

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)
