import os
import re

filepath = r"d:\TerraLegalAI\frontend\app\page.tsx"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update state declarations
old_state = """  const [step, setStep] = useState(1);
  const [docxFile, setDocxFile] = useState<File | null>(null);
  const [htmlTemplate, setHtmlTemplate] = useState("");"""

new_state = """  const [step, setStep] = useState(1);
  const [docxFile, setDocxFile] = useState<File | null>(null);
  const [previewData, setPreviewData] = useState<{preview_url: string, temp_id: string, zones: any[]} | null>(null);"""
content = content.replace(old_state, new_state)

# 2. Add imports at the top
if "import { Document, Page, pdfjs }" not in content:
    import_statement = """import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/esm/Page/AnnotationLayer.css';
import 'react-pdf/dist/esm/Page/TextLayer.css';
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;
"""
    content = content.replace('import {', import_statement + '\nimport {', 1)

# 3. Update formsApi.analyzeDocx call
old_analyze_call = """      const res = await formsApi.analyzeDocx(docxFile);
      setHtmlTemplate(res.html);
      setStep(2);"""

new_analyze_call = """      const res = await formsApi.analyzeDocx(docxFile);
      setPreviewData(res);
      setStep(2);"""
content = content.replace(old_analyze_call, new_analyze_call)

# 4. Update the docRef replacement in useEffect
# We actually don't need docRef vanilla DOM manipulation anymore.
# We will use a React component for the PDF.
# But for now, let's just write this to see if it replaces correctly.
with open(r"d:\TerraLegalAI\patch_page_test.py", "w", encoding="utf-8") as f:
    f.write("print('OK')")
