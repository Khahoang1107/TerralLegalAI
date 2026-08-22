import os

filepath = r"d:\TerraLegalAI\frontend\app\page.tsx"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

old_import = "import PdfFormPreview from '@/components/PdfFormPreview';"
new_import = """import dynamic from 'next/dynamic';
const PdfFormPreview = dynamic(() => import('@/components/PdfFormPreview'), { ssr: false });"""

content = content.replace(old_import, new_import)

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)
