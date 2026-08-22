import re

file_path = "d:/TerraLegalAI/backend/app/api/v1/forms.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Instead of matching the Vietnamese text which might be mangled, let's match the exact English python code lines before and after.
target_pattern = r"(\s+else:\s+raise HTTPException\(status_code=404, detail=\"[^\"]+\"\)\s+)(# X\?- lA cAc vA1ng v tay|\# X.*manual zones)"
match = re.search(target_pattern, content)

if match:
    replacement = match.group(1) + "\n        if body.user_labels:\n            user_ctx = \"\\n\\n--- THÔNG TIN NGƯỜI DÙNG ĐÃ CHỈNH SỬA ---\\n\"\n            for idx, label in body.user_labels.items():\n                if label.strip():\n                    user_ctx += f\"[[{idx}]]: {label}\\n\"\n            full_text += user_ctx\n\n        " + match.group(2)
    new_content = content[:match.start()] + replacement + content[match.end():]
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(new_content)
    print("Patched successfully!")
else:
    print("Failed to patch.")
