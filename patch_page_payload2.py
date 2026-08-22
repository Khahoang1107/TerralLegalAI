import sys

with open("d:/TerraLegalAI/frontend/app/page.tsx", "r", encoding="utf-8") as f:
    content = f.read()

save_idx = content.find("const handleSaveVisual = async (e: React.FormEvent) => {")
if save_idx != -1:
    payload_start = content.find("const fields = labeledList.map(f => {", save_idx)
    payload_end = content.find("    const payload = {", payload_start)
    if payload_start != -1 and payload_end != -1:
        new_payload = """const fields = labeledList.map(f => {
      const zone = previewData?.zones?.find((z: any) => String(z.idx) === f.blankIdx);
      const isCheckbox = zone?.field_type === 'checkbox';
      const suggested = zone?.suggested_label || zone?.ai_label || "";
      const finalName = fieldData[f.id] !== undefined ? fieldData[f.id] : (suggested || f.id);
      
      const customDesc = fieldDesc[f.id];
      const resolvedType = fieldType[f.id] || (isCheckbox ? 'checkbox' : 'text');
      const defaultDesc = resolvedType === 'checkbox' ? `Có hay không: ${finalName}?` : `Nhập thông tin cho ${finalName}`;
      
      const base: any = {
        key: f.id,
        name: finalName,
        description: customDesc || defaultDesc,
        required: fieldRequired[f.id] !== false,
        type: resolvedType === 'checkbox' ? 'boolean' : resolvedType === 'digit_group' ? 'digit_group' : 'string'
      };
      
      if (fieldDependsOn[f.id]) {
        base.depends_on = { field: fieldDependsOn[f.id], value: true };
      }
      if (fieldRequireOneOfGroup[f.id]?.trim()) {
        base.require_one_of_group = fieldRequireOneOfGroup[f.id].trim();
      }
      
      if (resolvedType === 'digit_group') {
        const gk = (fieldGroupKey[f.id] || finalName || f.id).trim();
        base.group_key = gk;
        base.digit_index = parseInt(String(zone?.idx)) || 0;
      }
      return base;
    });
"""
        content = content[:payload_start] + new_payload + content[payload_end:]
        print("Replaced payload!")
        
with open("d:/TerraLegalAI/frontend/app/page.tsx", "w", encoding="utf-8") as f:
    f.write(content)
