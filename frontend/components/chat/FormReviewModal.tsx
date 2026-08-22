import React, { useState, useEffect } from "react";
import { formsApi } from "@/lib/api";
import { X, Download, FileText, RefreshCw } from "lucide-react";

interface FormReviewModalProps {
  formId: string;
  initialData: Record<string, string>;
  onClose: () => void;
}

export default function FormReviewModal({ formId, initialData, onClose }: FormReviewModalProps) {
  const [formData, setFormData] = useState<Record<string, string>>(initialData || {});
  const [formSchema, setFormSchema] = useState<any>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [downloadingWord, setDownloadingWord] = useState(false);
  const [downloadingPdf, setDownloadingPdf] = useState(false);

  useEffect(() => {
    formsApi.getForm(formId).then(form => {
      if (form) setFormSchema(form);
    }).catch(console.error);
  }, [formId]);

  const loadPreview = async () => {
    setLoadingPreview(true);
    try {
      const blob = await formsApi.previewPdf(formId, formData);
      if (previewUrl) URL.revokeObjectURL(previewUrl);
      const url = URL.createObjectURL(blob);
      setPreviewUrl(url);
    } catch (err) {
      console.error("Lỗi tải bản xem trước", err);
    } finally {
      setLoadingPreview(false);
    }
  };

  useEffect(() => {
    loadPreview();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleDownload = async (format: "docx" | "pdf") => {
    if (format === "docx") setDownloadingWord(true);
    else setDownloadingPdf(true);

    try {
      const blob = await formsApi.generateFormDocument(formId, formData, format);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `Tai_lieu_${format.toUpperCase()}.${format}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Lỗi tải xuống", err);
      alert("Không thể tải xuống tài liệu. Vui lòng thử lại.");
    } finally {
      if (format === "docx") setDownloadingWord(false);
      else setDownloadingPdf(false);
    }
  };

  if (!formSchema) return (
    <div style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0, backgroundColor: "rgba(0,0,0,0.5)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 9999 }}>
      <div style={{ background: "white", padding: 20, borderRadius: 8 }}>Đang tải thông tin biểu mẫu...</div>
    </div>
  );

  return (
    <div style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0, backgroundColor: "rgba(0,0,0,0.5)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 9999 }}>
      <div style={{ background: "white", width: "90%", maxWidth: 1200, height: "85vh", borderRadius: 12, display: "flex", flexDirection: "column", overflow: "hidden", boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.1)" }}>
        
        {/* Header */}
        <div style={{ padding: "16px 24px", borderBottom: "1px solid #e5e7eb", display: "flex", justifyContent: "space-between", alignItems: "center", background: "#f8fafc" }}>
          <h2 style={{ margin: 0, fontSize: "1.25rem", color: "#1e293b", display: "flex", alignItems: "center", gap: 8 }}>
            <FileText size={22} color="#4f46e5" />
            Kiểm tra dữ liệu: {formSchema.name}
          </h2>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: "#64748b" }}>
            <X size={24} />
          </button>
        </div>

        {/* Content */}
        <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
          
          {/* Left Panel: Form Data */}
          <div style={{ width: "40%", borderRight: "1px solid #e5e7eb", padding: 24, overflowY: "auto", display: "flex", flexDirection: "column", gap: 16 }}>
            <h3 style={{ margin: 0, fontSize: "1rem", color: "#334155" }}>Thông tin đã thu thập</h3>
            <p style={{ fontSize: "0.875rem", color: "#64748b", margin: 0 }}>Vui lòng kiểm tra và chỉnh sửa thông tin trước khi tải xuống tài liệu.</p>
            
            <div style={{ display: "flex", flexDirection: "column", gap: 12, marginTop: 8 }}>
              {(() => {
                const displayFields: any[] = [];
                const processedGroups = new Set();
                
                formSchema.fields?.forEach((field: any) => {
                  if (field.type === 'digit_group') {
                    const gKey = field.group_key || field.key || field.name;
                    if (!processedGroups.has(gKey)) {
                      processedGroups.add(gKey);
                      displayFields.push({ ...field, uiKey: gKey, isGroup: true });
                    }
                  } else {
                    displayFields.push({ ...field, uiKey: field.key || field.name });
                  }
                });
                
                return displayFields.map((field: any) => (
                  <label key={field.uiKey} style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: "0.875rem", fontWeight: 500, color: "#475569" }}>
                    <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      {(field.name && field.name.includes('_') && field.description && !field.description.startsWith('Nhập thông tin')) ? field.description : (field.name || field.key)}
                      {field.isGroup && (
                        <span style={{ fontSize: "0.7rem", color: "#6366f1", background: "#eef2ff", borderRadius: 4, padding: "1px 6px", fontWeight: 600 }}>
                          Mỗi ký tự = 1 ô
                        </span>
                      )}
                    </span>
                    {field.type === 'boolean' ? (
                      <input
                        type="checkbox"
                        checked={
                          formData[field.uiKey] === 'true' || formData[field.uiKey] === 'có' || formData[field.uiKey] === 'x' || formData[field.uiKey] === '☑' ||
                          (formData[field.uiKey] === undefined && (formData[field.name] === 'true' || formData[field.name] === 'có' || formData[field.name] === 'x'))
                        }
                        onChange={(e) => setFormData({ ...formData, [field.uiKey]: e.target.checked ? 'true' : 'false' })}
                        style={{ width: 20, height: 20, marginTop: 4 }}
                      />
                    ) : (
                      <>
                        <input
                          value={
                            formData[field.uiKey] === "__SKIPPED__" ? "" : 
                            (formData[field.uiKey] !== undefined ? formData[field.uiKey] : (formData[field.name] || ""))
                          }
                          onChange={(e) => setFormData({ ...formData, [field.uiKey]: e.target.value })}
                          style={{ padding: "8px 12px", border: "1px solid #cbd5e1", borderRadius: 6, fontSize: "0.9rem" }}
                          placeholder={field.isGroup ? "Nhập liền không dấu cách (vd: 110122008111)" : ""}
                        />
                        {field.isGroup && (
                          <span style={{ fontSize: "0.7rem", color: "#64748b" }}>
                            Nhập chuỗi số liền nhau — hệ thống sẽ tự điền từng ô
                          </span>
                        )}
                      </>
                    )}
                  </label>
                ));
              })()}
            </div>
            
            <div style={{ marginTop: "auto", paddingTop: 20 }}>
              <button 
                type="button"
                onClick={loadPreview}
                disabled={loadingPreview}
                style={{ width: "100%", padding: "10px", borderRadius: 6, border: "1px solid #cbd5e1", background: "white", color: "#334155", fontWeight: 600, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}
              >
                <RefreshCw size={16} className={loadingPreview ? "animate-spin" : ""} />
                Cập nhật bản xem trước (PDF)
              </button>
            </div>
          </div>
          
          {/* Right Panel: PDF Preview */}
          <div style={{ width: "60%", background: "#f1f5f9", display: "flex", flexDirection: "column", padding: 16 }}>
            <div style={{ flex: 1, background: "white", borderRadius: 8, overflow: "hidden", border: "1px solid #cbd5e1", display: "flex", alignItems: "center", justifyContent: "center", position: "relative" }}>
              {loadingPreview ? (
                <div style={{ color: "#64748b", display: "flex", flexDirection: "column", alignItems: "center", gap: 8 }}>
                  <RefreshCw size={24} className="animate-spin" />
                  <span>Đang tạo bản xem trước...</span>
                </div>
              ) : previewUrl ? (
                <iframe src={`${previewUrl}#toolbar=0`} style={{ width: "100%", height: "100%", border: "none" }} />
              ) : (
                <span style={{ color: "#94a3b8" }}>Không có bản xem trước</span>
              )}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div style={{ padding: "16px 24px", borderTop: "1px solid #e5e7eb", display: "flex", justifyContent: "flex-end", gap: 12, background: "#f8fafc" }}>
          <button onClick={onClose} style={{ padding: "10px 20px", borderRadius: 6, border: "1px solid #cbd5e1", background: "white", color: "#475569", fontWeight: 500, cursor: "pointer" }}>
            Đóng
          </button>
          <button 
            onClick={() => handleDownload("pdf")} 
            disabled={downloadingPdf}
            style={{ padding: "10px 20px", borderRadius: 6, border: "none", background: "#f43f5e", color: "white", fontWeight: 600, cursor: "pointer", display: "flex", alignItems: "center", gap: 8 }}
          >
            <Download size={18} />
            {downloadingPdf ? "Đang tạo..." : "Tải xuống PDF"}
          </button>
          <button 
            onClick={() => handleDownload("docx")} 
            disabled={downloadingWord}
            style={{ padding: "10px 20px", borderRadius: 6, border: "none", background: "#4f46e5", color: "white", fontWeight: 600, cursor: "pointer", display: "flex", alignItems: "center", gap: 8 }}
          >
            <Download size={18} />
            {downloadingWord ? "Đang tạo..." : "Tải xuống Word"}
          </button>
        </div>
        
      </div>
    </div>
  );
}
