import os

filepath = r"d:\TerraLegalAI\frontend\components\PdfFormPreview.tsx"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# Fix pageWidth logic
old_effect = """  useEffect(() => {
    const updateWidth = () => {
      if (containerRef.current) {
        setPageWidth(containerRef.current.clientWidth - 40);
      }
    };"""

new_effect = """  useEffect(() => {
    const updateWidth = () => {
      if (containerRef.current) {
        const cw = containerRef.current.clientWidth;
        if (cw > 100) {
          setPageWidth(cw - 40);
        }
      }
    };"""
content = content.replace(old_effect, new_effect)

# Add onLoadError for Document
if "onLoadError={console.error}" not in content:
    content = content.replace('onLoadSuccess={onDocumentLoadSuccess}', 'onLoadSuccess={onDocumentLoadSuccess}\n        onLoadError={console.error}')

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)
