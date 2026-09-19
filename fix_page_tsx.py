import sys

with open("d:/TerraLegalAI/frontend/app/page.tsx", "r", encoding="utf-8") as f:
    content = f.read()

# Remove from DocumentsView
bad_hooks = """  const [fieldType, setFieldType] = useState<Record<string, string>>({});
  const [fieldGroupKey, setFieldGroupKey] = useState<Record<string, string>>({});
  const [fieldDependsOn, setFieldDependsOn] = useState<Record<string, string>>({});
  const [fieldRequireOneOfGroup, setFieldRequireOneOfGroup] = useState<Record<string, string>>({});
"""
if bad_hooks in content:
    content = content.replace(bad_hooks, "")
else:
    print("bad hooks not found exactly")

# Insert into FormsView
forms_view_idx = content.find("function FormsView()")
if forms_view_idx != -1:
    # find the useToast inside FormsView
    toast_idx = content.find("const { toast, show: showToast, hide: hideToast } = useToast();", forms_view_idx)
    if toast_idx != -1:
        content = content[:toast_idx] + bad_hooks + "  " + content[toast_idx:]
        print("Injected into FormsView successfully")

with open("d:/TerraLegalAI/frontend/app/page.tsx", "w", encoding="utf-8") as f:
    f.write(content)
