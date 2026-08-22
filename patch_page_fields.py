import sys

with open("d:/TerraLegalAI/frontend/app/page.tsx", "r", encoding="utf-8") as f:
    content = f.read()

# 1. State hooks
if "const [fieldType" not in content:
    hook_insert_pos = content.find("const { toast, show: showToast, hide: hideToast } = useToast();")
    if hook_insert_pos != -1:
        new_hooks = """  const [fieldType, setFieldType] = useState<Record<string, string>>({});
  const [fieldGroupKey, setFieldGroupKey] = useState<Record<string, string>>({});
  const [fieldDependsOn, setFieldDependsOn] = useState<Record<string, string>>({});
  const [fieldRequireOneOfGroup, setFieldRequireOneOfGroup] = useState<Record<string, string>>({});
  """
        content = content[:hook_insert_pos] + new_hooks + content[hook_insert_pos:]

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

# 3. Payload generation
payload_old = """      const zone = previewData?.zones?.find((z: any) => String(z.idx) === f.blankIdx);
      const isCheckbox = zone?.field_type === 'checkbox';
      const suggested = zone?.suggested_label || zone?.ai_label || "";
      const finalName = fieldData[f.id] !== undefined ? fieldData[f.id] : (suggested || f.id);
      
      const customDesc = fieldDesc[f.id];
      const defaultDesc = isCheckbox ? `Có hay không: ${finalName}?` : `Nhập thông tin cho ${finalName}`;
      
      return {
        key: f.id,
        name: finalName,
        description: customDesc || defaultDesc,
        required: fieldRequired[f.id] !== false,
        type: isCheckbox ? "boolean" : "string"
      };"""

payload_new = """      const zone = previewData?.zones?.find((z: any) => String(z.idx) === f.blankIdx);
      const suggested = zone?.suggested_label || zone?.ai_label || "";
      const finalName = fieldData[f.id] !== undefined ? fieldData[f.id] : (suggested || f.id);
      
      const customDesc = fieldDesc[f.id];
      const resolvedType = fieldType[f.id] || (zone?.field_type === 'checkbox' ? 'checkbox' : 'text');
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
        const gk = (fieldGroupKey?.[f.id] || finalName || f.id).trim();
        base.group_key = gk;
        base.digit_index = parseInt(String(zone?.idx)) || 0;
      }
      return base;"""
content = content.replace(payload_old, payload_new)

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
                                          style={{ padding: "3px 6px", fontSize: "0.75rem", border: "1px solid #d8b4fe", borderRadius: "4px", background: "#faf5ff", color: "#6b21a8", cursor: "pointer" }}
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
                                  </div>"""

content = content.replace(ui_old, ui_new)

with open("d:/TerraLegalAI/frontend/app/page.tsx", "w", encoding="utf-8") as f:
    f.write(content)
