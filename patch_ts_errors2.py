import os

filepath = r"d:\TerraLegalAI\frontend\app\page.tsx"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

bad_str = """      const res = await formsApi.analyzeDocx(docxFile);
      setHtmlTemplate(res.html); // useEffect s? set innerHTML + reset ref
      setStep(2);"""

new_str = """      const res = await formsApi.analyzeDocx(docxFile);
      setPreviewData(res);
      setStep(2);"""

content = content.replace(bad_str, new_str)

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)
