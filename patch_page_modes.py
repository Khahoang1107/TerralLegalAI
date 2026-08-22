
import re
import codecs

def main():
    with codecs.open("d:/TerraLegalAI/frontend/app/page.tsx", "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Add states
    states_injection = """  const [showModal, setShowModal] = useState(false);
  const [showModeSelector, setShowModeSelector] = useState(false);
  const [showManualUploadModal, setShowManualUploadModal] = useState(false);
  const [manualJsonFile, setManualJsonFile] = useState<File | null>(null);
  const [manualDocxFile, setManualDocxFile] = useState<File | null>(null);
  const [manualUploading, setManualUploading] = useState(false);
"""
    content = content.replace("  const [showModal, setShowModal] = useState(false);", states_injection)

    # 2. Add reset logic to resetModal
    reset_injection = """  const resetModal = () => {
    setShowModal(false);
    setShowModeSelector(false);
    setShowManualUploadModal(false);
    setManualJsonFile(null);
    setManualDocxFile(null);
    setManualUploading(false);
"""
    content = content.replace("  const resetModal = () => {\n    setShowModal(false);", reset_injection)

    # 3. Add handleManualUpload
    manual_handler = """
  const handleManualUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!manualJsonFile || !manualDocxFile) {
      showToast("Vui lòng chọn cả file JSON và DOCX", "error");
      return;
    }
    setManualUploading(true);
    try {
      await formsApi.uploadForm(manualJsonFile, manualDocxFile);
      showToast("Tạo biểu mẫu bằng cấu hình thành công!", "success");
      resetModal();
      fetchForms();
    } catch (err: any) {
      const msg = err.response?.data?.detail || "Lỗi khi tạo biểu mẫu";
      showToast(typeof msg === "string" ? msg : JSON.stringify(msg), "error");
    } finally {
      setManualUploading(false);
    }
  };

"""
    content = content.replace("  const handleAnalyzeDocx = async", manual_handler + "  const handleAnalyzeDocx = async")

    # 4. Replace the "Thêm Biểu mẫu thông minh" button click
    content = content.replace("onClick={() => setShowModal(true)}", "onClick={() => setShowModeSelector(true)}")

    # 5. Add Modals
    modals_html = """
      {/* Mode Selector Dialog */}
      {showModeSelector && (
        <div className="dialog-backdrop" onClick={resetModal}>
          <div className="rename-dialog" style={{ maxWidth: 480, width: "95%" }} onClick={(e) => e.stopPropagation()}>
            <div className="dialog-head">
              <h2>Chọn chế độ Tạo Biểu mẫu</h2>
              <button type="button" className="icon-button" onClick={resetModal}><X size={18} /></button>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 16, marginTop: 10 }}>
              <button 
                onClick={() => { setShowModeSelector(false); setShowModal(true); }}
                style={{ padding: 16, border: "1px solid #cfd7d1", borderRadius: 8, background: "#f8fafc", textAlign: "left", cursor: "pointer", transition: "all 0.2s" }}
                onMouseOver={(e) => e.currentTarget.style.borderColor = "#4f46e5"}
                onMouseOut={(e) => e.currentTarget.style.borderColor = "#cfd7d1"}
              >
                <div style={{ fontWeight: 600, color: "#1e293b", fontSize: 15, marginBottom: 4 }}>✨ Tạo bằng AI (Trực quan)</div>
                <div style={{ color: "#64748b", fontSize: 13 }}>Tải file Word trống lên, AI sẽ tự động quét khoảng trống và gợi ý tên trường. (Khuyên dùng)</div>
              </button>

              <button 
                onClick={() => { setShowModeSelector(false); setShowManualUploadModal(true); }}
                style={{ padding: 16, border: "1px solid #cfd7d1", borderRadius: 8, background: "#f8fafc", textAlign: "left", cursor: "pointer", transition: "all 0.2s" }}
                onMouseOver={(e) => e.currentTarget.style.borderColor = "#4f46e5"}
                onMouseOut={(e) => e.currentTarget.style.borderColor = "#cfd7d1"}
              >
                <div style={{ fontWeight: 600, color: "#1e293b", fontSize: 15, marginBottom: 4 }}>⚙ Tải lên cấu hình (Nâng cao)</div>
                <div style={{ color: "#64748b", fontSize: 13 }}>Tải lên trực tiếp file JSON Schema và file Word mẫu đã cắm sẵn thẻ Jinja2. Dành cho Admin pro.</div>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Manual Upload Modal */}
      {showManualUploadModal && (
        <div className="dialog-backdrop" onClick={resetModal}>
          <form className="rename-dialog" style={{ maxWidth: 500, width: "95%" }} onSubmit={handleManualUpload} onClick={(e) => e.stopPropagation()}>
            <div className="dialog-head">
              <h2>Tạo biểu mẫu từ File cấu hình</h2>
              <button type="button" className="icon-button" onClick={resetModal}><X size={18} /></button>
            </div>
            <p style={{ fontSize: 13, color: "#64748b", marginBottom: 16 }}>
              Vui lòng tải lên cả File JSON chứa cấu trúc field và File DOCX mẫu tương ứng. 
              <br/>
              <a href="/sample_form.json" download style={{ color: "#4f46e5", textDecoration: "underline", fontWeight: 600 }}>Tải file JSON mẫu tại đây</a>
            </p>

            <label style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 13, fontWeight: 600, marginBottom: 14 }}>
              1. File cấu hình Schema (.json) *
              <input type="file" accept=".json" onChange={(e) => setManualJsonFile(e.target.files?.[0] || null)} style={{ border: "1px solid #cfd7d1", padding: "10px", borderRadius: 6, fontSize: 14 }} required />
            </label>

            <label style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 13, fontWeight: 600, marginBottom: 20 }}>
              2. File Word mẫu (.docx) *
              <input type="file" accept=".docx" onChange={(e) => setManualDocxFile(e.target.files?.[0] || null)} style={{ border: "1px solid #cfd7d1", padding: "10px", borderRadius: 6, fontSize: 14 }} required />
            </label>

            <div className="dialog-actions">
              <button type="button" className="secondary-button" onClick={resetModal} disabled={manualUploading}>Hủy</button>
              <button type="submit" className="primary-button" disabled={manualUploading}>
                {manualUploading ? "Đang xử lý..." : "Tạo biểu mẫu"}
              </button>
            </div>
          </form>
        </div>
      )}
"""
    content = content.replace("{/* Create Form Modal */}", modals_html + "\n      {/* Create Form Modal */}")

    with codecs.open("d:/TerraLegalAI/frontend/app/page.tsx", "w", encoding="utf-8") as f:
        f.write(content)

    print("Patched page.tsx successfully.")

if __name__ == "__main__":
    main()

