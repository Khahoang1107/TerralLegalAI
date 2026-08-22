import os

filepath = r"d:\TerraLegalAI\frontend\components\PdfFormPreview.tsx"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# Add getToken logic inside component
old_return = """  return (
    <div 
      ref={containerRef}"""

new_return = """  const token = typeof window !== 'undefined' 
    ? (localStorage.getItem("terralegal_access_token") ?? sessionStorage.getItem("terralegal_access_token"))
    : null;

  return (
    <div 
      ref={containerRef}"""
content = content.replace(old_return, new_return)

# Update file prop in Document
old_document = """      <Document
        file={`http://localhost:8000${previewUrl}`}
        onLoadSuccess={onDocumentLoadSuccess}"""

new_document = """      <Document
        file={{
          url: `http://localhost:8000${previewUrl}`,
          httpHeaders: token ? { Authorization: `Bearer ${token}` } : {}
        }}
        onLoadSuccess={onDocumentLoadSuccess}"""
content = content.replace(old_document, new_document)

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)
