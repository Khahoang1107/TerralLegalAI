"use client";

import React, { useState, useEffect } from "react";
import {
  X, User, Sliders, MapPin, Sparkles, Check, Monitor, Shield, Save
} from "lucide-react";

export interface UserSettings {
  fullName: string;
  email?: string;
  region: string;
  responseStyle: "detailed" | "concise" | "actionable";
  autoShowRightPanel: boolean;
  fontSize: "normal" | "large";
}

const DEFAULT_SETTINGS: UserSettings = {
  fullName: "Truc Thanh",
  email: "tructhanh@terralegal.vn",
  region: "TP. Hồ Chí Minh",
  responseStyle: "detailed",
  autoShowRightPanel: true,
  fontSize: "normal",
};

const PROVINCES = [
  "TP. Hồ Chí Minh",
  "Hà Nội",
  "Đà Nẵng",
  "Vĩnh Long",
  "Bình Dương",
  "Đồng Nai",
  "Long An",
  "Cần Thơ",
  "Hải Phòng",
  "Quảng Ninh",
  "Khánh Hòa",
  "Bà Rịa - Vũng Tàu",
  "Khác (Áp dụng khung chung Toàn quốc)",
];

interface UserSettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  userName: string;
  onSave?: (settings: UserSettings) => void;
}

