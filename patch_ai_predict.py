with open("d:/TerraLegalAI/frontend/app/page.tsx", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Inject handleAIPredict logic
old_logic = "const [activeZoneIdx, setActiveZoneIdx] = useState<string | null>(null);"
new_logic = """const [activeZoneIdx, setActiveZoneIdx] = useState<string | null>(null);
  const [isPredictingAI, setIsPredictingAI] = useState(false);

  const handleAIPredict = async () => {
    if (!previewData?.temp_id) return;
    setIsPredictingAI(true);
    try {
      const res = await formsApi.aiPredict(previewData.temp_id, editableZones);
      setEditableZones(res.zones);
      
      const newLabeledSnapshot = { ...labeledSnapshot };
      const newFieldOrder = [...fieldOrderSnapshot];
      let addedCount = 0;
      let fieldCounter = manualCounterRef.current;
      
      res.zones.forEach((z: any) => {
        if (z.suggested_label) {
          const idxStr = String(z.idx);
          if (!newLabeledSnapshot[idxStr] && !labeledZonesRef.current[idxStr]) {
            const fieldId = `field_${fieldCounter++}`;
            newLabeledSnapshot[idxStr] = fieldId;
            labeledZonesRef.current[idxStr] = fieldId;
            newFieldOrder.push(fieldId);
            fieldOrderRef.current.push(fieldId);
            addedCount++;
          }
        }
      });
      manualCounterRef.current = fieldCounter;
      setLabeledSnapshot(newLabeledSnapshot);
      setFieldOrderSnapshot(newFieldOrder);
      setLabeledCount(Object.keys(newLabeledSnapshot).length);
      
      showToast(`AI đã gợi ý và tự động chọn ${addedCount} vùng!`, "success");
    } catch (err) {
      showToast("Lỗi khi gọi AI phân tích", "error");
    } finally {
      setIsPredictingAI(false);
    }
  };"""

if "const [isPredictingAI" not in content:
    content = content.replace(old_logic, new_logic)

# 2. Inject button in step 2
old_btn = """                        <p style={{ color: "#6b7280", fontSize: "0.875rem", marginBottom: 16 }}>
                          Nhấp vào vùng trống trên PDF bên phải để dán nhãn. Sau khi xong, nhấn "Tiếp theo".
                        </p>"""

new_btn = """                        <p style={{ color: "#6b7280", fontSize: "0.875rem", marginBottom: 16 }}>
                          Nhấp vào vùng trống trên PDF bên phải để dán nhãn. Sau khi xong, nhấn "Tiếp theo".
                        </p>

                        <button
                          type="button"
                          onClick={handleAIPredict}
                          disabled={isPredictingAI || editableZones.length === 0}
                          style={{
                            width: "100%",
                            padding: "10px 16px",
                            marginBottom: 20,
                            borderRadius: "8px",
                            border: "none",
                            background: "linear-gradient(135deg, #6366f1 0%, #a855f7 100%)",
                            color: "#fff",
                            fontWeight: 600,
                            fontSize: "0.9rem",
                            cursor: (isPredictingAI || editableZones.length === 0) ? "not-allowed" : "pointer",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            gap: 8,
                            opacity: (isPredictingAI || editableZones.length === 0) ? 0.7 : 1,
                            boxShadow: "0 4px 6px -1px rgba(99, 102, 241, 0.2)"
                          }}
                        >
                          {isPredictingAI ? (
                            <>
                              <RefreshCw size={16} className="animate-spin" />
                              Đang nhờ AI phân tích...
                            </>
                          ) : (
                            <>
                              🪄 Phân tích tự động bằng AI
                            </>
                          )}
                        </button>"""

if "onClick={handleAIPredict}" not in content:
    content = content.replace(old_btn, new_btn)

# Ensure RefreshCw is imported
if "RefreshCw" not in content:
    content = content.replace("import { Search, UploadCloud, Eye, RefreshCw } from 'lucide-react';", "import { Search, UploadCloud, Eye, RefreshCw, X, Pencil, Trash2, Sparkles, ShieldCheck, FileText, Activity } from 'lucide-react';")

with open("d:/TerraLegalAI/frontend/app/page.tsx", "w", encoding="utf-8") as f:
    f.write(content)
