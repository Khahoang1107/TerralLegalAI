import sys

with open("d:/TerraLegalAI/frontend/app/page.tsx", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add state hooks to FormsView
forms_view_idx = content.find("function FormsView()")
if forms_view_idx != -1:
    toast_idx = content.find("const { toast, show: showToast, hide: hideToast } = useToast();", forms_view_idx)
    if toast_idx != -1:
        new_hooks = """  const [fieldType, setFieldType] = useState<Record<string, string>>({});
  const [fieldGroupKey, setFieldGroupKey] = useState<Record<string, string>>({});
  const [fieldDependsOn, setFieldDependsOn] = useState<Record<string, string>>({});
  const [fieldRequireOneOfGroup, setFieldRequireOneOfGroup] = useState<Record<string, string>>({});
"""
        # Ensure we don't insert multiple times
        if "const [fieldType" not in content[forms_view_idx:forms_view_idx+1000]:
            content = content[:toast_idx] + new_hooks + "  " + content[toast_idx:]

# 2. Reset modal
reset_old = """    fieldOrderRef.current = initialFieldOrder;
    setFieldData({});"""
reset_new = """    fieldOrderRef.current = initialFieldOrder;
    setFieldData({});
    setFieldType({});
    setFieldGroupKey({});
    setFieldDependsOn({});
    setFieldRequireOneOfGroup({});"""
content = content.replace(reset_old, reset_new)

# 3. Payload generation in handleSaveVisual
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

# 4. Advanced Fields UI
ui_old = """                                  {/* Advanced Field Options */}
                                  <div style={{ display: "flex", gap: "10px", marginTop: "10px", alignItems: "center", flexWrap: "wrap" }}>
                                    <label style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "0.75rem", cursor: "pointer", flexShrink: 0 }}>
                                      <input
                                        type="checkbox"
                                        checked={fieldRequired[field.id] !== false}
                                        onChange={(e) => setFieldRequired({ ...fieldRequired, [field.id]: e.target.checked })}
                                      />
                                      Bắt buộc điền
                                    </label>
                                    <input
                                      type="text"
                                      placeholder="Mô tả / Điều kiện (vd: Chỉ điền khi không có MST)"
                                      value={fieldDesc[field.id] || ""}
                                      onChange={(e) => setFieldDesc({ ...fieldDesc, [field.id]: e.target.value })}
                                      style={{ flex: 1, minWidth: 100, padding: "4px 8px", fontSize: "0.75rem", border: "1px solid #d1d5db", borderRadius: "4px" }}
                                    />
                                  </div>"""

# Wait, if ui_old is different in git version, let's find it more robustly:
adv_idx = content.find("{/* Advanced Field Options */}")
if adv_idx != -1:
    end_adv_idx = content.find("                                  {/* BUG 1 FIX: Show zone number", adv_idx)
    if end_adv_idx != -1:
        ui_new = """                                  {/* Advanced Field Options */}
                                  <div style={{ display: "flex", flexDirection: "column", gap: "10px", marginTop: "10px" }}>
                                    <div style={{ display: "flex", gap: "10px", alignItems: "center", flexWrap: "wrap" }}>
                                      <label style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "0.75rem", cursor: "pointer", flexShrink: 0 }}>
                                        <input
                                          type="checkbox"
                                          checked={fieldRequired[field.id] !== false}
                                          onChange={(e) => setFieldRequired({ ...fieldRequired, [field.id]: e.target.checked })}
                                        />
                                        Bắt buộc điền
                                      </label>
                                      
                                      <select
                                        value={fieldType[field.id] || (previewData?.zones?.find((z: any) => String(z.idx) === field.blankIdx)?.field_type === 'checkbox' ? 'checkbox' : 'text')}
                                        onChange={(e) => setFieldType({ ...fieldType, [field.id]: e.target.value })}
                                        style={{ padding: "3px 6px", fontSize: "0.75rem", border: "1px solid #d1d5db", borderRadius: "4px", cursor: "pointer", flexShrink: 0 }}
                                      >
                                        <option value="text">📝 Text</option>
                                        <option value="checkbox">☑ Checkbox</option>
                                        <option value="digit_group">🔢 Digit Group</option>
                                      </select>
                                      
                                      {(fieldType[field.id] === 'digit_group') && (
                                          <input
                                            type="text"
                                            placeholder="Group Key (vd: ma_so_thue)"
                                            value={fieldGroupKey[field.id] || ""}
                                            onChange={(e) => setFieldGroupKey({ ...fieldGroupKey, [field.id]: e.target.value })}
                                            style={{ width: 150, padding: "3px 8px", fontSize: "0.75rem", border: "1px solid #f59e0b", borderRadius: "4px", background: "#fffbeb" }}
                                          />
                                      )}
                                    </div>
                                    <div style={{ display: "flex", gap: "10px", alignItems: "center", flexWrap: "wrap" }}>
                                      <input
                                        type="text"
                                        placeholder="Mô tả / Điều kiện (vd: Chỉ điền khi không có MST)"
                                        value={fieldDesc[field.id] || ""}
                                        onChange={(e) => setFieldDesc({ ...fieldDesc, [field.id]: e.target.value })}
                                        style={{ flex: 1, minWidth: 100, padding: "4px 8px", fontSize: "0.75rem", border: "1px solid #d1d5db", borderRadius: "4px" }}
                                      />
                                      
                                      <div style={{ display: "flex", alignItems: "center", gap: 6, flexShrink: 0 }}>
                                        <Sparkles size={14} color="#a855f7" />
                                        <select
                                          value={fieldDependsOn[field.id] || ""}
                                          onChange={(e) => setFieldDependsOn({ ...fieldDependsOn, [field.id]: e.target.value })}
                                          style={{ padding: "3px 6px", fontSize: "0.75rem", border: "1px solid #d8b4fe", borderRadius: "4px", background: "#faf5ff", color: "#6b21a8", cursor: "pointer", maxWidth: 200 }}
                                        >
                                          <option value="">Không có logic nhánh (Luôn hỏi)</option>
                                          {labeledList.filter(l => l.id !== field.id).map(l => {
                                            const tgtName = fieldData[l.id] !== undefined ? fieldData[l.id] : (previewData?.zones?.find((z: any) => String(z.idx) === l.blankIdx)?.suggested_label || l.id);
                                            return <option key={l.id} value={tgtName}>Chỉ hỏi khi điền: {tgtName}</option>;
                                          })}
                                        </select>
                                      </div>
                                      
                                      <div style={{ display: "flex", alignItems: "center", gap: 6, flexShrink: 0, paddingLeft: 6, borderLeft: "1px dashed #cbd5e1" }}>
                                        <span style={{ fontSize: "0.75rem", color: "#b91c1c", fontWeight: 600 }}>Hoặc:</span>
                                        <input
                                          type="text"
                                          placeholder="Nhóm 1 trong 2 (vd: giayto1)"
                                          value={fieldRequireOneOfGroup[field.id] || ""}
                                          onChange={(e) => setFieldRequireOneOfGroup({ ...fieldRequireOneOfGroup, [field.id]: e.target.value })}
                                          style={{ width: 140, padding: "3px 8px", fontSize: "0.75rem", border: "1px solid #fca5a5", borderRadius: "4px", background: "#fef2f2" }}
                                          title="Nhập chung tên nhóm cho MST và CCCD để bắt buộc khách phải điền ít nhất 1 loại"
                                        />
                                      </div>
                                    </div>
                                  </div>\n"""
        content = content[:adv_idx] + ui_new + content[end_adv_idx:]

# 5. Fix imports
if "Sparkles" not in content:
    content = content.replace("import { Search, UploadCloud, Eye, RefreshCw } from 'lucide-react';", "import { Search, UploadCloud, Eye, RefreshCw, X, Pencil, Trash2, Sparkles, ShieldCheck, FileText, Activity } from 'lucide-react';")

# 6. Fix TS2440 (Remove duplicate PdfFormPreview import)
if "import PdfFormPreview from '@/components/PdfFormPreview';" in content:
    parts = content.split("import PdfFormPreview from '@/components/PdfFormPreview';")
    if len(parts) > 2:
        content = "import PdfFormPreview from '@/components/PdfFormPreview';".join([parts[0], parts[1]]) + "".join(parts[2:])
    content = content.replace("import dynamic from 'next/dynamic';\nconst PdfFormPreview = dynamic(() => import('@/components/PdfFormPreview'), { ssr: false });", "")

with open("d:/TerraLegalAI/frontend/app/page.tsx", "w", encoding="utf-8") as f:
    f.write(content)
