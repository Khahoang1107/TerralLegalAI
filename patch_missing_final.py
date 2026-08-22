# -*- coding: utf-8 -*-
import os
import re

# 1. Update api.ts
api_path = r"d:\TerraLegalAI\frontend\lib\api.ts"
with open(api_path, "r", encoding="utf-8") as f:
    api_content = f.read()

if "previewPdf" not in api_content:
    new_method = """  async previewPdf(id: string, data: any): Promise<Blob> {
    const response = await client.post(`/forms/preview-pdf/${id}`, data, { responseType: 'blob' });
    return response.data;
  },
  async generateFormDocument"""
    api_content = api_content.replace('async generateFormDocument', new_method)
    with open(api_path, "w", encoding="utf-8") as f:
        f.write(api_content)
    print("Patched api.ts")

# 2. Update page.tsx
page_path = r"d:\TerraLegalAI\frontend\app\page.tsx"
with open(page_path, "r", encoding="utf-8") as f:
    page_content = f.read()

old_modal_regex = re.compile(r"function FormReviewModal\(\{ formId, initialData, onClose \}: \{ formId: string, initialData: any, onClose: \(\) => void \}\) \{.*?\n\}\n", re.DOTALL)

new_modal = """function FormReviewModal({ formId, initialData, onClose }: { formId: string, initialData: any, onClose: () => void }) {
  const [forms, setForms] = useState<any[]>([]);
  const [formData, setFormData] = useState<any>(initialData || {});
  const [generating, setGenerating] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  useEffect(() => {
    formsApi.getForms().then(setForms).catch(console.error);
  }, []);

  const formSchema = forms.find(f => f.id === formId);

  const handleDownload = async () => {
    setGenerating(true);
    try {
      const blob = await formsApi.generateFormDocument(formId, formData);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `form_${formId.slice(0, 8)}.docx`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      onClose();
    } catch (err) {
      console.error(err);
      alert("Có lỗi xảy ra khi tạo văn bản.");
    } finally {
      setGenerating(false);
    }
  };

  const handlePreview = async () => {
    setPreviewing(true);
    try {
      const blob = await formsApi.previewPdf(formId, formData);
      const url = window.URL.createObjectURL(blob);
      setPreviewUrl(url);
    } catch (err) {
      console.error(err);
      alert("Có lỗi xảy ra khi tải bản xem trước.");
    } finally {
      setPreviewing(false);
    }
  };

  // Tự động load preview lần đầu
  useEffect(() => {
    if (formSchema && !previewUrl && !previewing) {
      handlePreview();
    }
  }, [formSchema, previewUrl, previewing]); // Chỉ re-run khi formSchema load xong

  if (!formSchema) return (
    <div className="dialog-backdrop">
      <div className="rename-dialog" style={{ maxWidth: 600, padding: 30, textAlign: 'center' }}>
        <h3>Đang tải biểu mẫu...</h3>
      </div>
    </div>
  );

  return (
    <div className="dialog-backdrop">
      <div className="rename-dialog" style={{ maxWidth: 900, width: "95%", height: "85vh", display: "flex", flexDirection: "column" }}>
        <div className="dialog-head" style={{ padding: "15px 20px", borderBottom: "1px solid #eee" }}>
          <h2 style={{ margin: 0, fontSize: "1.2rem" }}>Kiểm tra dữ liệu: {formSchema.name}</h2>
          <button onClick={onClose} className="icon-button"><X size={18} /></button>
        </div>
        
        <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
          {/* Left panel - Inputs */}
          <div style={{ padding: "20px", overflowY: "auto", flex: "1 1 350px", borderRight: "1px solid #eee", display: "flex", flexDirection: "column" }}>
            <p style={{ color: "#64748b", fontSize: "0.9rem", marginBottom: 20 }}>
              Vui lòng kiểm tra lại thông tin dưới đây. Bạn có thể sửa trực tiếp nếu AI điền sai hoặc điền thiếu trước khi tải xuống file Word.
            </p>
            <div style={{ display: "flex", flexDirection: "column", gap: 15 }}>
              {formSchema.fields.map((field: any) => (
                <label key={field.key} style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: "0.9rem", fontWeight: 600 }}>
                  {field.name} {field.required && <span style={{ color: "red" }}>*</span>}
                  {field.description && <span style={{ fontSize: "0.75rem", color: "#64748b", fontWeight: 400 }}>{field.description.replace("[TU_DONG_DIEN]", "").trim()}</span>}
                  <input 
                    value={formData[field.key] || ""} 
                    onChange={(e) => setFormData({ ...formData, [field.key]: e.target.value })}
                    style={{ border: "1px solid #cbd5e1", padding: "10px", borderRadius: 6, fontSize: "0.95rem" }} 
                  />
                </label>
              ))}
            </div>
            
            <button 
              type="button" 
              className="secondary-button" 
              style={{ marginTop: 20, alignSelf: "flex-start" }}
              onClick={handlePreview}
              disabled={previewing}
            >
              <RefreshCw size={15} style={{ marginRight: 6 }} /> {previewing ? "Đang cập nhật..." : "Cập nhật bản xem trước PDF"}
            </button>
          </div>
          
          {/* Right panel - PDF Preview */}
          <div style={{ flex: "1.5 1 500px", background: "#f1f5f9", display: "flex", flexDirection: "column", position: "relative" }}>
            {previewing && (
              <div style={{ position: "absolute", top: 0, left: 0, right: 0, bottom: 0, background: "rgba(255,255,255,0.7)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 10 }}>
                <span style={{ fontWeight: 500, color: "#3b82f6" }}>Đang tạo bản xem trước...</span>
              </div>
            )}
            {previewUrl ? (
              <iframe src={`${previewUrl}#toolbar=0&navpanes=0&scrollbar=0`} style={{ width: "100%", height: "100%", border: "none" }} title="PDF Preview" />
            ) : (
              <div style={{ margin: "auto", color: "#64748b" }}>Bản xem trước sẽ hiển thị ở đây</div>
            )}
          </div>
        </div>
        
        <div className="dialog-actions" style={{ padding: "15px 20px", borderTop: "1px solid #eee", justifyContent: "flex-end" }}>
          <button className="secondary-button" onClick={onClose}>Hủy</button>
          <button className="primary-button" onClick={handleDownload} disabled={generating}>
            {generating ? "Đang tạo..." : "Hoàn tất & Tải xuống (Word)"}
          </button>
        </div>
      </div>
    </div>
  );
}
"""

if "FormReviewModal" in page_content and "previewing" not in page_content:
    new_content, count = old_modal_regex.subn(new_modal, page_content)
    if count > 0:
        with open(page_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print("Patched page.tsx successfully")
    else:
        print("Regex didn't match anything")
else:
    print("Could not find old modal or already patched")
