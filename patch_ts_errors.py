import os

filepath = r"d:\TerraLegalAI\frontend\app\page.tsx"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# Fix docRef in useEffect
bad_useEffect = """    if (mode !== 'merge') {
      // Clear merge selection if switching out of merge mode
      mergeSelectionRef.current.forEach(idx => {
        const el = docRef.current?.querySelector(`[data-blank-idx="${idx}"]`);
        if (el) el.classList.remove("blank-zone--merging");
      });
      mergeSelectionRef.current.clear();
      setMergeCount(0);
    }"""
fixed_useEffect = """    if (mode !== 'merge') {
      mergeSelectionRef.current.clear();
      setMergeCount(0);
    }"""
content = content.replace(bad_useEffect, fixed_useEffect)

# Fix setHtmlTemplate occurrences
bad_analyze = """      const res = await formsApi.analyzeDocx(docxFile);
      setHtmlTemplate(res.html); // useEffect s? set innerHTML + reset ref
      setStep(2);"""
fixed_analyze = """      const res = await formsApi.analyzeDocx(docxFile);
      setPreviewData(res);
      setStep(2);"""
content = content.replace(bad_analyze, fixed_analyze)

# Fix resetModal
bad_reset = 'setHtmlTemplate("");'
fixed_reset = 'setPreviewData(null);'
content = content.replace(bad_reset, fixed_reset)

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)
