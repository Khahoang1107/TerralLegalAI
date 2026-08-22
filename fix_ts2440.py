import sys

with open("d:/TerraLegalAI/frontend/app/page.tsx", "r", encoding="utf-8") as f:
    content = f.read()

# Replace duplicate imports of PdfFormPreview
# Next.js may complain if there are two imports or an import and a local declaration
if "import PdfFormPreview from '@/components/PdfFormPreview';" in content:
    # Just remove the first one if there are multiple, or keep one
    parts = content.split("import PdfFormPreview from '@/components/PdfFormPreview';")
    if len(parts) > 2:
        # It's imported multiple times!
        content = "import PdfFormPreview from '@/components/PdfFormPreview';".join([parts[0], parts[1]]) + "".join(parts[2:])

    # What if it's imported from different paths?
    content = content.replace("import dynamic from 'next/dynamic';\nconst PdfFormPreview = dynamic(() => import('@/components/PdfFormPreview'), { ssr: false });", "")

with open("d:/TerraLegalAI/frontend/app/page.tsx", "w", encoding="utf-8") as f:
    f.write(content)
