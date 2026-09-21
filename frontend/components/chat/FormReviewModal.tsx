import React, { useState, useEffect, useRef } from "react";
import { formsApi } from "@/lib/api";
import { X, Download, FileText, RefreshCw, ExternalLink } from "lucide-react";

interface FormReviewModalProps {
  formId: string;
  initialData: Record<string, string>;
  onClose: () => void;
}

export default function FormReviewModal({ formId, initialData, onClose }: FormReviewModalProps) {
  // Normalize initialData: convert boolean/number values to strings
  const normalizeData = (data: Record<string, any>): Record<string, string> => {
    const result: Record<string, string> = {};
    for (const [k, v] of Object.entries(data || {})) {
      if (v === null || v === undefined) result[k] = '';
      else if (typeof v === 'boolean') result[k] = v ? 'true' : 'false';
      else result[k] = String(v);
    }
    return result;
  };
  const [formData, setFormData] = useState<Record<string, string>>(() => normalizeData(initialData));
  const [formSchema, setFormSchema] = useState<any>(null);
  const [previewImages, setPreviewImages] = useState<string[]>([]);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [downloadingWord, setDownloadingWord] = useState(false);
  const [downloadingPdf, setDownloadingPdf] = useState(false);
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    formsApi.getForm(formId).then(form => {
      if (form) setFormSchema(form);
    }).catch(console.error);
  }, [formId]);

  // Load preview với data bất kỳ (không phụ thuộc state previewUrl)
  const loadPreview = (data: Record<string, string>) => {
    setLoadingPreview(true);
    formsApi.previewImages(formId, data)
      .then(images => setPreviewImages(images))
      .catch(err => console.error("Lỗi tải bản xem trước", err))
      .finally(() => setLoadingPreview(false));
  };

  const openPdfInNewTab = async () => {
    try {
      const blob = await formsApi.previewPdf(formId, formData);
      const url = URL.createObjectURL(blob);
      window.open(url, "_blank");
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (err) {
      console.error("Lỗi mở PDF", err);
    }
  };

  // Tải preview ngay khi mở modal (1 lần duy nhất)
  useEffect(() => {
    loadPreview(formData);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Khi user thay đổi formData, ẩn preview cũ ngay để không hiển thị dữ liệu
  // lệch với cột nhập liệu; sau đó render lại nhanh với dữ liệu mới.
  // mountCountRef để bỏ qua lần đầu tiên (mount) — chỉ react với thay đổi của user
  const mountCountRef = useRef(0);
  useEffect(() => {
    mountCountRef.current += 1;
    if (mountCountRef.current <= 1) return; // bỏ qua lần mount đầu
    if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
    setLoadingPreview(true);
    debounceTimerRef.current = setTimeout(() => {
      loadPreview(formData);
    }, 400);
    return () => {
      if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [formData]);

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

  // Lấy giá trị hiện tại của field theo nhiều key
  const getFieldValue = (field: any): string => {
    const keys = [field.group_key, field.key, field.name].filter(Boolean);
    for (const key of keys) {
      const v = formData[key];
      if (v !== undefined && v !== null) return String(v);
    }
    return '';
  };

  // Set giá trị theo TẤT CẢ keys của field (key + name + group_key)
  const setFieldValue = (field: any, value: string) => {
    const keys = [field.group_key, field.key, field.name].filter(Boolean);
    setFormData(prev => {
      const next = { ...prev };
      keys.forEach(k => { next[k] = value; });
      return next;
    });
  };

  // Các ô số tách rời trong file Word cùng dùng một giá trị chung. Chỉ gộp ở
  // lớp hiển thị để người dùng nhập một lần; payload vẫn giữ nguyên key cũ.
  const displayFields = (() => {
    const groups = new Set<string>();
    const fields = (formSchema?.fields || []).slice().sort((a: any, b: any) => {
      const ordA = a.display_order ?? 9999;
      const ordB = b.display_order ?? 9999;
      return ordA - ordB;
    });
    return fields.filter((field: any) => {
      if (field.type !== "digit_group") return true;
      const groupKey = field.group_key || field.name || field.key;
      if (groups.has(groupKey)) return false;
      groups.add(groupKey);
      return true;
    });
  })();

  if (!formSchema) return (
    <div style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0, backgroundColor: "rgba(0,0,0,0.5)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 9999 }}>
      <div style={{ background: "white", padding: 20, borderRadius: 8 }}>Đang tải thông tin biểu mẫu...</div>
    </div>
  );

  return (
    <div
      style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0, backgroundColor: "rgba(0,0,0,0.5)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 9999 }}
      onClick={onClose}
    >
      <div
        style={{ background: "white", width: "95vw", maxWidth: 1550, height: "92vh", borderRadius: 12, display: "flex", flexDirection: "column", overflow: "hidden", boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.1)", position: "relative", isolation: "isolate" }}
        onClick={(e) => e.stopPropagation()}
      >
        
        <div style={{ padding: "14px 20px", borderBottom: "1px solid #e5e7eb", display: "flex", justifyContent: "space-between", alignItems: "center", background: "#f8fafc" }}>
          <h2 style={{ margin: 0, fontSize: "1.15rem", color: "#1e293b", display: "flex", alignItems: "center", gap: 8 }}>
            <FileText size={20} color="#4f46e5" />
            Kiểm tra dữ liệu: {formSchema.name}
          </h2>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            {previewImages.length > 0 && (
              <button
                type="button"
                onClick={openPdfInNewTab}
                title="Mở PDF trong tab mới của trình duyệt để xem rõ nét hơn"
                style={{
                  padding: "5px 10px",
                  fontSize: "0.78rem",
                  color: "#475569",
                  background: "#fff",
                  border: "1px solid #cbd5e1",
                  borderRadius: 6,
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 5,
                  cursor: "pointer",
                  fontWeight: 600
                }}
              >
                <ExternalLink size={14} />
                <span>Mở tab mới</span>
              </button>
            )}
            <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: "#64748b" }}>
              <X size={22} />
            </button>
          </div>
        </div>

        <div style={{ display: "flex", flex: 1, overflow: "hidden", minHeight: 0 }}>
          {/* LEFT PANEL - form fields */}
          <div style={{ flex: "0 0 38%", width: "38%", minWidth: 320, borderRight: "1px solid #e5e7eb", padding: 20, overflowY: "auto", display: "flex", flexDirection: "column", gap: 14, position: "relative", zIndex: 2 }}>
            <h3 style={{ margin: 0, fontSize: "0.95rem", color: "#334155" }}>Thông tin đã thu thập</h3>
            
            <div style={{ display: "flex", flexDirection: "column", gap: 14, marginTop: 4 }}>
              {displayFields.map((field: any, idx: number) => {
                const val = getFieldValue(field);
                const labelText = (field.name && field.name.includes('_') && field.description && !field.description.startsWith('Nhập')) ? field.description : (field.name || field.key);
                
                if (field.type === 'boolean') {
                  const isChecked = ['true', 'có', 'x', '☑', 'rồi', 'đúng', '1'].includes(String(val ?? '').toLowerCase().trim());
                  return (
                    <label key={idx} style={{ display: "flex", alignItems: "center", gap: 10, fontSize: "0.875rem", cursor: 'pointer', userSelect: 'none', position: 'relative', zIndex: 10 }}>
                      <input
                        type="checkbox"
                        checked={isChecked}
                        onChange={(e) => {
                          e.stopPropagation();
                          setFieldValue(field, e.target.checked ? 'true' : 'false');
                        }}
                        onClick={(e) => e.stopPropagation()}
                        style={{ width: 18, height: 18, cursor: 'pointer', flexShrink: 0, pointerEvents: 'auto', position: 'relative', zIndex: 10 }}
                      />
                      <span style={{ color: "#475569" }}>{labelText}</span>
                    </label>
                  );
                }

                if (field.type === 'choice') {
                  const options = Array.isArray(field.options) ? field.options : [];
                  return <div key={idx} style={{ display: "flex", flexDirection: "column", gap: 6 }}><span style={{ fontSize: "0.875rem", fontWeight: 500, color: "#475569" }}>{labelText}</span><select value={val === '__SKIPPED__' ? '' : val} onChange={(e) => setFieldValue(field, e.target.value)} style={{ padding: "8px 12px", border: "1px solid #cbd5e1", borderRadius: 6, fontSize: "0.9rem" }}><option value="">Chọn đáp án...</option>{options.map((option: string) => <option key={option} value={option}>{option}</option>)}</select></div>;
                }

                return (
                  <div key={idx} style={{ display: "flex", flexDirection: "column", gap: 4, position: 'relative', zIndex: 10 }}>
                    <span style={{ fontSize: "0.875rem", fontWeight: 500, color: "#475569" }}>
                      {labelText}
                    </span>
                    {field.type === 'textarea' || (val && val.length > 50) ? (
                      <textarea
                        value={val === '__SKIPPED__' ? '' : val}
                        onChange={(e) => setFieldValue(field, e.target.value)}
                        onClick={(e) => e.stopPropagation()}
                        style={{ padding: "8px 12px", border: "1px solid #cbd5e1", borderRadius: 6, fontSize: "0.9rem", width: "100%", minHeight: "80px", boxSizing: "border-box", pointerEvents: 'auto', position: 'relative', zIndex: 10 }}
                      />
                    ) : (
                      <input
                        type="text"
                        value={val === '__SKIPPED__' ? '' : val}
                        inputMode={field.type === 'digit_group' ? "numeric" : undefined}
                        onChange={(e) => setFieldValue(
                          field,
                          field.type === 'digit_group' ? e.target.value.replace(/\D/g, '') : e.target.value
                        )}
                        onClick={(e) => e.stopPropagation()}
                        style={{ padding: "8px 12px", border: "1px solid #cbd5e1", borderRadius: 6, fontSize: "0.9rem", width: "100%", boxSizing: "border-box", pointerEvents: 'auto', position: 'relative', zIndex: 10 }}
                      />
                    )}
                    {field.type === 'digit_group' && (
                      <span style={{ fontSize: "0.72rem", color: "#64748b" }}>
                        Nhập một dãy số liền nhau — bản xem trước sẽ đặt từng chữ số vào từng ô.
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
          
          {/* RIGHT PANEL - PDF preview, fully contained */}
          <div style={{ flex: 1, minWidth: 400, background: "#1e293b", display: "flex", flexDirection: "column", padding: 0, overflow: "hidden", position: "relative", zIndex: 1 }}>
            <div style={{ flex: 1, background: "#334155", overflow: "hidden", display: "flex", alignItems: "center", justifyContent: "center", position: "relative" }}>
              {loadingPreview ? (
                <div style={{ color: "#cbd5e1", display: "flex", flexDirection: "column", alignItems: "center", gap: 8 }}>
                  <RefreshCw size={24} className="animate-spin" />
                  <span>Đang cập nhật...</span>
                </div>
              ) : previewImages.length > 0 ? (
                <div style={{ width: "100%", height: "100%", overflow: "auto", padding: 16, boxSizing: "border-box" }}>
                  {previewImages.map((src, index) => (
                    <img
                      key={index}
                      src={src}
                      alt={`Trang ${index + 1}`}
                      style={{ width: "100%", height: "auto", display: "block", marginBottom: 16, background: "white", boxShadow: "0 2px 8px rgba(0,0,0,.25)" }}
                    />
                  ))}
                </div>
              ) : (
                <div style={{ color: "#cbd5e1" }}>Không thể tạo bản xem trước.</div>
              )}
            </div>
          </div>
        </div>

        <div style={{ padding: "14px 20px", borderTop: "1px solid #e5e7eb", display: "flex", justifyContent: "flex-end", gap: 12, background: "#f8fafc" }}>
          <button onClick={onClose} style={{ padding: "9px 18px", borderRadius: 6, border: "1px solid #cbd5e1", background: "white", color: "#475569", fontWeight: 500, cursor: "pointer" }}>
            Đóng
          </button>
          <button 
            onClick={() => handleDownload("pdf")} 
            disabled={downloadingPdf}
            style={{ padding: "9px 18px", borderRadius: 6, border: "none", background: "#f43f5e", color: "white", fontWeight: 600, cursor: "pointer", display: "flex", alignItems: "center", gap: 8 }}
          >
            <Download size={18} />
            {downloadingPdf ? "Đang tạo..." : "Tải xuống PDF"}
          </button>
          <button 
            onClick={() => handleDownload("docx")} 
            disabled={downloadingWord}
            style={{ padding: "9px 18px", borderRadius: 6, border: "none", background: "#4f46e5", color: "white", fontWeight: 600, cursor: "pointer", display: "flex", alignItems: "center", gap: 8 }}
          >
            <Download size={18} />
            {downloadingWord ? "Đang tạo..." : "Tải xuống Word"}
          </button>
        </div>
      </div>
    </div>
  );
}
