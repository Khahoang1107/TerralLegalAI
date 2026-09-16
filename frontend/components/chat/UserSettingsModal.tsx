"use client";

import React, { useState, useEffect } from "react";
import {
  X, User, Sliders, MapPin, Sparkles, Check, Monitor, Shield, Save, LogOut, AlertTriangle, KeyRound
} from "lucide-react";
import { authApi } from "@/lib/api";

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
  autoShowRightPanel: false,
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
  userId: string;
  userName: string;
  userEmail: string;
  onSave?: (settings: UserSettings) => void;
  onLogout?: () => void;
}

export default function UserSettingsModal({
  isOpen,
  onClose,
  userId,
  userName,
  userEmail,
  onSave,
  onLogout,
}: UserSettingsModalProps) {
  const [activeTab, setActiveTab] = useState<"profile" | "ai" | "display" | "account">("profile");
  const [settings, setSettings] = useState<UserSettings>(DEFAULT_SETTINGS);
  const [isSaved, setIsSaved] = useState(false);
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordError, setPasswordError] = useState("");
  const [passwordSuccess, setPasswordSuccess] = useState("");
  const [isChangingPassword, setIsChangingPassword] = useState(false);
  const settingsStorageKey = `terra_user_settings:${userId}`;
  const initials = userName.split(" ").map((n) => n[0]).join("").substring(0, 2).toUpperCase();

  useEffect(() => {
    try {
      const saved = localStorage.getItem(settingsStorageKey);
      if (saved) {
        const parsed = JSON.parse(saved);
        setSettings({ ...DEFAULT_SETTINGS, ...parsed, fullName: userName || parsed.fullName, email: userEmail });
      } else {
        setSettings({ ...DEFAULT_SETTINGS, fullName: userName, email: userEmail });
      }
    } catch {
      // fallback to default
    }
    // Reset logout confirm & active tab on every open
    setShowLogoutConfirm(false);
    setActiveTab("profile");
    setCurrentPassword("");
    setNewPassword("");
    setConfirmPassword("");
    setPasswordError("");
    setPasswordSuccess("");
  }, [userName, userEmail, settingsStorageKey, isOpen]);

  if (!isOpen) return null;

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    try {
      localStorage.setItem(settingsStorageKey, JSON.stringify({ ...settings, email: userEmail }));
    } catch (err) {
      console.error(err);
    }
    setIsSaved(true);
    if (onSave) onSave({ ...settings, email: userEmail });
    setTimeout(() => {
      setIsSaved(false);
      onClose();
    }, 600);
  };

  const handleConfirmLogout = () => {
    setShowLogoutConfirm(false);
    onClose();
    if (onLogout) onLogout();
  };

  const handleChangePassword = async () => {
    setPasswordError("");
    setPasswordSuccess("");
    if (!currentPassword || !newPassword || !confirmPassword) {
      setPasswordError("Vui lòng nhập đầy đủ mật khẩu hiện tại, mật khẩu mới và xác nhận mật khẩu mới.");
      return;
    }
    if (newPassword.length < 8) {
      setPasswordError("Mật khẩu mới phải có ít nhất 8 ký tự.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setPasswordError("Xác nhận mật khẩu mới không khớp.");
      return;
    }

    setIsChangingPassword(true);
    try {
      await authApi.changePassword(currentPassword, newPassword);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setPasswordSuccess("Đã đổi mật khẩu thành công.");
    } catch (error: unknown) {
      const detail = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setPasswordError(detail || "Không thể đổi mật khẩu. Vui lòng thử lại.");
    } finally {
      setIsChangingPassword(false);
    }
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

            <button
              type="button"
              className={`settings-nav-item settings-nav-account ${activeTab === "account" ? "active" : ""}`}
              onClick={() => setActiveTab("account")}
            >
              <LogOut size={17} />
              <span>Tài khoản</span>
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
                    value={userEmail}
                    readOnly
                    title="Email tài khoản được quản lý tại hồ sơ đăng nhập"
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

            {activeTab === "account" && (
              <div className="settings-section">
                {/* Account info card */}
                <div className="account-info-card">
                  <div className="account-avatar-lg">
                    <span>{initials}</span>
                  </div>
                  <div className="account-info-text">
                    <strong>{userName}</strong>
                    <span>{userEmail}</span>
                  </div>
                </div>

                <div className="account-divider" />

                <h4>Đổi mật khẩu</h4>
                <p className="form-hint">Mật khẩu mới cần có ít nhất 8 ký tự. Sau khi đổi, bạn vẫn đăng nhập bình thường trên thiết bị này.</p>
                <div className="password-change-fields">
                  <div className="form-group">
                    <label htmlFor="current-password">Mật khẩu hiện tại</label>
                    <input id="current-password" type="password" autoComplete="current-password" value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} />
                  </div>
                  <div className="form-group">
                    <label htmlFor="new-password">Mật khẩu mới</label>
                    <input id="new-password" type="password" autoComplete="new-password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} />
                  </div>
                  <div className="form-group">
                    <label htmlFor="confirm-password">Xác nhận mật khẩu mới</label>
                    <input id="confirm-password" type="password" autoComplete="new-password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} />
                  </div>
                </div>
                {passwordError && <p className="password-change-message error" role="alert">{passwordError}</p>}
                {passwordSuccess && <p className="password-change-message success" role="status">{passwordSuccess}</p>}
                <button type="button" className="change-password-btn" onClick={handleChangePassword} disabled={isChangingPassword}>
                  <KeyRound size={16} />
                  {isChangingPassword ? "Đang đổi mật khẩu..." : "Đổi mật khẩu"}
                </button>

                <div className="account-divider" />

                <h4>Phiên đăng nhập</h4>
                <p className="form-hint">
                  Đăng xuất sẽ kết thúc phiên làm việc hiện tại. Dữ liệu hội thoại và tùy chỉnh của bạn được lưu trữ an toàn và sẽ hiển thị lại khi bạn đăng nhập lại.
                </p>

                {!showLogoutConfirm ? (
                  <button
                    type="button"
                    className="logout-action-btn"
                    onClick={() => setShowLogoutConfirm(true)}
                  >
                    <LogOut size={16} />
                    Đăng xuất khỏi tài khoản
                  </button>
                ) : (
                  <div className="logout-confirm-box">
                    <div className="logout-confirm-icon">
                      <AlertTriangle size={22} />
                    </div>
                    <p className="logout-confirm-text">
                      Bạn có chắc muốn <strong>đăng xuất</strong> khỏi TerraLegalAI không?
                    </p>
                    <div className="logout-confirm-actions">
                      <button
                        type="button"
                        className="secondary-button"
                        onClick={() => setShowLogoutConfirm(false)}
                      >
                        Hủy bỏ
                      </button>
                      <button
                        type="button"
                        className="logout-confirm-yes-btn"
                        onClick={handleConfirmLogout}
                      >
                        <LogOut size={15} />
                        Xác nhận đăng xuất
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Footer buttons — only show save for non-account tabs */}
            {activeTab !== "account" && (
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
            )}
          </form>
        </div>
      </div>
    </div>
  );
}
