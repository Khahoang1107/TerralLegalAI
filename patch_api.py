
import re

with open("d:/TerraLegalAI/frontend/lib/api.ts", "r", encoding="utf-8") as f:
    content = f.read()

new_method = """
    async uploadForm(jsonFile: File, docxFile: File): Promise<any> {
      const form = new FormData();
      form.append("json_file", jsonFile);
      form.append("docx_file", docxFile);
      const { data } = await client.post("/forms/upload", form, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      return data;
    },
"""

content = content.replace("async analyzeDocx(file: File): Promise<any> {", new_method + "    async analyzeDocx(file: File): Promise<any> {")

with open("d:/TerraLegalAI/frontend/lib/api.ts", "w", encoding="utf-8") as f:
    f.write(content)

print("Patched api.ts")

