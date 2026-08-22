import os

filepath = r"d:\TerraLegalAI\frontend\components\PdfFormPreview.tsx"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# Add logging to Page
old_page = """              <Page 
                pageNumber={pageNumber} 
                width={pageWidth}
                renderTextLayer={false}
                renderAnnotationLayer={false}
                className="pdf-page-container"
              />"""

new_page = """              <Page 
                pageNumber={pageNumber} 
                width={pageWidth}
                renderTextLayer={false}
                renderAnnotationLayer={false}
                className="pdf-page-container"
                onRenderError={(error) => console.error('Page render error:', error)}
                onLoadError={(error) => console.error('Page load error:', error)}
              />"""

content = content.replace(old_page, new_page)

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)