export default function UserSettingsModal({
  isOpen,
  onClose,
  userName,
  onSave,
}: UserSettingsModalProps) {
  const [activeTab, setActiveTab] = useState<"profile" | "ai" | "display">("profile");
  const [settings, setSettings] = useState<UserSettings>(DEFAULT_SETTINGS);
  const [isSaved, setIsSaved] = useState(false);

  useEffect(() => {
    try {
      const saved = localStorage.getItem("terra_user_settings");
      if (saved) {
        const parsed = JSON.parse(saved);
        setSettings({ ...DEFAULT_SETTINGS, ...parsed, fullName: userName || parsed.fullName });
      } else {
        setSettings((prev) => ({ ...prev, fullName: userName || prev.fullName }));
      }
    } catch {
      // fallback to default
    }
  }, [userName, isOpen]);

  if (!isOpen) return null;

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    try {
      localStorage.setItem("terra_user_settings", JSON.stringify(settings));
    } catch (err) {
      console.error(err);
    }
    setIsSaved(true);
    if (onSave) onSave(settings);
    setTimeout(() => {
      setIsSaved(false);
      onClose();
    }, 600);
  };

  return (
    <div className="dialog-backdrop" onClick={onClose}>
      <div
        className="settings-modal"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        {/* Header */}
        <div className="settings-header">
          <div className="settings-header-title">
            <div className="settings-icon-badge">
              <Sliders size={20} />
            </div>
            <div>
              <h3>Cài đặt & Tùy chỉnh</h3>
              <p>Tối ưu hóa trợ lý pháp lý theo nhu cầu cá nhân của bạn</p>
            </div>
          </div>
          <button type="button" className="icon-button close-btn" onClick={onClose} title="Đóng">
            <X size={18} />
          </button>
        </div>

        {/* Body with Sidebar Tabs */}
        <div className="settings-body">
          <aside className="settings-nav">
            <button
              type="button"
              className={`settings-nav-item ${activeTab === "profile" ? "active" : ""}`}
              onClick={() => setActiveTab("profile")}
            >
              <User size={17} />
              <span>Hồ sơ & Địa phương</span>
            </button>
            <button
              type="button"
              className={`settings-nav-item ${activeTab === "ai" ? "active" : ""}`}
              onClick={() => setActiveTab("ai")}
            >
              <Sparkles size={17} />
              <span>Cấu hình Trợ lý AI</span>
            </button>
            <button
              type="button"
              className={`settings-nav-item ${activeTab === "display" ? "active" : ""}`}
              onClick={() => setActiveTab("display")}
            >
              <Monitor size={17} />
              <span>Giao diện & Tiện ích</span>
            </button>

            <div className="settings-nav-footer">
              <Shield size={14} />
              <span>Dữ liệu lưu an toàn trên trình duyệt</span>
            </div>
          </aside>

          <form className="settings-content" onSubmit={handleSave}>
            {activeTab === "profile" && (
              <div className="settings-section">
                <h4>Thông tin người dùng</h4>
                <div className="form-group">
                  <label>Họ và tên</label>
                  <input
                    type="text"
                    value={settings.fullName}
                    onChange={(e) => setSettings({ ...settings, fullName: e.target.value })}
                    placeholder="Nhập tên của bạn"
                    required
                  />
                </div>

                <div className="form-group">
                  <label>Địa chỉ Email</label>
                  <input
                    type="email"
                    value={settings.email || ""}
                    onChange={(e) => setSettings({ ...settings, email: e.target.value })}
                    placeholder="name@example.com"
                  />
                </div>

                <h4 style={{ marginTop: "24px" }}>Địa phương áp dụng thủ tục</h4>
                <p className="form-hint">
                  Hệ thống AI sẽ ưu tiên đối chiếu bảng giá đất, quy hoạch và quy định hành chính đặc thù của tỉnh/thành phố này.
                </p>
                <div className="form-group">
                  <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <MapPin size={15} className="text-emerald" /> Tỉnh / Thành phố
                  </label>
                  <select
                    value={settings.region}
                    onChange={(e) => setSettings({ ...settings, region: e.target.value })}
                    className="settings-select"
                  >
                    {PROVINCES.map((prov) => (
                      <option key={prov} value={prov}>
                        {prov}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            )}

            {activeTab === "ai" && (
              <div className="settings-section">
                <h4>Phong cách phản hồi của AI</h4>
                <p className="form-hint">
                  Chọn mức độ chi tiết khi TerraLegalAI trích dẫn và trả lời vướng mắc pháp lý đất đai.
                </p>

                <div className="radio-cards">
                  <label
                    className={`radio-card ${settings.responseStyle === "detailed" ? "selected" : ""}`}
                    onClick={() => setSettings({ ...settings, responseStyle: "detailed" })}
                  >
                    <input
                      type="radio"
                      name="responseStyle"
                      checked={settings.responseStyle === "detailed"}
                      onChange={() => {}}
                    />
                    <div>
                      <strong>Chuyên sâu & Trích dẫn đầy đủ (Khuyên dùng)</strong>
                      <span>Trích dẫn cụ thể điều, khoản của Luật Đất đai 2024, Nghị định và văn bản hiện hành.</span>
                    </div>
                  </label>

                  <label
                    className={`radio-card ${settings.responseStyle === "concise" ? "selected" : ""}`}
                    onClick={() => setSettings({ ...settings, responseStyle: "concise" })}
                  >
                    <input
                      type="radio"
                      name="responseStyle"
                      checked={settings.responseStyle === "concise"}
                      onChange={() => {}}
                    />
                    <div>
                      <strong>Tóm tắt trọng tâm & Nhanh gọn</strong>
                      <span>Trả lời trực diện các bước thực hiện, cơ quan thụ lý và thời hạn giải quyết.</span>
                    </div>
                  </label>

                  <label
                    className={`radio-card ${settings.responseStyle === "actionable" ? "selected" : ""}`}
                    onClick={() => setSettings({ ...settings, responseStyle: "actionable" })}
                  >
                    <input
                      type="radio"
                      name="responseStyle"
                      checked={settings.responseStyle === "actionable"}
                      onChange={() => {}}
                    />
                    <div>
                      <strong>Kèm Checklist biểu mẫu & Thủ tục từng bước</strong>
                      <span>Liệt kê danh sách giấy tờ cần nộp và cảnh báo các rủi ro pháp lý phổ biến.</span>
                    </div>
                  </label>
                </div>
              </div>
            )}

            {activeTab === "display" && (
              <div className="settings-section">
                <h4>Hiển thị & Tiện ích Không gian làm việc</h4>

                <div className="toggle-row">
                  <div>
                    <strong>Tự động mở Khung Đề xuất bên phải</strong>
                    <span>Hiển thị gợi ý câu hỏi và checklist giấy tờ theo dự án đang làm việc.</span>
                  </div>
                  <label className="switch">
                    <input
                      type="checkbox"
                      checked={settings.autoShowRightPanel}
                      onChange={(e) =>
                        setSettings({ ...settings, autoShowRightPanel: e.target.checked })
                      }
                    />
                    <span className="slider round"></span>
                  </label>
                </div>

                <div className="form-group" style={{ marginTop: "20px" }}>
                  <label>Kích thước cỡ chữ tin nhắn</label>
                  <div className="font-size-options">
                    <button
                      type="button"
                      className={`btn-option ${settings.fontSize === "normal" ? "active" : ""}`}
                      onClick={() => setSettings({ ...settings, fontSize: "normal" })}
                    >
                      Tiêu chuẩn (14.5px)
                    </button>
                    <button
                      type="button"
                      className={`btn-option ${settings.fontSize === "large" ? "active" : ""}`}
                      onClick={() => setSettings({ ...settings, fontSize: "large" })}
                    >
                      Cỡ chữ lớn (16px)
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* Footer buttons */}
            <div className="settings-footer">
              <button type="button" className="secondary-button" onClick={onClose}>
                Hủy
              </button>
              <button type="submit" className="primary-button save-btn">
                {isSaved ? (
                  <>
                    <Check size={16} /> Đã lưu
                  </>
                ) : (
                  <>
                    <Save size={16} /> Lưu tùy chỉnh
                  </>
                )}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
