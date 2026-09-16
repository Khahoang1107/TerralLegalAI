"use client";

import axios from "axios";
import { useEffect, useState, useRef, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import PdfFormPreview from "@/components/PdfFormPreview";
import FormReviewModal from "@/components/chat/FormReviewModal";
import UsersView from "@/components/admin/UsersView";
import TestsView from "@/components/admin/TestsView";
import { authApi, chatApi, conversationApi, formsApi, documentsApi, evaluationApi, reportsApi, type AuthUser, type Citation, type Conversation, type Document, type TestCase, type EvaluationRun } from "@/lib/api";
import ProjectSidebar, { type LegalProject } from "@/components/chat/ProjectSidebar";
import ProjectAssistantPanel from "@/components/chat/ProjectAssistantPanel";
import UserSettingsModal, { type UserSettings } from "@/components/chat/UserSettingsModal";
import {
  AlertCircle, ArrowRight, BarChart3, BookOpen, Bot, Check, CheckCircle2, ChevronDown, CircleAlert, Clock3,
  ExternalLink, Eye, EyeOff, FileCheck2, FileText, GitBranch, Layers, LayoutDashboard, Lock, LogOut, Mail,
  Maximize2, Menu, MessageSquare, Minimize2, MoreHorizontal, Paperclip, Pencil, Plus, RefreshCw, Save, Scale, Search,
  Send, Settings, ShieldCheck, Sparkles, TestTube2, ThumbsDown, ThumbsUp,
  Trash2, UploadCloud, User, Users, X,
} from "lucide-react";



type Role = "citizen" | "admin";
type AdminView = "overview" | "documents" | "tests" | "reports" | "forms" | "users";

function uniqueCitations(citations: Citation[]) {
  return Array.from(
    new Map(
      citations.map((citation) => [
        `${citation.source_name}|${citation.article ?? ""}|${citation.clause ?? ""}`,
        citation,
      ])
    ).values()
  );
}

function fmtPct(val?: number | null) {
  if (val == null) return "—";
  return `${Math.round(val * 100)}%`;
}

function statusLabel(s: string) {
  if (s === "indexed") return { label: "Hoàn thành", cls: "done", icon: <Check size={13} /> };
  if (s === "indexing") return { label: "Đang xử lý", cls: "processing", icon: <Clock3 size={13} /> };
  if (s === "error") return { label: "Lỗi", cls: "error", icon: <AlertCircle size={13} /> };
  return { label: "Chờ xử lý", cls: "processing", icon: <Clock3 size={13} /> };
}

// ─── Toast ────────────────────────────────────────────────────────
function Toast({ msg, type, onClose }: { msg: string; type: "success" | "error"; onClose: () => void }) {
  useEffect(() => {
    const t = setTimeout(onClose, 3500);
    return () => clearTimeout(t);
  }, [onClose]);
  return (
    <div style={{
      position: "fixed", bottom: 24, right: 24, zIndex: 9999, display: "flex",
      alignItems: "center", gap: 10, padding: "12px 18px",
      background: type === "success" ? "#166b45" : "#a63d3d",
      color: "#fff", borderRadius: 8, boxShadow: "0 4px 24px #0004", fontSize: 14, fontWeight: 600, maxWidth: 340
    }}>
      {type === "success" ? <CheckCircle2 size={16} /> : <AlertCircle size={16} />}
      {msg}
      <button onClick={onClose} style={{ background: "none", border: 0, color: "#fff", marginLeft: 8, cursor: "pointer" }}>
        <X size={15} />
      </button>
    </div>
  );
}

function useToast() {
  const [toast, setToast] = useState<{ msg: string; type: "success" | "error" } | null>(null);
  const show = useCallback((msg: string, type: "success" | "error" = "success") => setToast({ msg, type }), []);
  const hide = useCallback(() => setToast(null), []);
  return { toast, show: show as (msg: string, type?: "success" | "error") => void, hide };
}

// ─── Upload Modal ─────────────────────────────────────────────────
function UploadModal({ onClose, onSuccess, initialFile }: { onClose: () => void; onSuccess: () => void; initialFile?: File | null }) {
  const [file, setFile] = useState<File | null>(initialFile || null);
  const [sourceName, setSourceName] = useState(initialFile ? initialFile.name.replace(/\.[^/.]+$/, "") : "");
  const [groupType, setGroupType] = useState("quyet_dinh");
  const [procedureType, setProcedureType] = useState("all");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const f = e.dataTransfer.files[0];
    if (f) setFile(f);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file || !sourceName.trim()) { setError("Vui lòng chọn file và nhập tên nguồn."); return; }
    setLoading(true); setError("");
    try {
      await documentsApi.uploadDocument(file, sourceName.trim(), groupType, procedureType);
      onSuccess(); onClose();
    } catch (err) {
      const detail = axios.isAxiosError(err) ? err.response?.data?.detail : null;
      setError(typeof detail === "string" ? detail : "Tải lên thất bại, vui lòng thử lại.");
    } finally { setLoading(false); }
  };

  return (
    <div className="dialog-backdrop" onClick={onClose}>
      <form className="rename-dialog" style={{ maxWidth: 480, width: "95%" }} onSubmit={handleSubmit} onClick={(e) => e.stopPropagation()}>
        <div className="dialog-head">
          <h2>Tải tài liệu lên</h2>
          <button type="button" className="icon-button" onClick={onClose}><X size={18} /></button>
        </div>
        <div className="upload-zone" style={{ padding: "1.5rem", marginBottom: "1rem", cursor: "pointer" }}
          onDragOver={(e) => e.preventDefault()} onDrop={handleDrop} onClick={() => fileInputRef.current?.click()}>
          <UploadCloud size={24} />
          <div>
            <strong>{file ? file.name : "Kéo thả PDF / DOCX vào đây"}</strong>
            <span>{file ? `${(file.size / 1024 / 1024).toFixed(1)} MB` : "hoặc bấm để chọn file"}</span>
          </div>
          <input ref={fileInputRef} type="file" accept=".pdf,.docx,.doc" style={{ display: "none" }} onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        </div>
        <label style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 13, fontWeight: 600, marginBottom: 12 }}>
          Tên nguồn tài liệu *
          <input value={sourceName} onChange={(e) => setSourceName(e.target.value)} placeholder="VD: QĐ 1085/QĐ-UBND" required style={{ border: "1px solid #cfd7d1", padding: "10px 12px", borderRadius: 6, fontSize: 14 }} />
        </label>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 12 }}>
          <label style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 13, fontWeight: 600 }}>
            Nhóm tài liệu
            <select value={groupType} onChange={(e) => setGroupType(e.target.value)} className="compact-select" style={{ height: 40 }}>
              <option value="quyet_dinh">Quyết định</option>
              <option value="luat">Luật / Nghị định</option>
              <option value="bieu_mau">Biểu mẫu</option>
              <option value="faq">FAQ</option>
            </select>
          </label>
          <label style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 13, fontWeight: 600 }}>
            Thủ tục áp dụng
            <select value={procedureType} onChange={(e) => setProcedureType(e.target.value)} className="compact-select" style={{ height: 40 }}>
              <option value="all">Tất cả</option>
              <option value="chuyen_nhuong">Chuyển nhượng</option>
              <option value="cap_doi">Cấp đổi GCN</option>
              <option value="tang_cho">Tặng cho</option>
            </select>
          </label>
        </div>
        {error && <div className="login-error" style={{ marginBottom: 12 }}><AlertCircle size={15} /> {error}</div>}
        <div className="dialog-actions">
          <button type="button" className="secondary-button" onClick={onClose}>Hủy</button>
          <button type="submit" className="primary-button" disabled={loading}>{loading ? "Đang tải lên..." : "Tải lên"}</button>
        </div>
      </form>
    </div>
  );
}

function Login({ onLogin, onRegister }: { onLogin: (role: Role) => void; onRegister: () => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [remember, setRemember] = useState(true);
  const [loading, setLoading] = useState(false);

  const handleLogin = async () => {
    setLoading(true);
    setError("");
    try {
      const result = await authApi.login(email.trim(), password, remember);
      onLogin(result.user.role);
    } catch (err) {
      const detail = axios.isAxiosError(err) ? err.response?.data?.detail : null;
      setError(
        typeof detail === "string" ? detail :
        (Array.isArray(detail) && detail[0]?.msg) ? detail[0].msg : "Không thể đăng nhập."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="login-page">
      <section className="login-intro">
        <div className="login-intro-glow glow-1" />
        <div className="login-intro-glow glow-2" />
        <div className="login-intro-grid" />

        <div className="intro-top">
          <div className="brand-header">
            <div className="brand-mark-glow">
              <BookOpen size={24} />
            </div>
            <div>
              <div className="brand-title">TerraLegalAI</div>
              <div className="brand-badge">Hệ thống Pháp lý Đất đai</div>
            </div>
          </div>
        </div>

        <div className="intro-copy">
          <div className="intro-pill">
            <Sparkles size={13} />
            <span>NỀN TẢNG THÔNG TIN PHÁP LÝ SỐ</span>
          </div>
          <h1>Tra cứu thủ tục rõ ràng,<br /><span className="text-highlight">chuẩn xác đúng nguồn.</span></h1>
          <p>Hỗ trợ người dân và cán bộ tiếp cận nhanh chóng quy trình, hồ sơ mẫu và căn cứ pháp lý từ tài liệu chính thức của cơ quan nhà nước.</p>
          
          <div className="trust-cards">
            <div className="trust-card">
              <div className="trust-card-icon"><ShieldCheck size={20} /></div>
              <div className="trust-card-content">
                <strong>Trích dẫn theo văn bản gốc</strong>
                <span>Đối chiếu trực tiếp từng điều, khoản trong Luật & Nghị định</span>
              </div>
            </div>
            <div className="trust-card">
              <div className="trust-card-icon"><FileCheck2 size={20} /></div>
              <div className="trust-card-content">
                <strong>Theo dõi hiệu lực tài liệu</strong>
                <span>Cập nhật quyết định từ UBND tỉnh & Bộ Nông nghiệp và Môi trường</span>
              </div>
            </div>
            <div className="trust-card">
              <div className="trust-card-icon"><Clock3 size={20} /></div>
              <div className="trust-card-content">
                <strong>Hỗ trợ tra cứu 24/7</strong>
                <span>Hỗ trợ điền mẫu hồ sơ và rà soát điều kiện pháp lý tức thì</span>
              </div>
            </div>
          </div>
        </div>

        <div className="intro-foot">
          <span>© 2026 TerraLegalAI • Dữ liệu chuẩn hóa theo Luật Đất đai mới nhất</span>
        </div>
      </section>

      <section className="login-panel">
        <div className="login-card">
          <div className="mobile-brand">
            <div className="brand-mark-glow small"><BookOpen size={20} /></div>
            <strong>TerraLegalAI</strong>
          </div>

          <div className="login-header">
            <span className="eyebrow">Cổng đăng nhập hệ thống</span>
            <h2>Chào mừng bạn quay lại</h2>
            <p>Nhập thông tin tài khoản được cấp để tiếp tục.</p>
          </div>

          <form className="login-form" onSubmit={(e) => { e.preventDefault(); handleLogin(); }}>
            <div className="field-group">
              <label htmlFor="login-email">Email hoặc tên đăng nhập</label>
              <div className="input-affix-wrapper">
                <span className="input-prefix"><User size={18} /></span>
                <input
                  id="login-email"
                  value={email}
                  onChange={(e) => { setEmail(e.target.value); setError(""); }}
                  autoComplete="username"
                  placeholder="Nhập email hoặc tên đăng nhập"
                  required
                />
              </div>
            </div>

            <div className="field-group">
              <div className="label-with-link">
                <label htmlFor="login-pass">Mật khẩu</label>
                <button type="button" className="text-button text-xs">Quên mật khẩu?</button>
              </div>
              <div className="input-affix-wrapper">
                <span className="input-prefix"><Lock size={18} /></span>
                <input
                  id="login-pass"
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => { setPassword(e.target.value); setError(""); }}
                  autoComplete="current-password"
                  placeholder="Nhập mật khẩu"
                  required
                />
                <button
                  type="button"
                  className="input-suffix-btn"
                  onClick={() => setShowPassword(!showPassword)}
                  tabIndex={-1}
                  title={showPassword ? "Ẩn mật khẩu" : "Hiện mật khẩu"}
                >
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>

            {error && (
              <div className="login-error" role="alert">
                <CircleAlert size={16} />
                <span>{error}</span>
              </div>
            )}

            <div className="form-row">
              <label className="check-label">
                <input
                  type="checkbox"
                  checked={remember}
                  onChange={(e) => setRemember(e.target.checked)}
                />
                <span>Ghi nhớ đăng nhập</span>
              </label>
            </div>

            <button className="primary-button submit-btn" type="submit" disabled={loading}>
              <span>{loading ? "Đang xử lý đăng nhập..." : "Đăng nhập hệ thống"}</span>
              {!loading && <ArrowRight size={17} />}
            </button>

            <div className="auth-divider">
              <span>hoặc</span>
            </div>

            <p className="auth-switch">
              Bạn chưa có tài khoản?{" "}
              <button type="button" className="text-button strong-link" onClick={onRegister}>
                Đăng ký tài khoản mới
              </button>
            </p>
          </form>

          <div className="panel-subfooter">
            <ShieldCheck size={14} />
            <span>Kết nối bảo mật mã hóa SSL 256-bit</span>
          </div>
        </div>
      </section>
    </main>
  );
}

function Register({ onBack, onRegister }: { onBack: () => void; onRegister: (role: Role) => void }) {
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmation, setShowConfirmation] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleRegister = async () => {
    if (password !== confirmation) {
      setError("Mật khẩu xác nhận không khớp.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const result = await authApi.register(fullName.trim(), email.trim(), password);
      onRegister(result.user.role);
    } catch (err) {
      const detail = axios.isAxiosError(err) ? err.response?.data?.detail : null;
      setError(
        typeof detail === "string" ? detail :
        (Array.isArray(detail) && detail[0]?.msg) ? detail[0].msg : "Không thể tạo tài khoản."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="login-page">
      <section className="login-intro">
        <div className="login-intro-glow glow-1" />
        <div className="login-intro-glow glow-2" />
        <div className="login-intro-grid" />

        <div className="intro-top">
          <div className="brand-header">
            <div className="brand-mark-glow">
              <BookOpen size={24} />
            </div>
            <div>
              <div className="brand-title">TerraLegalAI</div>
              <div className="brand-badge">Hệ thống Pháp lý Đất đai</div>
            </div>
          </div>
        </div>

        <div className="intro-copy">
          <div className="intro-pill">
            <Sparkles size={13} />
            <span>KHỞI TẠO TÀI KHOẢN MỚI</span>
          </div>
          <h1>Tra cứu thủ tục rõ ràng,<br /><span className="text-highlight">chuẩn xác đúng nguồn.</span></h1>
          <p>Tạo tài khoản cá nhân để lưu trữ toàn bộ lịch sử tư vấn, tải biểu mẫu đã điền và theo dõi văn bản pháp lý quan tâm.</p>
          
          <div className="trust-cards">
            <div className="trust-card">
              <div className="trust-card-icon"><ShieldCheck size={20} /></div>
              <div className="trust-card-content">
                <strong>Lưu trữ an toàn</strong>
                <span>Dữ liệu hồ sơ và lịch sử tra cứu được bảo mật tuyệt đối</span>
              </div>
            </div>
            <div className="trust-card">
              <div className="trust-card-icon"><FileCheck2 size={20} /></div>
              <div className="trust-card-content">
                <strong>Quản lý biểu mẫu</strong>
                <span>Xem lại và chỉnh sửa trực tiếp các đơn xin cấp đổi, chuyển nhượng</span>
              </div>
            </div>
            <div className="trust-card">
              <div className="trust-card-icon"><Clock3 size={20} /></div>
              <div className="trust-card-content">
                <strong>Đồng bộ đa thiết bị</strong>
                <span>Tiếp tục phiên làm việc trên máy tính hoặc điện thoại</span>
              </div>
            </div>
          </div>
        </div>

        <div className="intro-foot">
          <span>© 2026 TerraLegalAI • Dữ liệu chuẩn hóa theo Luật Đất đai mới nhất</span>
        </div>
      </section>

      <section className="login-panel">
        <div className="login-card">
          <div className="mobile-brand">
            <div className="brand-mark-glow small"><BookOpen size={20} /></div>
            <strong>TerraLegalAI</strong>
          </div>

          <div className="login-header">
            <span className="eyebrow">Đăng ký tài khoản</span>
            <h2>Tạo tài khoản mới</h2>
            <p>Điền thông tin bên dưới để bắt đầu sử dụng hệ thống.</p>
          </div>

          <form className="login-form" onSubmit={(e) => { e.preventDefault(); handleRegister(); }}>
            <div className="field-group">
              <label htmlFor="reg-name">Họ và tên</label>
              <div className="input-affix-wrapper">
                <span className="input-prefix"><User size={18} /></span>
                <input
                  id="reg-name"
                  value={fullName}
                  onChange={(e) => { setFullName(e.target.value); setError(""); }}
                  autoComplete="name"
                  placeholder="Ví dụ: Nguyễn Văn A"
                  required
                  minLength={2}
                />
              </div>
            </div>

            <div className="field-group">
              <label htmlFor="reg-email">Địa chỉ Email</label>
              <div className="input-affix-wrapper">
                <span className="input-prefix"><Mail size={18} /></span>
                <input
                  id="reg-email"
                  type="email"
                  value={email}
                  onChange={(e) => { setEmail(e.target.value); setError(""); }}
                  autoComplete="email"
                  placeholder="name@example.com"
                  required
                />
              </div>
            </div>

            <div className="field-group">
              <label htmlFor="reg-pass">Mật khẩu</label>
              <div className="input-affix-wrapper">
                <span className="input-prefix"><Lock size={18} /></span>
                <input
                  id="reg-pass"
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => { setPassword(e.target.value); setError(""); }}
                  autoComplete="new-password"
                  placeholder="Tối thiểu 8 ký tự"
                  required
                  minLength={8}
                />
                <button
                  type="button"
                  className="input-suffix-btn"
                  onClick={() => setShowPassword(!showPassword)}
                  tabIndex={-1}
                  title={showPassword ? "Ẩn mật khẩu" : "Hiện mật khẩu"}
                >
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>

            <div className="field-group">
              <label htmlFor="reg-confirm">Xác nhận mật khẩu</label>
              <div className="input-affix-wrapper">
                <span className="input-prefix"><Lock size={18} /></span>
                <input
                  id="reg-confirm"
                  type={showConfirmation ? "text" : "password"}
                  value={confirmation}
                  onChange={(e) => { setConfirmation(e.target.value); setError(""); }}
                  autoComplete="new-password"
                  placeholder="Nhập lại mật khẩu"
                  required
                  minLength={8}
                />
                <button
                  type="button"
                  className="input-suffix-btn"
                  onClick={() => setShowConfirmation(!showConfirmation)}
                  tabIndex={-1}
                  title={showConfirmation ? "Ẩn mật khẩu" : "Hiện mật khẩu"}
                >
                  {showConfirmation ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>

            {error && (
              <div className="login-error" role="alert">
                <CircleAlert size={16} />
                <span>{error}</span>
              </div>
            )}

            <button className="primary-button submit-btn" type="submit" disabled={loading}>
              <span>{loading ? "Đang tạo tài khoản..." : "Hoàn tất đăng ký"}</span>
              {!loading && <ArrowRight size={17} />}
            </button>

            <div className="auth-divider">
              <span>hoặc</span>
            </div>

            <p className="auth-switch">
              Bạn đã có tài khoản?{" "}
              <button type="button" className="text-button strong-link" onClick={onBack}>
                Đăng nhập ngay
              </button>
            </p>
          </form>

          <div className="panel-subfooter">
            <ShieldCheck size={14} />
            <span>Kết nối bảo mật mã hóa SSL 256-bit</span>
          </div>
        </div>
      </section>
    </main>
  );
}

function AppHeader({
  role,
  userName = "Người dùng",
  onLogout,
  onMenu,
  onOpenSettings,
  activeProjectName,
  isRightPanelOpen,
  onToggleRightPanel,
}: {
  role: Role;
  userName?: string;
  onLogout: () => void;
  onMenu: () => void;
  onOpenSettings?: () => void;
  activeProjectName?: string;
  isRightPanelOpen?: boolean;
  onToggleRightPanel?: () => void;
}) {
  const initials = userName.split(" ").map(n => n[0]).join("").substring(0, 2).toUpperCase();
  const [profileOpen, setProfileOpen] = useState(false);
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false);
  const profileRef = useRef<HTMLDivElement>(null);
  const hoverTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    if (!profileOpen) return;
    const handler = (e: MouseEvent) => {
      if (profileRef.current && !profileRef.current.contains(e.target as Node)) {
        setProfileOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [profileOpen]);

  const handleMouseEnter = () => {
    if (hoverTimeoutRef.current) clearTimeout(hoverTimeoutRef.current);
    setProfileOpen(true);
  };

  const handleMouseLeave = () => {
    hoverTimeoutRef.current = setTimeout(() => {
      setProfileOpen(false);
    }, 250);
  };

  return (
    <>
      <header className="app-header modern-header">
        <div className="header-brand">
          <button type="button" className="icon-button mobile-only" onClick={onMenu} title="Mở danh mục">
            <Menu size={20} />
          </button>
          <div className="brand-mark-modern">
            <Scale size={20} className="brand-icon-gold" />
          </div>
          <div className="brand-text-block">
            <div className="brand-title-row">
              <strong>TerraLegalAI</strong>
              <span className="brand-badge-version">v2.0</span>
            </div>
            <span className="brand-subtitle hide-sm">Trợ lý Pháp lý & Đất đai Chuyên sâu</span>
          </div>
          <span className="role-badge-modern">{role === "admin" ? "Quản trị viên" : "Hồ sơ Công dân"}</span>

          {activeProjectName && (
            <div className="header-active-project-tag hide-sm" title={`Dự án đang mở: ${activeProjectName}`}>
              <Layers size={13} />
              <span>{activeProjectName}</span>
            </div>
          )}
        </div>

        <div className="header-actions">
          {onToggleRightPanel && (
            <button
              type="button"
              className={`panel-toggle-btn ${isRightPanelOpen ? "active" : ""}`}
              onClick={onToggleRightPanel}
              title={isRightPanelOpen ? "Thu gọn Trợ lý Dự án & Đề xuất" : "Hiện Trợ lý Dự án & Đề xuất"}
            >
              <Sparkles size={15} />
              <span className="hide-sm">{isRightPanelOpen ? "Thu gọn Trợ lý" : "Trợ lý Dự án"}</span>
            </button>
          )}

          <div
            className="profile-dropdown-wrap"
            ref={profileRef}
            onMouseEnter={handleMouseEnter}
            onMouseLeave={handleMouseLeave}
          >
            <button
              type="button"
              className={`profile-button-enhanced ${profileOpen ? "active" : ""}`}
              onClick={() => setProfileOpen(prev => !prev)}
              aria-haspopup="true"
              aria-expanded={profileOpen}
              title="Nhấp hoặc rê chuột để mở Tùy chỉnh & Đăng xuất"
            >
              <span className="avatar-ring">
                <span className="avatar-text">{initials}</span>
              </span>
              <div className="profile-name-col hide-sm">
                <span className="profile-name">{userName}</span>
                <span className="profile-hint">Tùy chỉnh & Cài đặt</span>
              </div>
              <ChevronDown size={14} className={`profile-chevron ${profileOpen ? "open" : ""}`} />
            </button>

            {profileOpen && (
              <div className="profile-dropdown-menu" role="menu">
                <div className="profile-dropdown-user">
                  <span className="pdrop-avatar">{initials}</span>
                  <div className="pdrop-info">
                    <strong>{userName}</strong>
                    <span>{role === "admin" ? "Quản trị viên" : "Hồ sơ Công dân"}</span>
                  </div>
                </div>
                <div className="profile-dropdown-divider" />
                <button
                  type="button"
                  className="profile-dropdown-item"
                  role="menuitem"
                  onClick={() => {
                    setProfileOpen(false);
                    if (onOpenSettings) onOpenSettings();
                  }}
                >
                  <Settings size={15} />
                  <span>Cài đặt & Tùy chỉnh</span>
                </button>
                <div className="profile-dropdown-divider" />
                <button
                  type="button"
                  className="profile-dropdown-item profile-dropdown-logout"
                  role="menuitem"
                  onClick={() => {
                    setProfileOpen(false);
                    setShowLogoutConfirm(true);
                  }}
                >
                  <LogOut size={15} />
                  <span>Đăng xuất</span>
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Modal xác nhận đăng xuất khi bấm từ dropdown */}
      {showLogoutConfirm && (
        <div className="dialog-backdrop" onClick={() => setShowLogoutConfirm(false)}>
          <div className="confirm-modal-box" onClick={(e) => e.stopPropagation()}>
            <div className="confirm-modal-icon logout-icon">
              <AlertCircle size={28} />
            </div>
            <h3>Xác nhận đăng xuất</h3>
            <p>Bạn có chắc chắn muốn đăng xuất khỏi hệ thống <strong>TerraLegalAI</strong>?</p>
            <div className="confirm-modal-actions">
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
                onClick={() => {
                  setShowLogoutConfirm(false);
                  onLogout();
                }}
              >
                <LogOut size={15} />
                Đăng xuất
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function UserPortal({ userId, userName, userEmail, onLogout }: { userId: string; userName: string; userEmail: string; onLogout: () => void }) {
  const [sidebar, setSidebar] = useState(false);
  const [feedback, setFeedback] = useState<"up" | "down" | null>(null);
  const [conversationsList, setConversationsList] = useState<Conversation[]>([]);
  const [currentConversationId, setCurrentConversationId] = useState<string | null>(null);
  const [renamingConversation, setRenamingConversation] = useState<Conversation | null>(null);
  const [renameTitle, setRenameTitle] = useState("");
  const [conversationActionLoading, setConversationActionLoading] = useState(false);
  const [messages, setMessages] = useState<Array<{role: "user" | "ai", text: string, time: string, citations?: Citation[], form_completed?: boolean, form_id?: string, collected_data?: Record<string, string>}>>([]);
  const [reviewingForm, setReviewingForm] = useState<{form_id: string, collected_data: Record<string, string>} | null>(null);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  // Project and Right Panel States
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  // The project assistant is opt-in: keep it closed until the user opens it.
  const [isRightPanelOpen, setIsRightPanelOpen] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [userSettings, setUserSettings] = useState<UserSettings>({
    fullName: userName,
    email: userEmail,
    region: "TP. Hồ Chí Minh",
    responseStyle: "detailed",
    autoShowRightPanel: false,
    fontSize: "normal",
  });
  
  const bottomRef = useRef<HTMLDivElement>(null);

  // Load user settings
  useEffect(() => {
    try {
      const saved = localStorage.getItem(`terra_user_settings:${userId}`);
      if (saved) {
        const parsed = JSON.parse(saved);
        // Ignore the legacy auto-open preference. Suggestions should only be
        // displayed after an explicit click in the current session.
        setUserSettings(prev => ({ ...prev, ...parsed, autoShowRightPanel: false }));
      }
    } catch (e) {
      console.error(e);
    }
  }, [userId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    conversationApi.getConversations().then(data => {
      setConversationsList(data);
    }).catch(console.error);
  }, []);

  // Find active project object
  const [currentProject, setCurrentProject] = useState<LegalProject | null>(null);
  useEffect(() => {
    try {
      const saved = localStorage.getItem(`terra_legal_projects:${userId}`);
      if (saved) {
        const parsed: LegalProject[] = JSON.parse(saved);
        const found = parsed.find(p => p.id === selectedProjectId) || null;
        setCurrentProject(found);
      }
    } catch {
      setCurrentProject(null);
    }
  }, [selectedProjectId, userId]);

  const handleSelectConversation = async (id: string) => {
    try {
      const detail = await conversationApi.getConversation(id);
      setCurrentConversationId(detail.id);
      
      // Check if this conversation has a completed form
      const formState = (detail as any).form_state;
      const isFormComplete = formState?.is_complete === true;
      const formId = formState?.active_form_id;
      const collectedData = formState?.collected_data || {};
      
      const mappedMessages = detail.messages.map((m, idx, arr) => {
        let lastAssistantIdx = -1;
        for (let i = arr.length - 1; i >= 0; i--) {
          if (arr[i].role === 'assistant') { lastAssistantIdx = i; break; }
        }
        const isLastAssistantMsg = m.role === 'assistant' && idx === lastAssistantIdx;
        return {
          role: m.role as "user" | "ai",
          text: m.content,
          time: new Date(m.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          citations: m.citations,
          form_completed: (isLastAssistantMsg && isFormComplete) ? true : (m as any).form_completed,
          form_id: (isLastAssistantMsg && isFormComplete) ? formId : (m as any).form_id,
          collected_data: (isLastAssistantMsg && isFormComplete) ? collectedData : (m as any).collected_data,
        };
      });
      
      setMessages(mappedMessages);
      setSidebar(false);
    } catch (err) {
      console.error(err);
    }
  };

  const handleNewChat = () => {
    setCurrentConversationId(null);
    setMessages([]);
    setSidebar(false);
  };

  const openRenameConversation = (conversation: Conversation) => {
    setRenamingConversation(conversation);
    setRenameTitle(conversation.title);
  };

  const handleRenameConversation = async (e: React.FormEvent) => {
    e.preventDefault();
    const title = renameTitle.trim();
    if (!renamingConversation || !title || conversationActionLoading) return;

    setConversationActionLoading(true);
    try {
      const updated = await conversationApi.updateConversation(renamingConversation.id, title);
      setConversationsList((items) => items.map((item) => item.id === updated.id ? updated : item));
      setRenamingConversation(null);
    } catch (err) {
      console.error(err);
      window.alert("Không thể đổi tên cuộc trò chuyện. Vui lòng thử lại.");
    } finally {
      setConversationActionLoading(false);
    }
  };

  const handleDeleteConversation = async (conversation: Conversation) => {
    if (!window.confirm(`Xóa cuộc trò chuyện "${conversation.title}"?`)) return;

    try {
      await conversationApi.deleteConversation(conversation.id);
    } catch (err) {
      if (!axios.isAxiosError(err) || err.response?.status !== 404) {
        window.alert("Không thể xóa cuộc trò chuyện. Vui lòng thử lại.");
        return;
      }
    }

    setConversationsList((items) => items.filter((item) => item.id !== conversation.id));
    if (currentConversationId === conversation.id) {
      handleNewChat();
    }
  };

  const handleSend = async (e?: React.FormEvent, customQuestion?: string) => {
    e?.preventDefault();
    const textToSend = (customQuestion !== undefined ? customQuestion : input).trim();
    if (!textToSend || loading) return;
    
    setInput("");
    
    const now = new Date();
    const timeString = `${now.getHours().toString().padStart(2, "0")}:${now.getMinutes().toString().padStart(2, "0")}`;
    
    setMessages(prev => [...prev, { role: "user", text: textToSend, time: timeString }]);
    setLoading(true);
    
    try {
      const response = await chatApi.sendMessage({
        question: textToSend,
        procedure_filter: currentProject?.procedure_type !== "all" ? currentProject?.procedure_type : undefined,
        conversation_id: currentConversationId || undefined,
      });
      
      if (!currentConversationId && response.conversation_id) {
        setCurrentConversationId(response.conversation_id);
      }
      
      setMessages(prev => [...prev, { 
        role: "ai", 
        text: response.answer, 
        time: timeString,
        citations: response.citations,
        form_completed: response.form_completed,
        form_id: response.form_id,
        collected_data: response.collected_data
      }]);
      
      if (response.form_completed && response.form_id) {
        setReviewingForm({ form_id: response.form_id, collected_data: response.collected_data || {} });
      }
    } catch (err) {
      console.error(err);
      setMessages(prev => [...prev, { 
        role: "ai", 
        text: "Xin lỗi, đã có lỗi xảy ra khi kết nối với máy chủ. Vui lòng thử lại sau.", 
        time: timeString 
      }]);
    } finally {
      conversationApi.getConversations().then(setConversationsList).catch(console.error);
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className={`app-shell ${userSettings.fontSize === "large" ? "text-large-mode" : ""}`}>
      <AppHeader
        role="citizen"
        userName={userSettings.fullName || userName}
        onLogout={onLogout}
        onMenu={() => setSidebar(true)}
        onOpenSettings={() => setIsSettingsOpen(true)}
        activeProjectName={currentProject?.name}
        isRightPanelOpen={isRightPanelOpen}
        onToggleRightPanel={() => setIsRightPanelOpen(!isRightPanelOpen)}
      />

      <div className={`workspace workspace-three-col ${!isRightPanelOpen ? "right-collapsed" : ""}`}>
        {/* Left Sidebar: Projects and Conversations with scroll */}
        <ProjectSidebar
          userId={userId}
          isOpen={sidebar}
          onClose={() => setSidebar(false)}
          conversationsList={conversationsList}
          currentConversationId={currentConversationId}
          onSelectConversation={handleSelectConversation}
          onNewChat={handleNewChat}
          onOpenRename={openRenameConversation}
          onDeleteConversation={handleDeleteConversation}
          selectedProjectId={selectedProjectId}
          onSelectProject={(id) => setSelectedProjectId(id)}
        />
        {sidebar && <button type="button" className="overlay" onClick={() => setSidebar(false)} />}

        {/* Central Main Chat Area */}
        <main className="chat-main">
          <div className="chat-toolbar">
            <div className="toolbar-left">
              <h1>
                {currentProject ? currentProject.name : "Tra cứu & Tư vấn thủ tục đất đai"}
              </h1>
              <p>
                {currentProject
                  ? `Đang áp dụng đối chiếu theo quy chuẩn hồ sơ: ${currentProject.name}`
                  : "Thông tin được đối chiếu từ Luật Đất đai 2024 & Nghị định hướng dẫn"}
              </p>
            </div>

            <div className="toolbar-right">
              {currentProject && (
                <button
                  type="button"
                  className="toolbar-project-chat-btn"
                  onClick={() => handleNewChat()}
                  title={`Tạo cuộc trò chuyện mới cho dự án: ${currentProject.name}`}
                >
                  <Plus size={14} />
                  <span>Chat mới trong dự án</span>
                </button>
              )}
            </div>
          </div>

          <div className="message-stream custom-scrollbar">
            <div className="date-divider"><span>Hôm nay</span></div>
            
            {messages.length === 0 ? (
              <div className="welcome-hero-container">
                <div className="welcome-badge-icon">
                  <Scale size={28} />
                </div>
                <h2>Chào mừng bạn đến với TerraLegalAI</h2>
                <p>
                  Trợ lý pháp lý thông minh hỗ trợ giải đáp quy trình, thành phần hồ sơ và tính nghĩa vụ tài chính đất đai chuẩn xác.
                </p>

                {/* Prompt Cards Grid */}
                <div className="prompt-cards-grid">
                  <button
                    type="button"
                    className="prompt-card"
                    onClick={() => handleSend(undefined, "Thành phần hồ sơ đăng ký sang tên chuyển nhượng đất gồm những giấy tờ gì?")}
                  >
                    <div className="prompt-card-icon"><FileCheck2 size={20} /></div>
                    <div className="prompt-card-text">
                      <strong>Hồ sơ sang tên Sổ đỏ</strong>
                      <span>Thành phần giấy tờ bắt buộc theo Nghị định 101/2024</span>
                    </div>
                  </button>

                  <button
                    type="button"
                    className="prompt-card"
                    onClick={() => handleSend(undefined, "Cách tính Thuế TNCN 2% và Lệ phí trước bạ 0.5% khi chuyển nhượng bất động sản?")}
                  >
                    <div className="prompt-card-icon"><Sparkles size={20} /></div>
                    <div className="prompt-card-text">
                      <strong>Nghĩa vụ tài chính</strong>
                      <span>Công thức tính thuế TNCN, lệ phí trước bạ và trường hợp miễn giảm</span>
                    </div>
                  </button>

                  <button
                    type="button"
                    className="prompt-card"
                    onClick={() => handleSend(undefined, "Điều kiện và thủ tục cấp đổi Sổ đỏ sang mẫu mới theo Luật Đất đai 2024?")}
                  >
                    <div className="prompt-card-icon"><BookOpen size={20} /></div>
                    <div className="prompt-card-text">
                      <strong>Cấp đổi Sổ đỏ mới</strong>
                      <span>Trình tự đổi phôi Giấy chứng nhận mẫu mới thống nhất</span>
                    </div>
                  </button>

                  <button
                    type="button"
                    className="prompt-card"
                    onClick={() => handleSend(undefined, "Quy định về thời hạn giải quyết và cơ quan tiếp nhận hồ sơ đất đai?")}
                  >
                    <div className="prompt-card-icon"><Clock3 size={20} /></div>
                    <div className="prompt-card-text">
                      <strong>Thời hạn & Thẩm quyền</strong>
                      <span>Chi nhánh Văn phòng Đăng ký đất đai & Bộ phận Một cửa</span>
                    </div>
                  </button>
                </div>
              </div>
            ) : (
              messages.map((msg, idx) => (
                <article key={idx} className={`message-row ${msg.role === "user" ? "user-message" : "ai-message"}`}>
                  <div className={`message-avatar ${msg.role}`} >
                    {msg.role === "user" ? <User size={17} /> : <Bot size={18} />}
                  </div>
                  <div className={msg.role === "user" ? "bubble" : "answer-block"}>
                    {msg.role === "ai" && <div className="answer-label"><Sparkles size={15} /> TerraLegalAI Trợ lý</div>}
                    {msg.role === "user" ? (
                      <div style={{ whiteSpace: "pre-wrap" }}>{msg.text}</div>
                    ) : (
                      <div className="markdown-content">
                        <ReactMarkdown>{msg.text}</ReactMarkdown>
                      </div>
                    )}
                    
                    {msg.citations && msg.citations.length > 0 && (
                      <div className="citations-list" style={{ marginTop: "1rem" }}>
                        <p className="citations-heading">Cơ sở pháp lý đối chiếu</p>
                        {uniqueCitations(msg.citations).map((cit, cidx) => (
                          <div key={cidx} className="citation-box">
                            <div>
                              <FileText size={18} />
                              <span>
                                <strong>{cit.source_name}</strong>
                                <small>{cit.article ? `${cit.article}` : ''} {cit.clause ? `${cit.clause}` : ''}</small>
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                    
                    {msg.role === "ai" && (
                      <div className="answer-actions">
                        <span>Câu trả lời này có hữu ích?</span>
                        <button type="button" className={feedback === "up" ? "selected" : ""} onClick={() => setFeedback("up")} title="Hữu ích"><ThumbsUp size={16} /></button>
                        <button type="button" className={feedback === "down" ? "selected negative" : ""} onClick={() => setFeedback("down")} title="Chưa hữu ích"><ThumbsDown size={16} /></button>
                        <span className="answer-time">{msg.time}</span>
                      </div>
                    )}
                    {msg.form_completed && msg.form_id && (
                      <div style={{ marginTop: "16px" }}>
                        <button 
                          type="button"
                          className="primary-button" 
                          onClick={() => setReviewingForm({ form_id: msg.form_id!, collected_data: msg.collected_data || {} })}
                          style={{ display: "inline-flex", alignItems: "center", gap: 8, padding: "10px 16px", borderRadius: 8 }}
                        >
                          <FileCheck2 size={18} /> Xem & Chỉnh sửa biểu mẫu
                        </button>
                      </div>
                    )}
                    {msg.role === "user" && <time>{msg.time}</time>}
                  </div>
                </article>
              ))
            )}
            
            {loading && (
              <article className="message-row ai-message">
                <div className="message-avatar ai"><Bot size={18} /></div>
                <div className="answer-block">
                   <div className="answer-label pulse-glow"><Sparkles size={15} /> TerraLegalAI đang tra cứu cơ sở dữ liệu pháp luật...</div>
                </div>
              </article>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Composer Input Area */}
          <div className="composer-area">
            {messages.length > 0 && (
              <div className="quick-suggestions-bar">
                <button type="button" onClick={() => handleSend(undefined, "Thời hạn giải quyết là bao lâu?")}>Thời hạn giải quyết?</button>
                <button type="button" onClick={() => handleSend(undefined, "Nộp hồ sơ ở cơ quan nào?")}>Nộp hồ sơ ở đâu?</button>
                <button type="button" onClick={() => handleSend(undefined, "Mức phí và lệ phí nhà nước?")}>Lệ phí cấp đổi thế nào?</button>
              </div>
            )}
            <form className="composer modern-composer" onSubmit={(e) => handleSend(e)}>
              <button type="button" className="icon-button attach-btn" title="Đính kèm tài liệu tham khảo"><Paperclip size={18} /></button>
              <textarea 
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={currentProject ? `Đặt câu hỏi cho ${currentProject.name}...` : "Hỏi về quy trình, thành phần hồ sơ, lệ phí đất đai..."}
                rows={1} 
                disabled={loading}
              />
              <button type="submit" className="send-button modern-send" title="Gửi câu hỏi" disabled={!input.trim() || loading}>
                <Send size={18} />
              </button>
            </form>
            <p className="legal-disclaimer">Thông tin mang tính tham khảo đối chiếu từ văn bản pháp quy. Vui lòng kiểm tra lại với cơ quan có thẩm quyền tại địa phương.</p>
          </div>
        </main>

        {/* Right Assistant Panel: Contextual suggestions by project */}
        <ProjectAssistantPanel
          isOpen={isRightPanelOpen}
          onClose={() => setIsRightPanelOpen(false)}
          selectedProject={currentProject}
          onSelectSuggestion={(q) => handleSend(undefined, q)}
          userRegion={userSettings.region}
        />
      </div>

      {/* Review Form Modal */}
      {reviewingForm && (
        <FormReviewModal 
          formId={reviewingForm.form_id} 
          initialData={reviewingForm.collected_data} 
          onClose={() => setReviewingForm(null)} 
        />
      )}

      {/* Rename Conversation Dialog */}
      {renamingConversation && (
        <div className="dialog-backdrop" onClick={() => setRenamingConversation(null)}>
          <form className="rename-dialog" onSubmit={handleRenameConversation} onClick={(e) => e.stopPropagation()}>
            <div className="dialog-head">
              <h2>Đổi tên cuộc trò chuyện</h2>
              <button type="button" className="icon-button" onClick={() => setRenamingConversation(null)} title="Đóng"><X size={18} /></button>
            </div>
            <label>Tên cuộc trò chuyện<input autoFocus value={renameTitle} onChange={(e) => setRenameTitle(e.target.value)} maxLength={200} /></label>
            <div className="dialog-actions">
              <button type="button" className="secondary-button" onClick={() => setRenamingConversation(null)}>Hủy</button>
              <button type="submit" className="primary-button" disabled={!renameTitle.trim() || conversationActionLoading}>{conversationActionLoading ? "Đang lưu..." : "Lưu"}</button>
            </div>
          </form>
        </div>
      )}

      {/* User Settings Modal */}
      <UserSettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        userId={userId}
        userName={userName}
        userEmail={userEmail}
        onSave={(newSettings) => setUserSettings(newSettings)}
        onLogout={onLogout}
      />
    </div>
  );
}

const adminNav = [
  { id: "overview", label: "Tổng quan", icon: LayoutDashboard },
  { id: "documents", label: "Tài liệu", icon: FileText },
  { id: "forms", label: "Biểu mẫu", icon: FileCheck2 },
  { id: "tests", label: "Bộ kiểm thử", icon: TestTube2 },
  { id: "reports", label: "Nhật ký & báo cáo", icon: BarChart3 },
] as const;

function Metric({ label, value, note, tone }: { label: string; value: string; note: string; tone?: string }) {
  return <article className="metric"><div className={`metric-icon ${tone ?? ""}`}><BarChart3 size={19} /></div><span>{label}</span><strong>{value}</strong><small>{note}</small></article>;
}

function Overview() {
  return <><div className="page-heading"><div><span className="eyebrow">Chất lượng hệ thống</span><h1>Bảng điều khiển</h1><p>Theo dõi hiệu quả trả lời và tình trạng kho tri thức.</p></div><select className="compact-select"><option>30 ngày gần nhất</option><option>7 ngày gần nhất</option></select></div>
    <section className="metric-grid"><Metric label="Faithfulness" value="92.4%" note="+2.1% so với kỳ trước" tone="green" /><Metric label="Answer Relevancy" value="88.7%" note="+1.3% so với kỳ trước" tone="blue" /><Metric label="Context Precision" value="86.1%" note="-0.8% cần theo dõi" tone="amber" /><Metric label="Tỷ lệ fallback" value="4.8%" note="38 / 792 câu hỏi" tone="red" /></section>
    <section className="admin-grid"><div className="panel chart-panel"><div className="panel-title"><div><h2>Chất lượng trả lời</h2><p>Điểm RAGAS theo 6 tuần gần nhất</p></div><MoreHorizontal /></div><div className="chart"><div className="y-labels"><span>100</span><span>75</span><span>50</span><span>25</span><span>0</span></div><div className="chart-body"><div className="chart-lines"><i /><i /><i /><i /></div><svg viewBox="0 0 600 190" preserveAspectRatio="none" aria-label="Biểu đồ điểm chất lượng"><polyline points="0,88 100,78 200,84 300,60 400,66 500,45 600,50" fill="none" stroke="#157347" strokeWidth="4" /><polyline points="0,110 100,100 200,106 300,90 400,84 500,78 600,72" fill="none" stroke="#315f9b" strokeWidth="4" /></svg><div className="x-labels"><span>Tuần 1</span><span>Tuần 2</span><span>Tuần 3</span><span>Tuần 4</span><span>Tuần 5</span><span>Tuần 6</span></div></div></div><div className="legend"><span><i className="green-dot" /> Faithfulness</span><span><i className="blue-dot" /> Relevancy</span></div></div>
      <div className="panel"><div className="panel-title"><div><h2>Tình trạng dữ liệu</h2><p>Cập nhật lúc 10:30 hôm nay</p></div></div><div className="data-stats"><div><span>Tài liệu đã index</span><strong>2</strong></div><div><span>Tổng số chunks</span><strong>280</strong></div><div><span>Câu hỏi hôm nay</span><strong>64</strong></div><div><span>Phản hồi tích cực</span><strong>91%</strong></div></div><button className="secondary-button"><RefreshCw size={16} /> Đồng bộ dữ liệu</button></div></section>
    <section className="panel"><div className="panel-title"><div><h2>Cần chú ý</h2><p>Các câu hỏi có độ tin cậy thấp cần cán bộ rà soát</p></div><button className="text-button">Xem tất cả</button></div><div className="issue-list"><div><CircleAlert /><span><strong>"Trường hợp mất sổ đỏ cần làm gì?"</strong><small>Độ tin cậy 43% · Cấp lại GCN</small></span><button>Kiểm tra</button></div><div><CircleAlert /><span><strong>"Có thể nộp hồ sơ trực tuyến không?"</strong><small>Độ tin cậy 51% · Nộp hồ sơ</small></span><button>Kiểm tra</button></div></div></section></>;
}

function DocumentsView() {
  const [docs, setDocs] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [showUpload, setShowUpload] = useState(false);
  const [chunkDoc, setChunkDoc] = useState<Document | null>(null);
  const [chunks, setChunks] = useState<{id:string;text:string;article?:string;clause?:string;field_type?:string}[]>([]);
  const { toast, show: showToast, hide: hideToast } = useToast();

  useEffect(() => {
    documentsApi.getDocuments().then(setDocs).catch(console.error).finally(() => setLoading(false));
  }, []);

  const handleDelete = async (id: string) => {
    if (!window.confirm("Bạn có chắc muốn xóa tài liệu này?")) return;
    try {
      await documentsApi.deleteDocument(id);
      setDocs(prev => prev.filter(d => d.id !== id));
      showToast("Đã xóa tài liệu.", "success");
    } catch { showToast("Lỗi khi xóa.", "error"); }
  };
  const viewChunks = async (doc: Document) => { try { setChunks(await documentsApi.getChunks(doc.id)); setChunkDoc(doc); } catch { showToast("Không tải được chunks.", "error"); } };
  const reindex = async (doc: Document) => { if (!window.confirm(`Lập chỉ mục lại “${doc.source_name}”? Chunks cũ sẽ được thay bằng chunks mới từ file gốc.`)) return; try { const out = await documentsApi.reindexDocument(doc.id); showToast(out.message, "success"); setDocs(prev => prev.map(item => item.id === doc.id ? {...item, status: "indexing"} : item)); } catch { showToast("Không thể lập chỉ mục lại tài liệu.", "error"); } };

  return <><div className="page-heading"><div><span className="eyebrow">Kho tri thức</span><h1>Quản lý tài liệu</h1><p>Cập nhật, kiểm duyệt và theo dõi quá trình lập chỉ mục.</p></div><button className="primary-button fit" onClick={() => setShowUpload(true)}><UploadCloud size={17} /> Tải tài liệu lên</button></div>
    <section className="panel table-panel"><div className="table-wrap"><table><thead><tr><th>Tài liệu</th><th>Ngày cập nhật</th><th>Chunks</th><th>Trạng thái</th><th /></tr></thead><tbody>
      {loading ? <tr><td colSpan={5} style={{ textAlign: "center", padding: "20px" }}>Đang tải...</td></tr>
      : docs.length === 0 ? <tr><td colSpan={5} style={{ textAlign: "center", padding: "20px" }}>Chưa có tài liệu nào.</td></tr>
      : docs.map(doc => { const sl = statusLabel(doc.status); return <tr key={doc.id}><td><div className="document-name"><FileText size={19} /><span><strong>{doc.source_name}</strong><small>{doc.group_type} · {doc.procedure_type}</small></span></div></td><td>{new Date(doc.created_at).toLocaleDateString("vi-VN")}</td><td>{doc.chunk_count || "—"}</td><td><span className={`status ${sl.cls}`}>{sl.icon}{sl.label}</span></td><td style={{display:"flex",gap:4}}><button className="secondary-button" onClick={() => viewChunks(doc)}>Xem chunks</button><button className="secondary-button" onClick={() => reindex(doc)}>Re-index</button><button className="icon-button" style={{ color: "red" }} onClick={() => handleDelete(doc.id)} title="Xóa"><Trash2 size={17} /></button></td></tr>; })
      }
    </tbody></table></div></section>
    {showUpload && <UploadModal onClose={() => setShowUpload(false)} onSuccess={() => { documentsApi.getDocuments().then(setDocs).catch(console.error); showToast("Tải lên thành công!", "success"); }} />}
    {chunkDoc && <div className="modal-backdrop"><div className="modal-content" style={{maxWidth:820}}><div className="modal-header"><div><h2>Chunks: {chunkDoc.source_name}</h2><small>{chunks.length} chunk · chỉ xem để đối chiếu nguồn</small></div><button className="icon-button" onClick={()=>setChunkDoc(null)}>×</button></div><div className="modal-body">{chunks.length===0?<p>Chưa có chunk. Hãy re-index tài liệu.</p>:chunks.map((chunk,index)=><article key={chunk.id} style={{border:"1px solid #e2e8f0",borderRadius:8,padding:14}}><strong>Chunk {index+1} {chunk.field_type ? `· ${chunk.field_type}` : ""}</strong><small style={{display:"block",color:"#64748b",margin:"4px 0 8px"}}>{[chunk.article,chunk.clause].filter(Boolean).join(" · ") || "Chưa có Điều/Khoản"}</small><p style={{whiteSpace:"pre-wrap",margin:0,lineHeight:1.55}}>{chunk.text}</p></article>)}</div></div></div>}
    {toast && <Toast msg={toast.msg} type={toast.type} onClose={hideToast} />}
  </>;
}


function ReportsView() {
  const [stats, setStats] = useState<Awaited<ReturnType<typeof reportsApi.getStats>> | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { reportsApi.getStats().then(setStats).catch(() => setError("Không tải được số liệu báo cáo thực tế.")); }, []);
  const topics = stats?.topic_stats || [];
  const feedback = stats?.feedback_stats;
  const fallbacks = stats?.fallback_logs || [];
  return <><div className="page-heading"><div><span className="eyebrow">Theo dõi sử dụng</span><h1>Nhật ký & báo cáo</h1><p>Số liệu lấy trực tiếp từ hội thoại, phản hồi và các fallback đã lưu trong hệ thống.</p></div></div>{error && <p style={{color:"#b91c1c"}}>{error}</p>}<section className="admin-grid"><div className="panel"><div className="panel-title"><div><h2>Chủ đề được hỏi nhiều</h2><p>30 ngày gần nhất</p></div></div><div className="topic-list">{topics.length ? topics.map(topic => <div key={topic.name}><span>{topic.name}</span><strong>{topic.percentage}%</strong><i style={{ width: `${topic.percentage}%` }} /></div>) : <p style={{color:"#64748b"}}>Chưa có đủ hội thoại để tổng hợp.</p>}</div></div><div className="panel"><div className="panel-title"><div><h2>Phản hồi người dùng</h2><p>{feedback?.total ?? 0} lượt đánh giá</p></div></div><div className="feedback-score"><div><ThumbsUp /><strong>{feedback?.up_pct ?? 0}%</strong><span>Hữu ích</span></div><div><ThumbsDown /><strong>{feedback?.down_pct ?? 0}%</strong><span>Chưa hữu ích</span></div></div></div></section><section className="panel"><div className="panel-title"><div><h2>Câu hỏi fallback gần đây</h2><p>Cần bổ sung dữ liệu hoặc điều chỉnh truy xuất</p></div></div><div className="log-list">{fallbacks.length ? fallbacks.map((item, index) => <div key={`${item.time}-${index}`}><time>{item.time}</time><span><strong>{item.question}</strong><small>{item.reason}</small></span></div>) : <p style={{color:"#64748b"}}>Chưa có câu hỏi fallback nào được ghi nhận.</p>}</div></section></>;
}

type FormSection = {
  id: string;
  name: string;
  mode: "always" | "yes_no" | "one_of";
  question: string;
  pdfBehavior: "none" | "checkboxes";
  tickYesField: string;
  tickNoField: string;
  oneOfStyle: "fields" | "branches";
  branches: { id: string; name: string; fieldIds: string[] }[];
};
type SectionFieldBehavior = "yes" | "no" | "always";

// ─── Forms View ───────────────────────────────────────────────────
function FormsView() {
  const [forms, setForms] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [showModeSelector, setShowModeSelector] = useState(false);
  const [showManualUploadModal, setShowManualUploadModal] = useState(false);
  const [manualJsonFile, setManualJsonFile] = useState<File | null>(null);
  const [manualDocxFile, setManualDocxFile] = useState<File | null>(null);
  const [manualUploading, setManualUploading] = useState(false);

  const [editingForm, setEditingForm] = useState<any | null>(null);
  const [editName, setEditName] = useState("");
  const [editProcedure, setEditProcedure] = useState("");
  const [editDesc, setEditDesc] = useState("");
  const [editSaving, setEditSaving] = useState(false);
  const [editFields, setEditFields] = useState<any[]>([]);
  const [editTab, setEditTab] = useState<"fields" | "groups" | "flow">("fields");
  const [editPdfUrl, setEditPdfUrl] = useState<string | null>(null);
  const [editPageImages, setEditPageImages] = useState<string[]>([]);
  const [editZoom, setEditZoom] = useState<number>(1);
  const [editZoomMode, setEditZoomMode] = useState<"a4" | "fit">("a4");
  const [editViewFormat, setEditViewFormat] = useState<"images" | "pdf">("images");
  const [editPdfLoading, setEditPdfLoading] = useState(false);
  const [editSections, setEditSections] = useState<FormSection[]>([]);
  const [editSearchQuery, setEditSearchQuery] = useState("");
  const [editFilterMode, setEditFilterMode] = useState<"all" | "unassigned" | "assigned">("all");
  const [editTypeFilter, setEditTypeFilter] = useState<string>("all");
  const [editAdvancedOpen, setEditAdvancedOpen] = useState<Record<string, boolean>>({});
  const [editCollapsedSections, setEditCollapsedSections] = useState<Record<string, boolean>>({});
  const [editGroupMenuOpen, setEditGroupMenuOpen] = useState(false);
  const [editSplitPercent, setEditSplitPercent] = useState<number>(50);
  const [editIsDraggingSplit, setEditIsDraggingSplit] = useState(false);
  const [editPdfOnly, setEditPdfOnly] = useState(false);
  const editContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!editIsDraggingSplit) return;
    const handleMouseMove = (e: MouseEvent) => {
      const container = editContainerRef.current;
      if (!container) return;
      const rect = container.getBoundingClientRect();
      const pct = Math.min(Math.max(((e.clientX - rect.left) / rect.width) * 100, 25), 80);
      setEditSplitPercent(Math.round(pct));
    };
    const handleMouseUp = () => {
      setEditIsDraggingSplit(false);
    };
    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, [editIsDraggingSplit]);

  // Visual Builder State
  const [step, setStep] = useState(1);
  const [docxFile, setDocxFile] = useState<File | null>(null);
  const [previewData, setPreviewData] = useState<any | null>(null);
  const [editableZones, setEditableZones] = useState<any[]>([]);
  const [mode, setMode] = useState<'label' | 'merge' | 'remove' | 'add' | 'adjust'>('label');
  const modeRef = useRef<'label' | 'merge' | 'remove' | 'add' | 'adjust'>('label');
  const [mergeCount, setMergeCount] = useState(0);
  const [labeledCount, setLabeledCount] = useState(0);
  const [activeZoneIdx, setActiveZoneIdx] = useState<string | null>(null);
  const [isPredictingAI, setIsPredictingAI] = useState(false);

  const handleAIPredict = async () => {
    if (!previewData?.temp_id) return;
    setIsPredictingAI(true);
    try {
      const userLabels: Record<string, string> = {};
      Object.entries(labeledSnapshot).forEach(([idxStr, fieldId]) => {
        if (fieldData[fieldId] && fieldData[fieldId].trim() !== "") {
          userLabels[idxStr] = fieldData[fieldId];
        }
      });

      const res = await formsApi.aiPredict(previewData.temp_id, editableZones, userLabels);
      setEditableZones(res.zones);
      
      const newLabeledSnapshot = { ...labeledSnapshot };
      const newFieldOrder = [...fieldOrderSnapshot];
      const newFieldData = { ...fieldData };
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
            newFieldData[fieldId] = z.suggested_label;
            addedCount++;
          } else if (newLabeledSnapshot[idxStr] && !newFieldData[newLabeledSnapshot[idxStr]]) {
            newFieldData[newLabeledSnapshot[idxStr]] = z.suggested_label;
          }
        }
      });
      manualCounterRef.current = fieldCounter;
      setLabeledSnapshot(newLabeledSnapshot);
      setFieldOrderSnapshot(newFieldOrder);
      setLabeledCount(Object.keys(newLabeledSnapshot).length);
      setFieldData(newFieldData);
      
      const manualUncertain = res.zones.filter((zone: any) => String(zone.suggested_label || "") === "Cần đặt tên").length;
      showToast(manualUncertain
        ? `AI đã phân tích. Có ${manualUncertain} vùng vẽ tay cần bạn kiểm tra và đặt tên.`
        : `AI đã gợi ý và tự động chọn ${addedCount} vùng!`, manualUncertain ? "error" : "success");
    } catch (err) {
      showToast("Lỗi khi gọi AI phân tích", "error");
    } finally {
      setIsPredictingAI(false);
    }
  };

  useEffect(() => {
    modeRef.current = mode;
    if (mode !== 'merge') {
      mergeSelectionRef.current.clear();
      setMergeCount(0);
    }
  }, [mode]);

  // Snapshots for step 3
  const [labeledSnapshot, setLabeledSnapshot] = useState<Record<string, string>>({});
  const [fieldOrderSnapshot, setFieldOrderSnapshot] = useState<string[]>([]);
  const mergeSelectionRef = useRef<Set<string>>(new Set());
  const labeledZonesRef = useRef<Record<string, string>>({});
  const fieldOrderRef = useRef<string[]>([]);
  const manualCounterRef = useRef(9000);

  const handleZoneClick = useCallback((idx: number) => {
    const idxStr = String(idx);
    if (mode === 'label') {
      if (labeledZonesRef.current[idxStr]) {
        if (activeZoneIdx === idxStr) {
          delete labeledZonesRef.current[idxStr];
          setActiveZoneIdx(null);
        } else {
          setActiveZoneIdx(idxStr);
        }
      } else {
        const newFieldId = `field_${manualCounterRef.current++}`;
        labeledZonesRef.current[idxStr] = newFieldId;
        if (!fieldOrderRef.current.includes(newFieldId)) {
          fieldOrderRef.current.push(newFieldId);
        }
      }
      setLabeledCount(Object.keys(labeledZonesRef.current).length);
      setLabeledSnapshot({ ...labeledZonesRef.current });
      setFieldOrderSnapshot([...fieldOrderRef.current]);
    } else if (mode === 'adjust') {
      setActiveZoneIdx(idxStr);
    } else if (mode === 'merge') {
      if (mergeSelectionRef.current.has(idxStr)) {
        mergeSelectionRef.current.delete(idxStr);
      } else {
        mergeSelectionRef.current.add(idxStr);
      }
      setMergeCount(mergeSelectionRef.current.size);
    } else if (mode === 'remove') {
      delete labeledZonesRef.current[idxStr];
      setLabeledCount(Object.keys(labeledZonesRef.current).length);
      setLabeledSnapshot({ ...labeledZonesRef.current });
      setFieldOrderSnapshot([...fieldOrderRef.current]);
    }
  }, [mode, activeZoneIdx]);

  const handleMerge = () => {
    if (mergeSelectionRef.current.size < 2) return;
    const items = Array.from(mergeSelectionRef.current);
    let targetField = "";
    for (const item of items) {
      if (labeledZonesRef.current[item]) {
        targetField = labeledZonesRef.current[item];
        break;
      }
    }
    if (!targetField) {
      targetField = `field_${manualCounterRef.current++}`;
      fieldOrderRef.current.push(targetField);
    }
    if (targetField) {
      items.forEach(item => {
        labeledZonesRef.current[item] = targetField;
      });
      showToast(`Đã gộp ${items.length} vùng vào chung nhãn!`, "success");
    }
    mergeSelectionRef.current.clear();
    setMergeCount(0);
    setMode('label');
    setLabeledSnapshot({ ...labeledZonesRef.current });
    setFieldOrderSnapshot([...fieldOrderRef.current]);
  };

  let uniqueFieldsSnapshot = Array.from(new Set(
    fieldOrderSnapshot.filter(fid => Object.values(labeledSnapshot).includes(fid))
  ));
  uniqueFieldsSnapshot.sort((a, b) => {
    const idxA = Object.entries(labeledSnapshot).find(([, v]) => v === a)?.[0] || "";
    const idxB = Object.entries(labeledSnapshot).find(([, v]) => v === b)?.[0] || "";
    const zoneA = editableZones?.find((z: any) => String(z.idx) === idxA);
    const zoneB = editableZones?.find((z: any) => String(z.idx) === idxB);
    if (!zoneA || !zoneB) return 0;
    if (zoneA.page !== zoneB.page) return zoneA.page - zoneB.page;
    const yDiff = zoneA.y - zoneB.y;
    if (Math.abs(yDiff) > 10) return yDiff;
    return zoneA.x - zoneB.x;
  });
  const labeledList = uniqueFieldsSnapshot.map((fid, i) => ({
    id: fid,
    num: i + 1,
    blankIdx: Object.entries(labeledSnapshot).find(([, v]) => v === fid)?.[0] || ""
  }));

  const [formName, setFormName] = useState("");
  const [procedureType, setProcedureType] = useState("");
  const [formDesc, setFormDesc] = useState("");
  const [fieldData, setFieldData] = useState<Record<string, string>>({});
  const [fieldRequired, setFieldRequired] = useState<Record<string, boolean>>({});
  const [fieldDesc, setFieldDesc] = useState<Record<string, string>>({});
  const [fieldType, setFieldType] = useState<Record<string, string>>({});
  const [fieldOptions, setFieldOptions] = useState<Record<string, string>>({});
  const [fieldGroupKey, setFieldGroupKey] = useState<Record<string, string>>({});
  const [fieldDependsOn, setFieldDependsOn] = useState<Record<string, string>>({});
  const [fieldDependsValue, setFieldDependsValue] = useState<Record<string, string>>({});
  const [alternativeGroups, setAlternativeGroups] = useState<{ id: string; name: string }[]>([]);
  const [fieldRequireOneOfGroup, setFieldRequireOneOfGroup] = useState<Record<string, string>>({});
  const [fieldAutoFill, setFieldAutoFill] = useState<Record<string, boolean>>({});
  const [fieldValueSource, setFieldValueSource] = useState<Record<string, string>>({});
  const [fieldDatePart, setFieldDatePart] = useState<Record<string, string>>({});
  const [virtualConditions, setVirtualConditions] = useState<{ id: string; name: string; beforeField: string }[]>([]);
  const [formSections, setFormSections] = useState<{ id: string; name: string; mode: "always" | "yes_no"; question: string }[]>([]);
  const [fieldSectionId, setFieldSectionId] = useState<Record<string, string>>({});
  const [fieldSectionBranch, setFieldSectionBranch] = useState<Record<string, "yes" | "no">>({});
  const { toast, show: showToast, hide: hideToast } = useToast();

  const fetchForms = useCallback(async () => {
    try {
      const data = await formsApi.getForms();
      setForms(data);
    } catch {
      console.error("Error fetching forms");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchForms(); }, [fetchForms]);


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

  const handleAnalyzeDocx = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!docxFile) return showToast("Vui lòng chọn file Word (.docx)", "error");
    setUploading(true);
    try {
      const res = await formsApi.analyzeDocx(docxFile);
      const zones = res.zones || [];
      setPreviewData(res);
      setEditableZones(zones);
      
      const initialLabeledZones: Record<string, string> = {};
      const initialFieldOrder: string[] = [];
      const initialFieldData: Record<string, string> = {};
      let fieldCounter = 1;

      // Auto-assign labels for zones with suggestions
      zones.forEach((zone: any) => {
        const suggestion = zone.suggested_label || zone.ai_label || zone.fallback_name;
        if (suggestion) {
          const fieldId = `field_${9000 + fieldCounter++}`;
          initialLabeledZones[String(zone.idx)] = fieldId;
          initialFieldOrder.push(fieldId);
          initialFieldData[fieldId] = suggestion;
        }
      });
      manualCounterRef.current = 9000 + fieldCounter;

      labeledZonesRef.current = initialLabeledZones;
      fieldOrderRef.current = initialFieldOrder;
      setFieldData(initialFieldData);
      setLabeledCount(Object.keys(initialLabeledZones).length);
      setLabeledSnapshot({ ...initialLabeledZones });
      setFieldOrderSnapshot([...initialFieldOrder]);
      setStep(2);
      
      const autoCount = Object.keys(initialLabeledZones).length;
      showToast((res.total_blanks ?? 0) > 0
        ? `Phát hiện ${res.total_blanks} ô trống. Đã tự động dán nhãn ${autoCount} vùng!`
        : `Tải lên thành công! Bôi đen văn bản hoặc nhấp vào vùng trống để dán nhãn.`, "success");
    } catch (err) {
      const detail = axios.isAxiosError(err) ? err.response?.data?.detail : null;
      showToast(typeof detail === "string" ? detail : "Lỗi phân tích file Word", "error");
    } finally {
      setUploading(false);
    }
  };

  const handleSaveVisual = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formName || !procedureType) {
      showToast("Vui lòng nhập Tên Biểu mẫu và Loại thủ tục", "error");
      return;
    }
    const allFilled = labeledList.every(f => {
      const zone = editableZones?.find((z: any) => String(z.idx) === f.blankIdx);
      const suggested = zone?.suggested_label || zone?.ai_label || "";
      const val = fieldData[f.id] !== undefined ? fieldData[f.id] : suggested;
      return val && val.trim() !== "";
    });
    if (!allFilled) {
      showToast("Vui lòng nhập Tên trường dữ liệu cho TẤT CẢ các nhãn", "error");
      return;
    }
    const radioWithoutChoices = labeledList.find(f => (fieldType[f.id] || "text") === "radio" && (fieldOptions[f.id] || "").split("|").map(v => v.trim()).filter(Boolean).length < 2);
    if (radioWithoutChoices) {
      showToast("Câu hỏi chọn một đáp án cần ít nhất 2 lựa chọn, ngăn cách bằng dấu |.", "error");
      return;
    }
    const invalidAlternativeGroup = alternativeGroups.find(group => !group.name.trim() || Object.values(fieldRequireOneOfGroup).filter(id => id === group.id).length < 2);
    if (invalidAlternativeGroup) {
      showToast("Mỗi nhóm lựa chọn thay thế cần có tên và ít nhất 2 ô được chọn.", "error");
      return;
    }
    const invalidVirtualCondition = virtualConditions.find(condition => !condition.name.trim() || !condition.beforeField);
    if (invalidVirtualCondition) {
      showToast("Mỗi câu hỏi điều kiện cần có nội dung và vị trí hỏi trước một ô thông tin.", "error");
      return;
    }
    const invalidSection = formSections.find(section => !section.name.trim() || !Object.values(fieldSectionId).includes(section.id) || (section.mode === "yes_no" && !section.question.trim()));
    if (invalidSection) {
      showToast("Mỗi cụm cần có tên, ít nhất một ô; cụm Có/Không cần có câu hỏi.", "error");
      return;
    }
    setUploading(true);
    const sectionConditions = formSections.filter(section => section.mode === "yes_no").map(section => {
      const members = labeledList.filter(field => fieldSectionId[field.id] === section.id);
      const firstMember = members[0];
      return { id: `section_condition_${section.id}`, name: section.question.trim(), beforeField: firstMember?.id || "" };
    });
    const allVirtualConditions = [...virtualConditions.filter(condition => condition.name.trim()), ...sectionConditions];
    const virtualFields = allVirtualConditions.map((condition, index) => ({
      key: condition.id,
      name: condition.name.trim(),
      description: `Câu hỏi điều kiện: ${condition.name.trim()}?`,
      required: true,
      type: "boolean",
      value_source: "user_input",
      is_virtual: true,
      display_order: ((labeledList.find(field => field.id === condition.beforeField)?.num || 1) * 100) - 1 - index,
    }));
    const fields = [...virtualFields, ...labeledList.map(f => {
      const zone = editableZones?.find((z: any) => String(z.idx) === f.blankIdx);
      const isCheckbox = zone?.field_type === 'checkbox';
      const suggested = zone?.suggested_label || zone?.ai_label || "";
      const finalName = fieldData[f.id] !== undefined ? fieldData[f.id] : (suggested || f.id);
      
      const customDesc = fieldDesc[f.id];
      const resolvedType = fieldType[f.id] || (isCheckbox ? 'checkbox' : 'text');
      const defaultDesc = resolvedType === 'checkbox' ? `Có hay không: ${finalName}?` : resolvedType === 'radio' ? `Chọn một phương án cho ${finalName}` : `Nhập thông tin cho ${finalName}`;
      
      const base: any = {
        key: f.id,
        name: finalName,
        description: customDesc || defaultDesc,
        required: fieldRequired[f.id] !== false,
        // Persist the visual/PDF order so the backend asks consistently even if
        // a field name has no numeric prefix such as [01].
        display_order: f.num * 100,
        type: resolvedType === 'checkbox' ? 'boolean' : resolvedType === 'radio' ? 'choice' : resolvedType === 'digit_group' ? 'digit_group' : 'string',
        is_auto_fill: fieldValueSource[f.id] === "ai_document" || fieldAutoFill[f.id] || false,
        value_source: fieldValueSource[f.id] || "user_input",
        auto_rule: fieldValueSource[f.id] === "current_date" ? `current_date_${fieldDatePart[f.id] || "day"}` : null,
      };
      
      if (fieldDependsOn[f.id]) {
        const parentId = fieldDependsOn[f.id];
        const parentZone = editableZones?.find((z: any) => String(z.idx) === labeledList.find(l => l.id === parentId)?.blankIdx);
        const parentType = virtualConditions.some(condition => condition.id === parentId) ? "checkbox" : fieldType[parentId] || (parentZone?.field_type === "checkbox" ? "checkbox" : "text");
        base.depends_on = {
          field: parentId,
          value: parentType === "checkbox" ? fieldDependsValue[f.id] !== "false" : fieldDependsValue[f.id],
        };
      }
      const section = formSections.find(item => item.id === fieldSectionId[f.id]);
      if (section?.name.trim()) {
        base.section_name = section.name.trim();
      }
      if (section?.mode === "yes_no") {
        base.depends_on = { field: `section_condition_${section.id}`, value: fieldSectionBranch[f.id] !== "no" };
      }
      if (resolvedType === 'radio') {
        base.options = (fieldOptions[f.id] || "").split("|").map(option => option.trim()).filter(Boolean);
      }
      const alternativeGroup = alternativeGroups.find(group => group.id === fieldRequireOneOfGroup[f.id]);
      if (alternativeGroup?.name.trim()) {
        base.require_one_of_group = alternativeGroup.name.trim();
      }
      
      if (resolvedType === 'digit_group') {
        const gk = (fieldGroupKey[f.id] || finalName || f.id).trim();
        base.group_key = gk;
        base.digit_index = parseInt(String(zone?.idx)) || 0;
      }
      return base;
    })];
    const payload = {
      name: formName,
      procedure_type: procedureType,
      description: formDesc,
      temp_id: previewData?.temp_id || "",
      mapping: labeledSnapshot,
      fields
    };
    try {
      await formsApi.createVisualForm(payload);
      showToast("Tạo biểu mẫu thành công!", "success");
      fetchForms();
      resetModal();
    } catch {
      showToast("Lỗi lưu biểu mẫu", "error");
    } finally {
      setUploading(false);
    }
  };

  const resetModal = () => {
    setShowModal(false);
    setShowModeSelector(false);
    setShowManualUploadModal(false);
    setStep(1);
    setDocxFile(null);
    setPreviewData(null);
    labeledZonesRef.current = {};
    setLabeledCount(0);
    setLabeledSnapshot({});
    setFormName("");
    setProcedureType("");
    setFormDesc("");
    setFieldData({});
  };

  const handleDelete = async (formId: string) => {
    if (!window.confirm("Bạn có chắc chắn muốn xóa biểu mẫu này không?")) return;
    try {
      await formsApi.deleteForm(formId);
      fetchForms();
      showToast("Đã xóa biểu mẫu.", "success");
    } catch {
      console.error("Lỗi khi xóa");
    }
  };

  const openEdit = async (form: any) => {
    setEditingForm(form);
    setEditName(form.name || "");
    setEditProcedure(form.procedure_type || "");
    setEditDesc(form.description || "");
    const rawFields = (form.fields || []).map((f: any, idx: number) => ({
      ...f,
      key: f.key || f.id || `field_${idx + 1}`,
      name: f.name || f.label || `Trường ${idx + 1}`,
      type: f.type || "string",
      required: f.required !== false,
      value_source: f.value_source || (f.is_auto_fill ? "ai_document" : "user_input"),
    }));
    setEditFields(rawFields);
    setEditTab("fields");
    setEditSearchQuery("");
    setEditFilterMode("all");
    setEditTypeFilter("all");
    setEditAdvancedOpen({});
    setEditCollapsedSections({});
    setEditGroupMenuOpen(false);

    // Parse sections from fields
    const physical = rawFields.filter((f: any) => !f.is_virtual);
    const sectionsMap = new Map<string, FormSection>();
    
    physical.forEach((f: any) => {
      const gId = f.alternative_group_id || f.condition_group_id || f.section_id;
      if (!gId) return;
      if (!sectionsMap.has(gId)) {
        const isOneOf = Boolean(f.alternative_group_id);
        const isYesNo = Boolean(f.condition_group_id);
        const mode: "always" | "yes_no" | "one_of" = isOneOf ? "one_of" : isYesNo ? "yes_no" : "always";
        const name = f.alternative_group_name || f.condition_group_name || f.section_name || "Nhóm logic";
        const virtual = rawFields.find((c: any) => c.is_virtual && c.key === `section_condition_${gId}`);
        const question = virtual?.name || f.question_group || "";
        sectionsMap.set(gId, {
          id: gId,
          name,
          mode,
          question,
          pdfBehavior: "none",
          tickYesField: "",
          tickNoField: "",
          oneOfStyle: "fields",
          branches: []
        });
      }
    });

    sectionsMap.forEach((sec, gId) => {
      if (sec.mode === "one_of") {
        const branchNames = new Set<string>();
        physical.forEach((f: any) => {
          if (f.alternative_group_id === gId && f.alternative_branch_name) {
            branchNames.add(f.alternative_branch_name);
          }
        });
        if (branchNames.size > 0) {
          sec.oneOfStyle = "branches";
          sec.branches = Array.from(branchNames).map((bName, idx) => ({
            id: `branch_${gId}_${idx + 1}`,
            name: bName,
            fieldIds: physical.filter((f: any) => f.alternative_group_id === gId && f.alternative_branch_name === bName).map((f: any) => f.key)
          }));
        }
      } else if (sec.mode === "yes_no") {
        const yesField = physical.find((f: any) => f.derived_from?.field === `section_condition_${gId}` && f.derived_from?.value === true);
        const noField = physical.find((f: any) => f.derived_from?.field === `section_condition_${gId}` && f.derived_from?.value === false);
        if (yesField || noField) {
          sec.pdfBehavior = "checkboxes";
          sec.tickYesField = yesField ? yesField.key : "";
          sec.tickNoField = noField ? noField.key : "";
        }
      }
    });

    setEditSections(Array.from(sectionsMap.values()));
    
    if (editPdfUrl) URL.revokeObjectURL(editPdfUrl);
    setEditPdfUrl(null);
    setEditPageImages([]);
    setEditZoom(1);
    setEditPdfLoading(true);
    try {
      const [imgs, blob] = await Promise.all([
        formsApi.previewImages(form.id, {}, "admin").catch(() => []),
        formsApi.previewPdf(form.id, {}, "admin").catch(() => null),
      ]);
      if (imgs && imgs.length > 0) {
        setEditPageImages(imgs);
      }
      if (blob) {
        setEditPdfUrl(URL.createObjectURL(blob));
      }
    } catch (e) {
      console.error("Lỗi tải bản xem trước", e);
    } finally {
      setEditPdfLoading(false);
    }
  };

  const closeEdit = () => {
    setEditingForm(null);
    if (editPdfUrl) URL.revokeObjectURL(editPdfUrl);
    setEditPdfUrl(null);
    setEditPageImages([]);
    setEditPdfOnly(false);
  };

  const addEditSectionPreset = (preset: "always" | "yes_no_none" | "yes_no_tick" | "one_of") => {
    const id = `section_${Date.now()}`;
    let newSec: FormSection;
    if (preset === "always") {
      newSec = { id, name: "", mode: "always", question: "", pdfBehavior: "none", tickYesField: "", tickNoField: "", oneOfStyle: "fields", branches: [] };
    } else if (preset === "yes_no_none") {
      newSec = { id, name: "", mode: "yes_no", question: "", pdfBehavior: "none", tickYesField: "", tickNoField: "", oneOfStyle: "fields", branches: [] };
    } else if (preset === "yes_no_tick") {
      newSec = { id, name: "", mode: "yes_no", question: "", pdfBehavior: "checkboxes", tickYesField: "", tickNoField: "", oneOfStyle: "fields", branches: [] };
    } else {
      const stamp = Date.now();
      newSec = {
        id,
        name: "",
        mode: "one_of",
        question: "",
        pdfBehavior: "none",
        tickYesField: "",
        tickNoField: "",
        oneOfStyle: "branches",
        branches: [
          { id: `branch_${stamp}_1`, name: "Phương án 1", fieldIds: [] },
          { id: `branch_${stamp}_2`, name: "Phương án 2", fieldIds: [] },
        ]
      };
    }
    setEditSections(prev => [...prev, newSec]);
    setEditGroupMenuOpen(false);
    setEditTab("groups");
  };

  const removeEditSection = (sectionId: string) => {
    setEditSections(prev => prev.filter(s => s.id !== sectionId));
    setEditFields(prev => prev.map(f => {
      if (f.section_id === sectionId || f.condition_group_id === sectionId || f.alternative_group_id === sectionId) {
        const next = { ...f };
        delete next.section_id;
        delete next.section_name;
        delete next.question_group;
        delete next.condition_group_id;
        delete next.condition_group_name;
        delete next.condition_behavior;
        delete next.derived_from;
        delete next.alternative_group_id;
        delete next.alternative_group_name;
        delete next.alternative_branch_name;
        if (typeof next.depends_on === "object" && String(next.depends_on?.field || "").startsWith("section_condition_")) {
          next.depends_on = null;
        }
        return next;
      }
      return f;
    }));
  };

  const toggleEditGroupMember = (sec: FormSection, fieldKey: string, checked: boolean, branchId?: string, behavior?: "yes" | "no" | "always") => {
    if (sec.mode === "one_of" && sec.oneOfStyle === "branches" && branchId) {
      setEditSections(prev => prev.map(s => {
        if (s.id !== sec.id) return s;
        return {
          ...s,
          branches: s.branches.map(b => ({
            ...b,
            fieldIds: b.id === branchId
              ? (checked ? [...b.fieldIds.filter(id => id !== fieldKey), fieldKey] : b.fieldIds.filter(id => id !== fieldKey))
              : b.fieldIds.filter(id => id !== fieldKey)
          }))
        };
      }));
      setEditFields(prev => prev.map(f => {
        if (f.key !== fieldKey) return f;
        if (!checked) {
          const next = { ...f };
          delete next.alternative_group_id;
          delete next.alternative_group_name;
          delete next.alternative_branch_name;
          if (typeof next.depends_on === "object" && String(next.depends_on?.field || "").startsWith("section_condition_")) next.depends_on = null;
          return next;
        }
        const b = sec.branches.find(candidate => candidate.id === branchId);
        return {
          ...f,
          alternative_group_id: sec.id,
          alternative_group_name: sec.name,
          alternative_branch_name: b?.name || "",
          depends_on: { field: `section_condition_${sec.id}`, value: b?.name || "" }
        };
      }));
      return;
    }

    setEditFields(prev => prev.map(f => {
      if (f.key !== fieldKey) return f;
      const next = { ...f };
      delete next.section_id; delete next.section_name; delete next.question_group;
      delete next.condition_group_id; delete next.condition_group_name; delete next.condition_behavior;
      delete next.alternative_group_id; delete next.alternative_group_name; delete next.alternative_branch_name; delete next.derived_from;
      if (typeof next.depends_on === "object" && String(next.depends_on?.field || "").startsWith("section_condition_")) next.depends_on = null;

      if (!checked) return next;

      if (sec.mode === "always") {
        return { ...next, section_id: sec.id, section_name: sec.name, question_group: sec.question };
      }
      if (sec.mode === "yes_no") {
        const beh = behavior || next.condition_behavior || "yes";
        return {
          ...next,
          section_id: sec.id,
          section_name: sec.name,
          condition_group_id: sec.id,
          condition_group_name: sec.name,
          condition_behavior: beh,
          depends_on: beh === "always" ? null : { field: `section_condition_${sec.id}`, value: beh === "yes" }
        };
      }
      return {
        ...next,
        alternative_group_id: sec.id,
        alternative_group_name: sec.name,
        depends_on: { field: `section_condition_${sec.id}`, value: next.name }
      };
    }));
  };

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingForm || !editName.trim() || !editProcedure.trim()) {
      showToast("Vui lòng điền đủ Tên và Loại thủ tục", "error");
      return;
    }
    setEditSaving(true);
    try {
      const physicalFields = editFields.filter(f => !f.is_virtual);
      const invalidFormula = physicalFields.find(f => f.value_source === "formula" && !(f.calculation_formula || "").trim());
      if (invalidFormula) {
        showToast(`Vui lòng nhập công thức cho trường "${invalidFormula.name}".`, "error");
        setEditAdvancedOpen(prev => ({ ...prev, [invalidFormula.key]: true }));
        setEditSaving(false);
        return;
      }

      // 2. Build virtual condition fields for yes_no and one_of sections
      const virtualConditions = editSections.filter(s => s.mode === "yes_no" || s.mode === "one_of").map(sec => {
        const members = sec.mode === "one_of" && sec.oneOfStyle === "branches"
          ? physicalFields.filter(f => sec.branches.some(b => b.fieldIds.includes(f.key)))
          : physicalFields.filter(f => (sec.mode === "one_of" ? f.alternative_group_id : f.section_id) === sec.id);
        const options = sec.mode === "one_of" && sec.oneOfStyle === "branches"
          ? sec.branches.map(b => b.name.trim())
          : members.map(f => f.name.trim());
        const genQuestion = sec.mode === "yes_no"
          ? `Bạn có ${sec.name.trim()} không?`
          : `Bạn cần khai báo một trong các thông tin sau: ${options.join(", ").replace(/, ([^,]*)$/, " hoặc $1")}. Bạn muốn cung cấp thông tin nào?`;
        return {
          key: `section_condition_${sec.id}`,
          name: sec.question.trim() || genQuestion,
          description: sec.mode === "one_of" ? `Chọn một phương án: ${sec.name.trim()}` : `Câu hỏi điều kiện: ${sec.name.trim()}?`,
          required: true,
          type: sec.mode === "one_of" ? "choice" : "boolean",
          options: sec.mode === "one_of" ? options : undefined,
          value_source: "user_input",
          is_virtual: true,
          display_order: 10,
        };
      });

      // 3. Assemble all physical fields
      const nonVirtual = physicalFields.map((field, idx) => {
        const res = { ...field };
        res.display_order = (idx + 1) * 100;
        res.is_auto_fill = ["ai_document", "current_date", "formula"].includes(res.value_source) || res.is_auto_fill || false;
        
        const sec = editSections.find(s => s.id === (res.section_id || res.condition_group_id || res.alternative_group_id));
        if (sec) {
          if (sec.mode === "always") {
            res.section_id = sec.id;
            res.section_name = sec.name.trim();
            res.question_group = sec.question.trim();
            delete res.condition_group_id;
            delete res.condition_group_name;
            delete res.condition_behavior;
            delete res.alternative_group_id;
            delete res.alternative_group_name;
            delete res.alternative_branch_name;
          } else if (sec.mode === "yes_no") {
            res.section_id = sec.id;
            res.section_name = sec.name.trim();
            res.condition_group_id = sec.id;
            res.condition_group_name = sec.name.trim();
            delete res.alternative_group_id;
            delete res.alternative_group_name;
            delete res.alternative_branch_name;
            if (sec.pdfBehavior === "checkboxes" && (sec.tickYesField === res.key || sec.tickNoField === res.key)) {
              res.derived_from = {
                field: `section_condition_${sec.id}`,
                value: sec.tickYesField === res.key,
              };
              res.required = false;
            } else {
              delete res.derived_from;
              if (res.condition_behavior === "yes" || res.condition_behavior === "no") {
                res.depends_on = { field: `section_condition_${sec.id}`, value: res.condition_behavior === "yes" };
              }
            }
          } else if (sec.mode === "one_of") {
            res.alternative_group_id = sec.id;
            res.alternative_group_name = sec.name.trim();
            delete res.section_id;
            delete res.section_name;
            delete res.question_group;
            delete res.condition_group_id;
            delete res.condition_group_name;
            delete res.condition_behavior;
            delete res.derived_from;
            if (sec.oneOfStyle === "branches") {
              const b = sec.branches.find(branch => branch.fieldIds.includes(res.key));
              if (b) {
                res.alternative_branch_name = b.name.trim();
                res.depends_on = { field: `section_condition_${sec.id}`, value: b.name.trim() };
              }
            } else {
              res.depends_on = { field: `section_condition_${sec.id}`, value: res.name.trim() };
            }
          }
        }
        return res;
      });

      const fieldsToSave = [...virtualConditions, ...nonVirtual];

      await formsApi.updateForm(editingForm.id, { 
        name: editName.trim(), 
        procedure_type: editProcedure.trim(), 
        description: editDesc.trim(), 
        fields: fieldsToSave
      });
      showToast("Cập nhật biểu mẫu thành công!", "success");
      closeEdit();
      fetchForms();
    } catch (err) {
      console.error(err);
      showToast("Lỗi cập nhật biểu mẫu", "error");
    } finally {
      setEditSaving(false);
    }
  };

  return (
    <>
      <style>{`
        .blank-zone {
          display: inline-block; min-width: 80px;
          border-bottom: 2.5px dashed #f59e0b; background: #fffbeb;
          cursor: pointer; padding: 1px 6px; margin: 0 1px;
          border-radius: 3px; transition: all 0.18s ease;
          vertical-align: baseline; position: relative;
        }
        .blank-zone::after { content: '↗'; font-size: 9px; color: #f59e0b; position: absolute; top: -4px; right: -2px; opacity: 0.7; }
        .blank-zone:hover { background: #fef3c7; border-bottom-color: #d97706; box-shadow: 0 0 0 2px #fde68a; }
        .blank-zone--labeled { background: #dbeafe; border-bottom: 2.5px solid #2563eb; border-radius: 3px; }
        .blank-zone--labeled::after { content: ''; }
        .blank-zone--labeled:hover { background: #bfdbfe; box-shadow: 0 0 0 2px #93c5fd; }
        .blank-dots { color: #b45309; font-family: inherit; font-size: inherit; pointer-events: none; }
        .blank-label-text { color: #1d4ed8; font-weight: 700; font-size: 0.88em; pointer-events: none; }
        .blank-zone--manual { border-bottom-color: #16a34a; background: #f0fdf4; }
        .blank-zone--manual:hover { background: #dcfce7; border-bottom-color: #15803d; box-shadow: 0 0 0 2px #bbf7d0; }
        .blank-zone--merging { background: #fef08a !important; border-bottom-color: #ca8a04 !important; box-shadow: 0 0 0 2px #fde047 !important; }
        .mode-remove .blank-zone:hover { background: #fee2e2 !important; border-bottom-color: #dc2626 !important; box-shadow: 0 0 0 2px #fca5a5 !important; cursor: not-allowed !important; }
        .mode-add { cursor: text !important; }
        .mode-add .blank-zone { cursor: default !important; }
      `}</style>

      <div className="page-heading">
        <div>
          <span className="eyebrow">Hệ thống</span>
          <h1>Quản lý Biểu mẫu</h1>
          <p>Tải lên file Word và AI sẽ tự động nhận diện khoảng trống.</p>
        </div>
        <div>
          <button type="button" className="primary-button fit" onClick={() => setShowModeSelector(true)} style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
            <UploadCloud size={17} /> Thêm Biểu mẫu thông minh
          </button>
        </div>
      </div>

      <section className="panel table-panel">
        <div className="table-wrap">
          <table>
            <thead><tr><th>Tên Biểu mẫu</th><th>Loại Thủ tục</th><th>Ngày tạo</th><th /></tr></thead>
            <tbody>
              {loading
                ? <tr><td colSpan={4} style={{ textAlign: "center", padding: "20px" }}>Đang tải...</td></tr>
                : forms.length === 0
                  ? <tr><td colSpan={4} style={{ textAlign: "center", padding: "20px" }}>Chưa có biểu mẫu nào trong hệ thống.</td></tr>
                  : forms.map(form => (
                    <tr key={form.id}>
                      <td><strong>{form.name}</strong></td>
                      <td><span className="status done">{form.procedure_type}</span></td>
                      <td>{new Date(form.created_at).toLocaleDateString("vi-VN")}</td>
                      <td>
                        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
                          <button onClick={() => openEdit(form)} className="icon-button" title="Chỉnh sửa" style={{ color: "#4f46e5" }}><Pencil size={17} /></button>
                          <button onClick={() => handleDelete(form.id)} className="icon-button" title="Xóa" style={{ color: "red" }}><Trash2 size={17} /></button>
                        </div>
                      </td>
                    </tr>
                  ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Edit Form Dialog */}
      {editingForm && (() => {
        const physicalFields = editFields.filter(f => !f.is_virtual);
        const assignedCount = physicalFields.filter(f => {
          const isOneOfBranch = editSections.some(s => s.mode === "one_of" && s.oneOfStyle === "branches" && s.branches.some(b => b.fieldIds.includes(f.key)));
          const isTickPdf = editSections.some(s => s.pdfBehavior === "checkboxes" && (s.tickYesField === f.key || s.tickNoField === f.key));
          return Boolean(f.section_id || f.condition_group_id || f.alternative_group_id || isOneOfBranch || isTickPdf);
        }).length;
        const unassignedCount = physicalFields.length - assignedCount;

        const filteredFields = physicalFields.filter((field, idx) => {
          const q = editSearchQuery.toLowerCase().trim();
          const num = idx + 1;
          if (q) {
            const matchNum = `ô #${num}`.includes(q) || `#${num}`.includes(q) || String(num) === q;
            const matchKey = (field.key || "").toLowerCase().includes(q);
            const matchName = (field.name || "").toLowerCase().includes(q);
            if (!matchNum && !matchKey && !matchName) return false;
          }

          const isOneOfBranch = editSections.some(s => s.mode === "one_of" && s.oneOfStyle === "branches" && s.branches.some(b => b.fieldIds.includes(field.key)));
          const isTickPdf = editSections.some(s => s.pdfBehavior === "checkboxes" && (s.tickYesField === field.key || s.tickNoField === field.key));
          const isAssigned = Boolean(field.section_id || field.condition_group_id || field.alternative_group_id || isOneOfBranch || isTickPdf);

          if (editFilterMode === "assigned" && !isAssigned) return false;
          if (editFilterMode === "unassigned" && isAssigned) return false;

          const currentType = field.type === "checkbox" || field.type === "boolean" ? "checkbox" : field.type === "date" ? "date" : field.type === "digit_group" ? "digit_group" : "text";
          if (editTypeFilter !== "all") {
            if (currentType !== editTypeFilter) return false;
          }

          return true;
        });

        return (
          <div
            className="dialog-backdrop"
            style={{
              position: "fixed",
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              padding: 0,
              background: "rgba(0,0,0,0.65)",
              display: "flex",
              alignItems: "stretch",
              justifyContent: "center",
              zIndex: 1000
            }}
            onClick={closeEdit}
          >
            <div
              ref={editContainerRef}
              className="rename-dialog"
              style={{
                width: "100%",
                maxWidth: "100%",
                height: "100vh",
                maxHeight: "100vh",
                padding: 0,
                overflow: "hidden",
                display: "flex",
                flexDirection: "row",
                gap: 0,
                borderRadius: 0,
                boxShadow: "none",
                border: "none",
                userSelect: editIsDraggingSplit ? "none" : "auto"
              }}
              onClick={(e) => e.stopPropagation()}
            >
              
              {/* Left Configuration Panel */}
              <div style={{
                width: editPdfOnly ? "0px" : `${editSplitPercent}%`,
                minWidth: editPdfOnly ? "0px" : "360px",
                maxWidth: editPdfOnly ? "0px" : "85%",
                display: editPdfOnly ? "none" : "flex",
                flexDirection: "column",
                background: "#f8fafc",
                borderRight: "1px solid #e2e8f0",
                overflow: "hidden",
                flexShrink: 0
              }}>
                
                {/* Panel Header */}
                <div style={{ padding: "12px 18px", borderBottom: "1px solid #e2e8f0", background: "#ffffff", display: "flex", alignItems: "center", justifyContent: "space-between", flexShrink: 0 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <div style={{ width: 34, height: 34, borderRadius: 8, background: "linear-gradient(135deg, #4f46e5 0%, #6366f1 100%)", display: "flex", alignItems: "center", justifyContent: "center", color: "#fff", boxShadow: "0 2px 6px rgba(79, 70, 229, 0.25)" }}>
                      <Pencil size={17} />
                    </div>
                    <div>
                      <h2 style={{ margin: 0, fontSize: "1.05rem", fontWeight: 700, color: "#1e293b" }}>Chỉnh sửa Biểu mẫu</h2>
                      <p style={{ margin: 0, fontSize: "0.74rem", color: "#64748b" }}>Cấu hình nhãn ô, nhóm logic, rẽ nhánh và luồng trợ lý AI</p>
                    </div>
                  </div>

                  {/* Preset layout switcher */}
                  <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
                    <button
                      type="button"
                      onClick={() => setEditSplitPercent(50)}
                      style={{
                        padding: "5px 10px", fontSize: "0.72rem", borderRadius: 6,
                        border: `1px solid ${editSplitPercent === 50 ? "#4f46e5" : "#cbd5e1"}`,
                        background: editSplitPercent === 50 ? "#ede9fe" : "#fff",
                        color: editSplitPercent === 50 ? "#4338ca" : "#64748b",
                        cursor: "pointer", fontWeight: editSplitPercent === 50 ? 700 : 500
                      }}
                      title="Chia đều 50% cấu hình - 50% tài liệu xem trước"
                    >
                      50 : 50
                    </button>
                    <button
                      type="button"
                      onClick={() => setEditSplitPercent(60)}
                      style={{
                        padding: "5px 10px", fontSize: "0.72rem", borderRadius: 6,
                        border: `1px solid ${editSplitPercent === 60 ? "#4f46e5" : "#cbd5e1"}`,
                        background: editSplitPercent === 60 ? "#ede9fe" : "#fff",
                        color: editSplitPercent === 60 ? "#4338ca" : "#64748b",
                        cursor: "pointer", fontWeight: editSplitPercent === 60 ? 700 : 500
                      }}
                      title="Ưu tiên cột chỉnh sửa rộng rãi hơn (60% màn hình)"
                    >
                      Rộng 60%
                    </button>
                    <button
                      type="button"
                      onClick={() => setEditSplitPercent(40)}
                      style={{
                        padding: "5px 10px", fontSize: "0.72rem", borderRadius: 6,
                        border: `1px solid ${editSplitPercent === 40 ? "#4f46e5" : "#cbd5e1"}`,
                        background: editSplitPercent === 40 ? "#ede9fe" : "#fff",
                        color: editSplitPercent === 40 ? "#4338ca" : "#64748b",
                        cursor: "pointer", fontWeight: editSplitPercent === 40 ? 700 : 500
                      }}
                      title="Ưu tiên tài liệu xem trước lớn hơn (40% chỉnh sửa : 60% xem)"
                    >
                      Rộng 40%
                    </button>
                    <button type="button" className="icon-button mobile-only" onClick={closeEdit}><X size={18} /></button>
                  </div>
                </div>

                <form id="edit-form" onSubmit={handleUpdate} style={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column", overflow: "hidden" }}>
                  <div style={{ flex: 1, minHeight: 0, overflowY: "auto", padding: "16px 20px", display: "flex", flexDirection: "column" }}>
                    
                    {/* Form Metadata Card */}
                    <div style={{ background: "#ffffff", padding: "12px 14px", borderRadius: 10, border: "1px solid #e2e8f0", marginBottom: 12, boxShadow: "0 1px 3px rgba(0,0,0,0.03)", flexShrink: 0 }}>
                      <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: 10, marginBottom: 8 }}>
                        <div>
                          <label style={{ display: "block", fontSize: "0.74rem", fontWeight: 700, color: "#334155", marginBottom: 4 }}>
                            Tên Biểu mẫu <span style={{ color: "#ef4444" }}>*</span>
                          </label>
                          <input
                            value={editName}
                            onChange={(e) => setEditName(e.target.value)}
                            placeholder="VD: Đơn đăng ký cấp đổi GCN"
                            style={{ width: "100%", padding: "7px 10px", border: "1px solid #cbd5e1", borderRadius: 6, fontSize: "0.82rem", outline: "none", background: "#f8fafc" }}
                            onFocus={(e) => { e.currentTarget.style.borderColor = "#4f46e5"; e.currentTarget.style.background = "#fff"; }}
                            onBlur={(e) => { e.currentTarget.style.borderColor = "#cbd5e1"; e.currentTarget.style.background = "#f8fafc"; }}
                          />
                        </div>
                        <div>
                          <label style={{ display: "block", fontSize: "0.74rem", fontWeight: 700, color: "#334155", marginBottom: 4 }}>
                            Loại thủ tục <span style={{ color: "#ef4444" }}>*</span>
                          </label>
                          <input
                            value={editProcedure}
                            onChange={(e) => setEditProcedure(e.target.value)}
                            placeholder="VD: cap_doi"
                            style={{ width: "100%", padding: "7px 10px", border: "1px solid #cbd5e1", borderRadius: 6, fontSize: "0.82rem", outline: "none", background: "#f8fafc" }}
                            onFocus={(e) => { e.currentTarget.style.borderColor = "#4f46e5"; e.currentTarget.style.background = "#fff"; }}
                            onBlur={(e) => { e.currentTarget.style.borderColor = "#cbd5e1"; e.currentTarget.style.background = "#f8fafc"; }}
                          />
                        </div>
                      </div>
                      <div>
                        <label style={{ display: "block", fontSize: "0.74rem", fontWeight: 700, color: "#334155", marginBottom: 4 }}>
                          Mô tả ngắn
                        </label>
                        <input
                          value={editDesc}
                          onChange={(e) => setEditDesc(e.target.value)}
                          placeholder="Mô tả tóm tắt thủ tục cho người dùng..."
                          style={{ width: "100%", padding: "6px 10px", border: "1px solid #cbd5e1", borderRadius: 6, fontSize: "0.8rem", outline: "none", background: "#f8fafc" }}
                          onFocus={(e) => { e.currentTarget.style.borderColor = "#4f46e5"; e.currentTarget.style.background = "#fff"; }}
                          onBlur={(e) => { e.currentTarget.style.borderColor = "#cbd5e1"; e.currentTarget.style.background = "#f8fafc"; }}
                        />
                      </div>
                    </div>

                    {/* Segmented 3-Tab Control */}
                    <div style={{ display: "flex", background: "#f1f5f9", padding: 3, borderRadius: 8, gap: 4, marginBottom: 14, border: "1px solid #e2e8f0", position: "sticky", top: 0, zIndex: 12, flexShrink: 0 }}>
                      <button
                        type="button"
                        onClick={() => setEditTab("fields")}
                        style={{
                          flex: 1, padding: "7px 6px", borderRadius: 6, border: "none",
                          background: editTab === "fields" ? "#ffffff" : "transparent",
                          color: editTab === "fields" ? "#4338ca" : "#64748b",
                          fontWeight: editTab === "fields" ? 700 : 500, fontSize: "0.76rem", cursor: "pointer",
                          display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
                          boxShadow: editTab === "fields" ? "0 1px 3px rgba(0,0,0,0.08)" : "none",
                          transition: "all 0.15s ease"
                        }}
                      >
                        <FileText size={14} />
                        <span>DS {physicalFields.length} trường</span>
                        <span style={{ background: editTab === "fields" ? "#ede9fe" : "#e2e8f0", color: editTab === "fields" ? "#6d28d9" : "#475569", padding: "1px 6px", borderRadius: 10, fontSize: "0.68rem" }}>
                          {assignedCount}/{physicalFields.length}
                        </span>
                      </button>

                      <button
                        type="button"
                        onClick={() => setEditTab("groups")}
                        style={{
                          flex: 1, padding: "7px 6px", borderRadius: 6, border: "none",
                          background: editTab === "groups" ? "#ffffff" : "transparent",
                          color: editTab === "groups" ? "#4338ca" : "#64748b",
                          fontWeight: editTab === "groups" ? 700 : 500, fontSize: "0.76rem", cursor: "pointer",
                          display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
                          boxShadow: editTab === "groups" ? "0 1px 3px rgba(0,0,0,0.08)" : "none",
                          transition: "all 0.15s ease"
                        }}
                      >
                        <Layers size={14} />
                        <span>Nhóm logic</span>
                        <span style={{ background: editTab === "groups" ? "#ede9fe" : "#e2e8f0", color: editTab === "groups" ? "#6d28d9" : "#475569", padding: "1px 6px", borderRadius: 10, fontSize: "0.68rem" }}>
                          {editSections.length}
                        </span>
                      </button>

                      <button
                        type="button"
                        onClick={() => setEditTab("flow")}
                        style={{
                          flex: 1, padding: "7px 6px", borderRadius: 6, border: "none",
                          background: editTab === "flow" ? "#ffffff" : "transparent",
                          color: editTab === "flow" ? "#4338ca" : "#64748b",
                          fontWeight: editTab === "flow" ? 700 : 500, fontSize: "0.76rem", cursor: "pointer",
                          display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
                          boxShadow: editTab === "flow" ? "0 1px 3px rgba(0,0,0,0.08)" : "none",
                          transition: "all 0.15s ease"
                        }}
                      >
                        <Sparkles size={14} />
                        <span>Luồng AI</span>
                      </button>
                    </div>

                    {/* TAB 1: DANH SÁCH TRƯỜNG */}
                    {editTab === "fields" && (
                      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                        {/* Search & Filter Toolbar */}
                        <div style={{ position: "sticky", top: 40, zIndex: 11, background: "#f8fafc", paddingBottom: 10, borderBottom: "1px solid #e2e8f0", marginBottom: 2 }}>
                          <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                            <div style={{ position: "relative", flex: 1 }}>
                              <Search size={14} style={{ position: "absolute", left: 9, top: "50%", transform: "translateY(-50%)", color: "#94a3b8" }} />
                              <input
                                value={editSearchQuery}
                                onChange={e => setEditSearchQuery(e.target.value)}
                                placeholder="Tìm theo tên trường, số #, hoặc ID..."
                                style={{ width: "100%", padding: "7px 28px 7px 28px", fontSize: "0.78rem", border: "1px solid #cbd5e1", borderRadius: 6, background: "#fff", outline: "none" }}
                              />
                              {editSearchQuery && (
                                <button
                                  type="button"
                                  onClick={() => setEditSearchQuery("")}
                                  style={{ position: "absolute", right: 6, top: "50%", transform: "translateY(-50%)", border: 0, background: "transparent", color: "#9ca3af", cursor: "pointer", padding: 2 }}
                                >
                                  <X size={13} />
                                </button>
                              )}
                            </div>
                          </div>

                          {/* Filter Chips */}
                          <div style={{ display: "flex", gap: 4, marginTop: 8, flexWrap: "wrap", alignItems: "center" }}>
                            <button
                              type="button"
                              onClick={() => setEditFilterMode("all")}
                              style={{
                                padding: "3px 8px", borderRadius: 20,
                                border: `1px solid ${editFilterMode === "all" ? "#4f46e5" : "#cbd5e1"}`,
                                background: editFilterMode === "all" ? "#ede9fe" : "#fff",
                                color: editFilterMode === "all" ? "#4338ca" : "#64748b",
                                fontSize: "0.72rem", fontWeight: editFilterMode === "all" ? 700 : 500, cursor: "pointer"
                              }}
                            >
                              Tất cả ({physicalFields.length})
                            </button>
                            <button
                              type="button"
                              onClick={() => setEditFilterMode("unassigned")}
                              style={{
                                padding: "3px 8px", borderRadius: 20,
                                border: `1px solid ${editFilterMode === "unassigned" ? "#f59e0b" : "#cbd5e1"}`,
                                background: editFilterMode === "unassigned" ? "#fef3c7" : "#fff",
                                color: editFilterMode === "unassigned" ? "#b45309" : "#64748b",
                                fontSize: "0.72rem", fontWeight: editFilterMode === "unassigned" ? 700 : 500, cursor: "pointer"
                              }}
                            >
                              Chưa gom ({unassignedCount})
                            </button>
                            <button
                              type="button"
                              onClick={() => setEditFilterMode("assigned")}
                              style={{
                                padding: "3px 8px", borderRadius: 20,
                                border: `1px solid ${editFilterMode === "assigned" ? "#10b981" : "#cbd5e1"}`,
                                background: editFilterMode === "assigned" ? "#d1fae5" : "#fff",
                                color: editFilterMode === "assigned" ? "#047857" : "#64748b",
                                fontSize: "0.72rem", fontWeight: editFilterMode === "assigned" ? 700 : 500, cursor: "pointer"
                              }}
                            >
                              Đã gom ({assignedCount})
                            </button>

                            <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 4 }}>
                              <select
                                value={editTypeFilter}
                                onChange={e => setEditTypeFilter(e.target.value)}
                                style={{ padding: "3px 6px", fontSize: "0.7rem", border: "1px solid #cbd5e1", borderRadius: 4, background: "#fff", color: "#475569" }}
                              >
                                <option value="all">Mọi loại ô</option>
                                <option value="text">📝 Chữ</option>
                                <option value="checkbox">☑ Checkbox</option>
                                <option value="date">📅 Ngày tháng</option>
                                <option value="digit_group">🔢 Dãy số</option>
                              </select>
                            </div>
                          </div>
                        </div>

                        {/* Fields List */}
                        {filteredFields.length === 0 && (
                          <div style={{ padding: "24px 16px", textAlign: "center", color: "#64748b", fontSize: "0.82rem", background: "#fff", border: "1px dashed #cbd5e1", borderRadius: 8 }}>
                            Không tìm thấy trường nào phù hợp với bộ lọc.
                          </div>
                        )}

                        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                          {filteredFields.map((field) => {
                            const fieldIndex = physicalFields.findIndex(f => f.key === field.key);
                            const num = fieldIndex + 1;
                            const isCheckbox = field.type === "checkbox" || field.type === "boolean";
                            const isDate = field.type === "date";
                            const isDigitGroup = field.type === "digit_group";
                            const selectedType = isCheckbox ? "checkbox" : isDate ? "date" : isDigitGroup ? "digit_group" : "text";
                            
                            const tickGroup = editSections.find(s => s.pdfBehavior === "checkboxes" && (s.tickYesField === field.key || s.tickNoField === field.key));
                            const alternativeBranch = editSections
                              .filter(item => item.mode === "one_of" && item.oneOfStyle === "branches")
                              .flatMap(item => item.branches.map(branch => ({ section: item, branch })))
                              .find(item => item.branch.fieldIds.includes(field.key));
                            const sec = editSections.find(s => s.id === (field.section_id || field.condition_group_id || field.alternative_group_id));
                            const hasGroup = Boolean(sec || tickGroup || alternativeBranch);

                            const hasAdvanced = Boolean(
                              field.description || field.depends_on || (field.value_source && field.value_source !== "user_input") || field.calculation_formula
                            );
                            const advOpen = editAdvancedOpen[field.key] ?? false;

                            return (
                              <div key={field.key} style={{
                                padding: "10px 12px",
                                border: `1px solid ${hasGroup ? "#c4b5fd" : "#e2e8f0"}`,
                                borderRadius: 8,
                                background: hasGroup ? "#faf8ff" : "#ffffff",
                                boxShadow: "0 1px 2px rgba(0,0,0,0.02)"
                              }}>
                                {/* Row 1: Badge, Input, Type selector */}
                                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                                  <div
                                    title={`Trường #${num} (${field.key})`}
                                    style={{
                                      width: 26, height: 26, borderRadius: "50%",
                                      background: selectedType === "checkbox" ? "#4f46e5" : selectedType === "date" ? "#059669" : hasGroup ? "#7c3aed" : "#3b82f6",
                                      color: "#fff", display: "flex", alignItems: "center",
                                      justifyContent: "center", fontWeight: 700, fontSize: "0.75rem",
                                      flexShrink: 0
                                    }}
                                  >
                                    {num}
                                  </div>

                                  <input
                                    type="text"
                                    value={field.name || ""}
                                    onChange={(e) => {
                                      const val = e.target.value;
                                      setEditFields(prev => prev.map(item => item.key === field.key ? { ...item, name: val } : item));
                                    }}
                                    placeholder={`Tên hiển thị trường #${num}`}
                                    style={{
                                      flex: 1, minWidth: 0, padding: "6px 9px",
                                      border: "1px solid #cbd5e1", borderRadius: 6,
                                      fontSize: "0.82rem", fontWeight: 500, background: "#fff", outline: "none"
                                    }}
                                  />

                                  <select
                                    value={selectedType}
                                    onChange={(e) => {
                                      const val = e.target.value;
                                      const newType = val === "checkbox" ? "boolean" : val === "date" ? "date" : val === "digit_group" ? "digit_group" : "string";
                                      setEditFields(prev => prev.map(item => item.key === field.key ? { ...item, type: newType } : item));
                                    }}
                                    style={{
                                      padding: "6px 8px", fontSize: "0.74rem",
                                      border: "1px solid #cbd5e1", borderRadius: 6,
                                      cursor: "pointer", flexShrink: 0,
                                      background: "#fff", fontWeight: 600, color: "#334155"
                                    }}
                                  >
                                    <option value="text">📝 Chữ</option>
                                    <option value="checkbox">☑ Checkbox</option>
                                    <option value="date">📅 Ngày tháng</option>
                                    <option value="digit_group">🔢 Dãy số</option>
                                  </select>
                                </div>

                                {/* Row 2: Logic nhánh, Group dropdown, Required, Advanced */}
                                <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
                                  
                                  {/* Logic nhánh (Phụ thuộc vào ô khác) */}
                                  <div style={{ display: "flex", alignItems: "center", gap: 4, flexShrink: 0 }}>
                                    <GitBranch size={13} style={{ color: field.depends_on ? "#7c3aed" : "#94a3b8" }} />
                                    <select
                                      value={typeof field.depends_on === "object" && field.depends_on !== null ? field.depends_on.field : (field.depends_on || "")}
                                      onChange={(e) => {
                                        const val = e.target.value;
                                        setEditFields(prev => prev.map(item => {
                                          if (item.key !== field.key) return item;
                                          if (!val) return { ...item, depends_on: null };
                                          return { ...item, depends_on: { field: val, value: true } };
                                        }));
                                      }}
                                      style={{
                                        fontSize: "0.72rem", padding: "4px 8px", borderRadius: 5,
                                        border: `1px solid ${field.depends_on ? "#c4b5fd" : "#cbd5e1"}`,
                                        background: field.depends_on ? "#f5f3ff" : "#fff",
                                        color: field.depends_on ? "#6d28d9" : "#475569",
                                        fontWeight: field.depends_on ? 600 : 400,
                                        maxWidth: 240, cursor: "pointer"
                                      }}
                                      title="Logic nhánh: Điều kiện phụ thuộc để AI hỏi ô này"
                                    >
                                      <option value="">-- Logic nhánh: Luôn hỏi --</option>
                                      {physicalFields.filter(other => other.key !== field.key).map((other, oIdx) => (
                                        <option key={other.key} value={other.key}>
                                          ↳ Chỉ hỏi khi có #{oIdx + 1}: {other.name || other.key}
                                        </option>
                                      ))}
                                    </select>
                                  </div>

                                  {/* Nhóm logic Dropdown */}
                                  <div style={{ display: "flex", alignItems: "center", gap: 4, flexShrink: 0 }}>
                                    <select
                                      value={
                                        (() => {
                                          if (tickGroup) return `tick:${tickGroup.id}:${tickGroup.tickYesField === field.key ? "yes" : "no"}`;
                                          if (alternativeBranch) return `branch:${alternativeBranch.section.id}:${alternativeBranch.branch.id}`;
                                          if (field.alternative_group_id) return `one_of:${field.alternative_group_id}`;
                                          if (field.condition_group_id) return `yes_no:${field.condition_group_id}:${field.condition_behavior || "yes"}`;
                                          if (field.section_id) return `always:${field.section_id}`;
                                          return "";
                                        })()
                                      }
                                      onChange={(e) => {
                                        const val = e.target.value;
                                        if (!val) {
                                          // Unassign
                                          setEditFields(prev => prev.map(item => {
                                            if (item.key !== field.key) return item;
                                            const next = { ...item };
                                            delete next.section_id; delete next.section_name; delete next.question_group;
                                            delete next.condition_group_id; delete next.condition_group_name; delete next.condition_behavior; delete next.derived_from;
                                            delete next.alternative_group_id; delete next.alternative_group_name; delete next.alternative_branch_name;
                                            if (typeof next.depends_on === "object" && String(next.depends_on?.field || "").startsWith("section_condition_")) next.depends_on = null;
                                            return next;
                                          }));
                                          setEditSections(prev => prev.map(s => {
                                            if (s.mode === "one_of" && s.oneOfStyle === "branches") {
                                              return { ...s, branches: s.branches.map(b => ({ ...b, fieldIds: b.fieldIds.filter(id => id !== field.key) })) };
                                            }
                                            if (s.pdfBehavior === "checkboxes") {
                                              return { ...s, tickYesField: s.tickYesField === field.key ? "" : s.tickYesField, tickNoField: s.tickNoField === field.key ? "" : s.tickNoField };
                                            }
                                            return s;
                                          }));
                                          return;
                                        }

                                        const [type, gId, extra] = val.split(":");
                                        const targetSec = editSections.find(s => s.id === gId);
                                        if (!targetSec) return;

                                        if (type === "always") {
                                          toggleEditGroupMember(targetSec, field.key, true);
                                        } else if (type === "yes_no") {
                                          toggleEditGroupMember(targetSec, field.key, true, undefined, extra as "yes" | "no" | "always");
                                        } else if (type === "one_of") {
                                          toggleEditGroupMember(targetSec, field.key, true);
                                        } else if (type === "branch") {
                                          toggleEditGroupMember(targetSec, field.key, true, extra);
                                        }
                                      }}
                                      style={{
                                        fontSize: "0.72rem", padding: "4px 8px", borderRadius: 5,
                                        border: `1px solid ${hasGroup ? "#a78bfa" : "#cbd5e1"}`,
                                        background: hasGroup ? "#f5f3ff" : "#f8fafc",
                                        color: hasGroup ? "#5b21b6" : "#64748b",
                                        fontWeight: hasGroup ? 600 : 400,
                                        maxWidth: 260, cursor: "pointer"
                                      }}
                                    >
                                      <option value="">-- Chưa vào nhóm --</option>
                                      {editSections.map(s => {
                                        if (s.mode === "always") {
                                          return <option key={s.id} value={`always:${s.id}`}>🟢 Cụm: {s.name || "Chưa đặt tên"}</option>;
                                        }
                                        if (s.mode === "yes_no") {
                                          return (
                                            <optgroup key={s.id} label={`${s.pdfBehavior === "checkboxes" ? "✅" : "🔀"} ${s.name || "Nhóm Có/Không"}`}>
                                              <option value={`yes_no:${s.id}:yes`}>↳ Khi Có: {s.name}</option>
                                              <option value={`yes_no:${s.id}:no`}>↳ Khi Không: {s.name}</option>
                                              <option value={`yes_no:${s.id}:always`}>↳ Luôn hỏi</option>
                                            </optgroup>
                                          );
                                        }
                                        if (s.mode === "one_of") {
                                          if (s.oneOfStyle === "branches") {
                                            return (
                                              <optgroup key={s.id} label={`◉ ${s.name || "Nhóm Hoặc"}`}>
                                                {s.branches.map(b => (
                                                  <option key={b.id} value={`branch:${s.id}:${b.id}`}>↳ Nhánh: {b.name || "Chưa đặt tên"}</option>
                                                ))}
                                              </optgroup>
                                            );
                                          }
                                          return <option key={s.id} value={`one_of:${s.id}`}>◉ Hoặc: {s.name || "Chọn 1"}</option>;
                                        }
                                        return null;
                                      })}
                                    </select>
                                  </div>

                                  {/* Checkbox Bắt buộc */}
                                  <label style={{ display: "flex", alignItems: "center", gap: 4, fontSize: "0.72rem", cursor: "pointer", color: "#374151" }}>
                                    <input
                                      type="checkbox"
                                      checked={field.required !== false}
                                      onChange={(e) => {
                                        const checked = e.target.checked;
                                        setEditFields(prev => prev.map(item => item.key === field.key ? { ...item, required: checked } : item));
                                      }}
                                    />
                                    Bắt buộc
                                  </label>

                                  <span style={{ fontSize: "0.68rem", color: "#94a3b8", marginLeft: "auto" }}>
                                    {field.key}
                                  </span>

                                  {/* Nút ⋯ Thêm / ▴ Bớt */}
                                  <button
                                    type="button"
                                    onClick={() => setEditAdvancedOpen(prev => ({ ...prev, [field.key]: !advOpen }))}
                                    style={{
                                      border: `1px solid ${hasAdvanced ? "#c084fc" : "#cbd5e1"}`,
                                      borderRadius: 4, padding: "2px 6px",
                                      background: hasAdvanced ? "#faf5ff" : "#fff",
                                      color: hasAdvanced ? "#7e22ce" : "#64748b",
                                      cursor: "pointer", fontSize: "0.7rem",
                                      display: "flex", alignItems: "center", gap: 3
                                    }}
                                  >
                                    {hasAdvanced && <span style={{ color: "#a855f7", fontWeight: "bold" }}>●</span>}
                                    {advOpen ? "▴ Bớt" : "⋯ Thêm"}
                                  </button>
                                </div>

                                {/* Drawer mở rộng nâng cao */}
                                {advOpen && (
                                  <div style={{ marginTop: 8, paddingTop: 8, borderTop: "1px dashed #e2e8f0", display: "flex", flexDirection: "column", gap: 7 }}>
                                    <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
                                      <span style={{ fontSize: "0.7rem", color: "#64748b" }}>Nguồn:</span>
                                      <select
                                        value={field.value_source || "user_input"}
                                        onChange={(e) => {
                                          const val = e.target.value;
                                          setEditFields(prev => prev.map(item => item.key === field.key ? { ...item, value_source: val, is_auto_fill: val !== "user_input" } : item));
                                        }}
                                        style={{ padding: "3px 6px", fontSize: "0.72rem", border: "1px solid #10b981", borderRadius: 4, background: "#ecfdf5", color: "#065f46" }}
                                      >
                                        <option value="user_input">Người dùng nhập</option>
                                        <option value="ai_document">AI đọc từ hồ sơ</option>
                                        <option value="current_date">Tự lấy ngày lập đơn</option>
                                        <option value="formula">Tự tính theo công thức</option>
                                      </select>

                                      {field.value_source === "formula" && (
                                        <input
                                          value={field.calculation_formula || ""}
                                          onChange={(e) => {
                                            const val = e.target.value;
                                            setEditFields(prev => prev.map(item => item.key === field.key ? { ...item, calculation_formula: val } : item));
                                          }}
                                          placeholder="Công thức, VD: [45] * 0.02"
                                          style={{ flex: 1, minWidth: 150, padding: "3px 6px", fontSize: "0.72rem", border: "1px solid #86efac", borderRadius: 4, background: "#f0fdf4" }}
                                        />
                                      )}
                                    </div>

                                    <div>
                                      <input
                                        value={field.description || ""}
                                        onChange={(e) => {
                                          const val = e.target.value;
                                          setEditFields(prev => prev.map(item => item.key === field.key ? { ...item, description: val } : item));
                                        }}
                                        placeholder="Mô tả / Điều kiện bổ sung (VD: Chỉ điền nếu không có MST)"
                                        style={{ width: "100%", padding: "4px 8px", fontSize: "0.72rem", border: "1px solid #cbd5e1", borderRadius: 4 }}
                                      />
                                    </div>
                                  </div>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )}

                    {/* TAB 2: QUẢN LÝ NHÓM LOGIC & RẼ NHÁNH */}
                    {editTab === "groups" && (
                      <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12, position: "sticky", top: 40, zIndex: 11, background: "#f8fafc", padding: "8px 0" }}>
                          <div>
                            <h4 style={{ margin: 0, color: "#1e293b", fontSize: "0.92rem", fontWeight: 700 }}>
                              Nhóm Logic & Rẽ nhánh ({editSections.length})
                            </h4>
                            <p style={{ margin: "2px 0 0", fontSize: "0.72rem", color: "#64748b" }}>
                              Gom cụm câu hỏi hoặc tạo điều kiện Có/Không cho chatbot
                            </p>
                          </div>

                          <div style={{ position: "relative" }}>
                            <button
                              type="button"
                              onClick={() => setEditGroupMenuOpen(!editGroupMenuOpen)}
                              style={{
                                border: "none", borderRadius: 8, padding: "7px 14px",
                                background: "linear-gradient(135deg, #4f46e5 0%, #6366f1 100%)",
                                color: "#fff", cursor: "pointer", fontSize: "0.78rem",
                                fontWeight: 600, display: "inline-flex", alignItems: "center", gap: 6,
                                whiteSpace: "nowrap", flexShrink: 0,
                                boxShadow: "0 2px 6px rgba(79, 70, 229, 0.3)",
                                transition: "all 0.15s ease"
                              }}
                            >
                              <Plus size={14} strokeWidth={2.5} />
                              <span>Thêm nhóm logic</span>
                              <ChevronDown size={13} strokeWidth={2.5} style={{ opacity: 0.85 }} />
                            </button>
                            {editGroupMenuOpen && (
                              <div style={{
                                position: "absolute", zIndex: 20, right: 0, top: "calc(100% + 4px)",
                                width: 270, padding: 6, border: "1px solid #e2e8f0", borderRadius: 8,
                                background: "#ffffff", boxShadow: "0 10px 25px rgba(0,0,0,.1)"
                              }}>
                                {([
                                  ["always", "🟢 Cụm thông tin", "Hỏi theo thứ tự, có câu dẫn giới thiệu"],
                                  ["yes_no_none", "🔀 Có/Không (mở nhánh)", "Nếu Không thì bỏ qua nhóm, không ghi PDF"],
                                  ["yes_no_tick", "✅ Có/Không (tự tick PDF)", "Hỏi Có/Không rồi tự đánh dấu vào 2 ô checkbox"],
                                  ["one_of", "◉ Chỉ cần một (Hoặc)", "Chỉ cần trả lời 1 trong nhiều trường con"]
                                ] as const).map(([preset, title, desc]) => (
                                  <button
                                    key={preset}
                                    type="button"
                                    onClick={() => addEditSectionPreset(preset)}
                                    style={{
                                      display: "block", width: "100%", padding: "8px 10px",
                                      border: 0, background: "transparent", textAlign: "left",
                                      color: "#1e293b", cursor: "pointer", borderRadius: 6,
                                      transition: "background 0.15s"
                                    }}
                                    onMouseOver={(e) => e.currentTarget.style.background = "#f1f5f9"}
                                    onMouseOut={(e) => e.currentTarget.style.background = "transparent"}
                                  >
                                    <div style={{ fontSize: "0.78rem", fontWeight: 700, color: "#1e293b" }}>{title}</div>
                                    <div style={{ fontSize: "0.7rem", color: "#64748b", marginTop: 2 }}>{desc}</div>
                                  </button>
                                ))}
                              </div>
                            )}
                          </div>
                        </div>

                        {/* Empty state */}
                        {editSections.length === 0 && (
                          <div style={{
                            padding: "24px 16px", textAlign: "center", border: "1px dashed #cbd5e1",
                            borderRadius: 8, background: "#f8fafc", color: "#64748b", fontSize: "0.78rem"
                          }}>
                            <Layers size={28} style={{ color: "#94a3b8", margin: "0 auto 8px" }} />
                            <strong style={{ display: "block", color: "#334155", marginBottom: 4 }}>Chưa có nhóm logic nào</strong>
                            <p style={{ margin: "0 0 12px", fontSize: "0.74rem", color: "#64748b", lineHeight: 1.4 }}>
                              Mặc định các ô sẽ được AI hỏi tuần tự từ trên xuống dưới. Nhấn <strong>"+ Thêm nhóm logic"</strong> để gom nhóm hoặc chia nhánh.
                            </p>
                          </div>
                        )}

                        {/* Group Cards List */}
                        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                          {editSections.map(section => {
                            const memberKeys = section.mode === "one_of" && section.oneOfStyle === "branches"
                              ? section.branches.flatMap(branch => branch.fieldIds)
                              : physicalFields.filter(f => (section.mode === "one_of" ? f.alternative_group_id : f.section_id) === section.id).map(f => f.key);
                            const isCollapsed = editCollapsedSections[section.id] ?? false;

                            return (
                              <div key={section.id} style={{
                                border: "1px solid #e2e8f0",
                                borderRadius: 8,
                                background: "#ffffff",
                                boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
                                overflow: "hidden"
                              }}>
                                {/* Group Card Header */}
                                <div style={{
                                  padding: "10px 12px",
                                  background: section.mode === "always" ? "#f0fdf4" : section.mode === "yes_no" ? "#eff6ff" : "#fff7ed",
                                  borderBottom: isCollapsed ? "none" : "1px solid #f1f5f9",
                                  display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8
                                }}>
                                  <div style={{ display: "flex", alignItems: "center", gap: 6, minWidth: 0, flex: 1 }}>
                                    <span style={{
                                      fontSize: "0.7rem", fontWeight: 700, padding: "2px 6px", borderRadius: 4,
                                      background: "#fff",
                                      color: section.mode === "always" ? "#16a34a" : section.mode === "yes_no" ? "#2563eb" : "#ea580c",
                                      border: `1px solid ${section.mode === "always" ? "#bbf7d0" : section.mode === "yes_no" ? "#bfdbfe" : "#fed7aa"}`,
                                      flexShrink: 0
                                    }}>
                                      {section.mode === "always" ? "🟢 Cụm" : section.mode === "yes_no" ? (section.pdfBehavior === "checkboxes" ? "✅ Tick PDF" : "🔀 Có/Không") : "◉ Hoặc"}
                                    </span>
                                    <span style={{ fontSize: "0.82rem", fontWeight: 700, color: "#1e293b", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                                      {section.name || "(Chưa đặt tên nhóm)"}
                                    </span>
                                    <span style={{
                                      fontSize: "0.68rem",
                                      padding: "1px 6px",
                                      borderRadius: 10,
                                      background: memberKeys.length > 0 ? "#e2e8f0" : "#fef3c7",
                                      color: memberKeys.length > 0 ? "#475569" : "#b45309",
                                      fontWeight: 600,
                                      flexShrink: 0
                                    }}>
                                      {memberKeys.length > 0 ? `${memberKeys.length} trường` : "Chưa có trường nào"}
                                    </span>
                                  </div>

                                  <div style={{ display: "flex", alignItems: "center", gap: 6, flexShrink: 0 }}>
                                    <button
                                      type="button"
                                      onClick={() => setEditCollapsedSections({ ...editCollapsedSections, [section.id]: !isCollapsed })}
                                      style={{
                                        border: "1px solid #cbd5e1", borderRadius: 4, padding: "3px 8px",
                                        background: "#fff", color: "#475569", fontSize: "0.7rem",
                                        fontWeight: 500, cursor: "pointer", display: "flex", alignItems: "center", gap: 3
                                      }}
                                    >
                                      {isCollapsed ? "Chi tiết ▾" : "Thu gọn ▴"}
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() => removeEditSection(section.id)}
                                      style={{
                                        border: 0, background: "transparent", color: "#ef4444",
                                        fontSize: "0.72rem", cursor: "pointer", padding: "3px 5px",
                                        borderRadius: 4
                                      }}
                                      title="Xóa nhóm này"
                                    >
                                      <Trash2 size={14} />
                                    </button>
                                  </div>
                                </div>

                                {/* Group Card Body */}
                                {!isCollapsed && (
                                  <div style={{ padding: "12px", display: "flex", flexDirection: "column", gap: 10 }}>
                                    <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 8 }}>
                                      <div>
                                        <label style={{ display: "block", fontSize: "0.7rem", fontWeight: 600, color: "#475569", marginBottom: 3 }}>
                                          Tên nhóm logic:
                                        </label>
                                        <input
                                          value={section.name}
                                          onChange={e => {
                                            const val = e.target.value;
                                            setEditSections(prev => prev.map(s => s.id === section.id ? { ...s, name: val } : s));
                                            setEditFields(prev => prev.map(f => {
                                              if (f.alternative_group_id === section.id) return { ...f, alternative_group_name: val };
                                              if (f.condition_group_id === section.id) return { ...f, condition_group_name: val };
                                              if (f.section_id === section.id) return { ...f, section_name: val };
                                              return f;
                                            }));
                                          }}
                                          placeholder="VD: Thông tin thửa đất"
                                          style={{ width: "100%", padding: "6px 8px", border: "1px solid #cbd5e1", borderRadius: 5, fontSize: "0.78rem" }}
                                        />
                                      </div>
                                      <div>
                                        <label style={{ display: "block", fontSize: "0.7rem", fontWeight: 600, color: "#475569", marginBottom: 3 }}>
                                          Loại nhóm:
                                        </label>
                                        <select
                                          value={section.mode}
                                          onChange={e => {
                                            const mode = e.target.value as "always" | "yes_no" | "one_of";
                                            setEditSections(prev => prev.map(s => s.id === section.id ? { ...s, mode } : s));
                                          }}
                                          style={{ padding: "6px 8px", border: "1px solid #cbd5e1", borderRadius: 5, fontSize: "0.78rem", background: "#fff" }}
                                        >
                                          <option value="always">🟢 Cụm thông tin</option>
                                          <option value="yes_no">🔀 Có/Không</option>
                                          <option value="one_of">◉ Chỉ cần một (Hoặc)</option>
                                        </select>
                                      </div>
                                    </div>

                                    <div>
                                      <label style={{ display: "block", fontSize: "0.7rem", fontWeight: 600, color: "#475569", marginBottom: 3 }}>
                                        {section.mode === "always" ? "Câu dẫn trước cụm:" : section.mode === "yes_no" ? "Câu hỏi Có/Không của AI:" : "Câu hỏi chọn một:"}
                                      </label>
                                      <input
                                        value={section.question}
                                        onChange={e => {
                                          const val = e.target.value;
                                          setEditSections(prev => prev.map(s => s.id === section.id ? { ...s, question: val } : s));
                                          if (section.mode === "always") {
                                            setEditFields(prev => prev.map(f => f.section_id === section.id ? { ...f, question_group: val } : f));
                                          }
                                        }}
                                        placeholder={
                                          section.mode === "always"
                                            ? "VD: Sau đây là thông tin về thửa đất:"
                                            : section.mode === "yes_no"
                                              ? "VD: Bạn đã có giấy chứng nhận quyền sử dụng đất chưa?"
                                              : "VD: Bạn muốn dùng loại giấy tờ nào?"
                                        }
                                        style={{ width: "100%", padding: "6px 8px", border: "1px solid #cbd5e1", borderRadius: 5, fontSize: "0.78rem" }}
                                      />
                                    </div>

                                    {/* One_of Branches Config */}
                                    {section.mode === "one_of" && (
                                      <div style={{ padding: "9px 10px", background: "#fff7ed", border: "1px solid #fed7aa", borderRadius: 6, display: "flex", flexDirection: "column", gap: 8 }}>
                                        <div>
                                          <label style={{ display: "block", fontSize: "0.7rem", fontWeight: 700, color: "#9a3412", marginBottom: 4 }}>Cấu trúc lựa chọn:</label>
                                          <select
                                            value={section.oneOfStyle}
                                            onChange={e => {
                                              const oneOfStyle = e.target.value as "fields" | "branches";
                                              setEditSections(prev => prev.map(item => {
                                                if (item.id !== section.id) return item;
                                                if (oneOfStyle === "branches" && item.branches.length === 0) {
                                                  const stamp = Date.now();
                                                  return { ...item, oneOfStyle, branches: [
                                                    { id: `branch_${stamp}_1`, name: "Phương án 1", fieldIds: [] },
                                                    { id: `branch_${stamp}_2`, name: "Phương án 2", fieldIds: [] },
                                                  ] };
                                                }
                                                return { ...item, oneOfStyle };
                                              }));
                                            }}
                                            style={{ width: "100%", padding: "6px 8px", border: "1px solid #fdba74", borderRadius: 5, fontSize: "0.75rem", background: "#fff", color: "#7c2d12", fontWeight: 600 }}
                                          >
                                            <option value="fields">Mỗi lựa chọn là một trường đơn</option>
                                            <option value="branches">Mỗi lựa chọn là một nhánh có nhiều trường con</option>
                                          </select>
                                        </div>

                                        {section.oneOfStyle === "branches" && (
                                          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                                            <div style={{ fontSize: "0.69rem", color: "#9a3412", lineHeight: 1.4 }}>
                                              AI hỏi câu chọn một ở trên đúng một lần, sau đó chỉ hỏi các trường trong nhánh người dùng chọn.
                                            </div>
                                            {section.branches.map((branch, branchIndex) => (
                                              <div key={branch.id} style={{ padding: 8, background: "#fff", border: "1px solid #fed7aa", borderRadius: 6 }}>
                                                <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6 }}>
                                                  <span style={{ fontSize: "0.68rem", color: "#c2410c", fontWeight: 700, whiteSpace: "nowrap" }}>Nhánh {branchIndex + 1}</span>
                                                  <input
                                                    value={branch.name}
                                                    onChange={e => {
                                                      const val = e.target.value;
                                                      setEditSections(prev => prev.map(item => item.id === section.id ? {
                                                        ...item,
                                                        branches: item.branches.map(candidate => candidate.id === branch.id ? { ...candidate, name: val } : candidate),
                                                      } : item));
                                                      setEditFields(prev => prev.map(f => {
                                                        if (f.alternative_group_id === section.id && branch.fieldIds.includes(f.key)) {
                                                          return { ...f, alternative_branch_name: val, depends_on: { field: `section_condition_${section.id}`, value: val } };
                                                        }
                                                        return f;
                                                      }));
                                                    }}
                                                    placeholder="VD: Dùng mã số thuế"
                                                    style={{ flex: 1, minWidth: 0, padding: "5px 7px", border: "1px solid #fdba74", borderRadius: 4, fontSize: "0.73rem" }}
                                                  />
                                                  <button
                                                    type="button"
                                                    disabled={section.branches.length <= 2}
                                                    onClick={() => setEditSections(prev => prev.map(item => item.id === section.id ? { ...item, branches: item.branches.filter(candidate => candidate.id !== branch.id) } : item))}
                                                    title={section.branches.length <= 2 ? "Nhóm Hoặc cần ít nhất 2 nhánh" : "Xóa nhánh"}
                                                    style={{ border: 0, background: "transparent", color: section.branches.length <= 2 ? "#cbd5e1" : "#ef4444", cursor: section.branches.length <= 2 ? "not-allowed" : "pointer", padding: 3 }}
                                                  >
                                                    <Trash2 size={13} />
                                                  </button>
                                                </div>
                                                <details>
                                                  <summary style={{ cursor: "pointer", fontSize: "0.69rem", fontWeight: 600, color: "#c2410c" }}>
                                                    Chọn trường con ({branch.fieldIds.length} trường) ▾
                                                  </summary>
                                                  <div style={{ marginTop: 6, maxHeight: 150, overflowY: "auto", display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 4, padding: 6, background: "#fffaf5", borderRadius: 5 }}>
                                                    {physicalFields.map((f, fIdx) => {
                                                      const belongs = branch.fieldIds.includes(f.key);
                                                      const belongsToOtherBranch = section.branches.some(candidate => candidate.id !== branch.id && candidate.fieldIds.includes(f.key));
                                                      return (
                                                        <label key={f.key} style={{ display: "flex", alignItems: "center", gap: 5, padding: "3px 5px", borderRadius: 4, border: `1px solid ${belongs ? "#fb923c" : "#e2e8f0"}`, background: belongs ? "#ffedd5" : "#fff", color: "#334155", cursor: "pointer", minWidth: 0 }}>
                                                          <input
                                                            type="checkbox"
                                                            checked={belongs}
                                                            onChange={e => toggleEditGroupMember(section, f.key, e.target.checked, branch.id)}
                                                          />
                                                          <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontSize: "0.72rem" }}>#{fIdx + 1} · {f.name || f.key}</span>
                                                          {belongsToOtherBranch && !belongs && <span title="Đang ở nhánh khác" style={{ marginLeft: "auto", color: "#f97316", fontSize: "0.7rem" }}>↔</span>}
                                                        </label>
                                                      );
                                                    })}
                                                  </div>
                                                </details>
                                              </div>
                                            ))}
                                            <button
                                              type="button"
                                              onClick={() => setEditSections(prev => prev.map(item => item.id === section.id ? { ...item, branches: [...item.branches, { id: `branch_${Date.now()}`, name: `Phương án ${item.branches.length + 1}`, fieldIds: [] }] } : item))}
                                              style={{ alignSelf: "flex-start", border: "1px dashed #fb923c", borderRadius: 5, background: "#fff", color: "#c2410c", padding: "5px 9px", fontSize: "0.7rem", fontWeight: 700, cursor: "pointer" }}
                                            >
                                              + Thêm nhánh lựa chọn
                                            </button>
                                          </div>
                                        )}
                                      </div>
                                    )}

                                    {/* Yes/No PDF Behavior */}
                                    {section.mode === "yes_no" && (
                                      <div style={{ padding: "8px 10px", background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 6, display: "flex", flexDirection: "column", gap: 6 }}>
                                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                                          <span style={{ fontSize: "0.72rem", fontWeight: 600, color: "#475569" }}>Kết quả trên PDF:</span>
                                          <select
                                            value={section.pdfBehavior}
                                            onChange={e => {
                                              const pdfBehavior = e.target.value as "none" | "checkboxes";
                                              setEditSections(prev => prev.map(item => item.id === section.id ? { ...item, pdfBehavior } : item));
                                            }}
                                            style={{ padding: "4px 8px", border: "1px solid #cbd5e1", borderRadius: 4, fontSize: "0.74rem", background: "#fff" }}
                                          >
                                            <option value="none">Không ghi gì trên PDF</option>
                                            <option value="checkboxes">Tự tick checkbox theo câu trả lời</option>
                                          </select>
                                        </div>
                                        {section.pdfBehavior === "checkboxes" && (
                                          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 2 }}>
                                            <select
                                              value={section.tickYesField}
                                              onChange={e => {
                                                const tickYesField = e.target.value;
                                                setEditSections(prev => prev.map(item => item.id === section.id ? { ...item, tickYesField } : item));
                                              }}
                                              style={{ flex: 1, minWidth: 140, padding: "5px 7px", border: "1px solid #86efac", borderRadius: 4, fontSize: "0.72rem", background: "#f0fdf4" }}
                                            >
                                              <option value="">Ô tick khi CÓ...</option>
                                              {physicalFields.filter(f => f.key !== section.tickNoField).map((f, fIdx) => (
                                                <option key={f.key} value={f.key}>
                                                  #{fIdx + 1} · {f.name || f.key}
                                                </option>
                                              ))}
                                            </select>
                                            <select
                                              value={section.tickNoField}
                                              onChange={e => {
                                                const tickNoField = e.target.value;
                                                setEditSections(prev => prev.map(item => item.id === section.id ? { ...item, tickNoField } : item));
                                              }}
                                              style={{ flex: 1, minWidth: 140, padding: "5px 7px", border: "1px solid #fca5a5", borderRadius: 4, fontSize: "0.72rem", background: "#fef2f2" }}
                                            >
                                              <option value="">Ô tick khi KHÔNG...</option>
                                              {physicalFields.filter(f => f.key !== section.tickYesField).map((f, fIdx) => (
                                                <option key={f.key} value={f.key}>
                                                  #{fIdx + 1} · {f.name || f.key}
                                                </option>
                                              ))}
                                            </select>
                                          </div>
                                        )}
                                      </div>
                                    )}

                                    {/* Field Assignment Checklist */}
                                    {!(section.mode === "one_of" && section.oneOfStyle === "branches") && (
                                      <details>
                                        <summary style={{ cursor: "pointer", color: "#4f46e5", fontWeight: 600, padding: "4px 0", fontSize: "0.75rem" }}>
                                          {section.mode === "yes_no" ? "Gán trường vào nhánh Có / Không / Luôn hỏi ▾" : `Gán các trường vào nhóm (${memberKeys.length} trường đã chọn) ▾`}
                                        </summary>
                                        <div style={{ marginTop: 6, maxHeight: 180, overflowY: "auto", display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 5, padding: 8, background: "#f8fafc", borderRadius: 6, border: "1px solid #e2e8f0" }}>
                                          {physicalFields.map((f, fIdx) => {
                                            const belongs = memberKeys.includes(f.key);
                                            const isResultCheckbox = section.mode === "yes_no" && (section.tickYesField === f.key || section.tickNoField === f.key);
                                            return (
                                              <div
                                                key={f.key}
                                                style={{
                                                  display: "flex", alignItems: "center", gap: 4, minWidth: 0,
                                                  padding: "3px 6px", borderRadius: 4,
                                                  background: belongs ? "#ede9fe" : "#ffffff",
                                                  border: `1px solid ${belongs ? "#c4b5fd" : "#e2e8f0"}`,
                                                  color: isResultCheckbox ? "#94a3b8" : "#334155"
                                                }}
                                              >
                                                <label style={{ display: "flex", alignItems: "center", gap: 5, cursor: isResultCheckbox ? "not-allowed" : "pointer", minWidth: 0, flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                                                  <input
                                                    type="checkbox"
                                                    disabled={isResultCheckbox}
                                                    checked={belongs}
                                                    onChange={e => toggleEditGroupMember(section, f.key, e.target.checked)}
                                                  />
                                                  <span style={{ overflow: "hidden", textOverflow: "ellipsis", fontSize: "0.72rem" }}>#{fIdx + 1} · {f.name || f.key}</span>
                                                </label>
                                                {section.mode === "yes_no" && belongs && (
                                                  <select
                                                    value={f.condition_behavior || "yes"}
                                                    onChange={e => toggleEditGroupMember(section, f.key, true, undefined, e.target.value as "yes" | "no" | "always")}
                                                    style={{ padding: "2px 4px", fontSize: "0.68rem", border: "1px solid #a5b4fc", borderRadius: 4, background: "#fff", color: "#3730a3" }}
                                                  >
                                                    <option value="yes">Khi Có</option>
                                                    <option value="no">Khi Không</option>
                                                    <option value="always">Luôn hỏi</option>
                                                  </select>
                                                )}
                                              </div>
                                            );
                                          })}
                                        </div>
                                      </details>
                                    )}
                                  </div>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )}

                    {/* TAB 3: LUỒNG AI SIMULATION */}
                    {editTab === "flow" && (
                      <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
                        <div style={{ marginBottom: 12, position: "sticky", top: 40, zIndex: 11, background: "#f8fafc", padding: "8px 0" }}>
                          <h4 style={{ margin: 0, color: "#1e293b", fontSize: "0.92rem", fontWeight: 700 }}>
                            Mô phỏng Luồng AI Trò chuyện
                          </h4>
                          <p style={{ margin: "2px 0 0", fontSize: "0.72rem", color: "#64748b" }}>
                            Trình tự chatbot hỏi người dân để thu thập thông tin và tự động điền vào biểu mẫu
                          </p>
                        </div>

                        <div style={{ display: "flex", flexDirection: "column", gap: 10, position: "relative", paddingLeft: 24 }}>
                          {/* Vertical timeline line */}
                          <div style={{ position: "absolute", left: 10, top: 12, bottom: 20, width: 2, background: "#e2e8f0", zIndex: 0 }} />

                          {(() => {
                            const sectionMembers = (sec: FormSection) => sec.mode === "one_of" && sec.oneOfStyle === "branches"
                              ? physicalFields.filter(f => sec.branches.some(branch => branch.fieldIds.includes(f.key)))
                              : physicalFields.filter(f => (sec.mode === "one_of" ? f.alternative_group_id : f.section_id) === sec.id);
                            
                            const sectionByField = new Map<string, FormSection>();
                            editSections.forEach(sec => sectionMembers(sec).forEach(f => sectionByField.set(f.key, sec)));
                            const resultTickIds = new Set(editSections.flatMap(sec => [sec.tickYesField, sec.tickNoField]).filter(Boolean));

                            const entries: Array<{ order: number; kind: "field"; field: typeof physicalFields[number]; num: number } | { order: number; kind: "section"; section: FormSection; members: typeof physicalFields }> = [];

                            editSections.forEach((sec, idx) => {
                              const members = sectionMembers(sec);
                              const firstIdx = physicalFields.findIndex(f => members.some(m => m.key === f.key));
                              entries.push({ order: firstIdx >= 0 ? firstIdx + 1 : (physicalFields.length + idx + 1), kind: "section", section: sec, members });
                            });

                            physicalFields.forEach((field, fIdx) => {
                              if (!sectionByField.has(field.key) && !resultTickIds.has(field.key)) {
                                entries.push({ order: fIdx + 1, kind: "field", field, num: fIdx + 1 });
                              }
                            });

                            entries.sort((a, b) => a.order - b.order || (a.kind === "section" ? -1 : 1));

                            return entries.map((entry, index) => {
                              if (entry.kind === "field") {
                                const field = entry.field;
                                const isAuto = field.value_source && field.value_source !== "user_input";
                                const parent = physicalFields.find(item => item.key === (typeof field.depends_on === "object" ? field.depends_on?.field : field.depends_on));
                                return (
                                  <div key={`flow-field-${field.key}`} style={{ position: "relative", zIndex: 1 }}>
                                    <div style={{ position: "absolute", left: -21, top: 6, width: 16, height: 16, borderRadius: "50%", background: isAuto ? "#0891b2" : "#64748b", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "0.55rem", fontWeight: 700, boxShadow: "0 0 0 3px #fff" }}>
                                      {index + 1}
                                    </div>
                                    <div style={{ background: isAuto ? "#ecfeff" : "#fff", border: `1px solid ${isAuto ? "#a5f3fc" : "#e2e8f0"}`, borderRadius: 8, padding: "8px 10px" }}>
                                      <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                                        <strong style={{ fontSize: "0.76rem", color: "#1e293b" }}>#{entry.num} · {field.name || field.key}</strong>
                                        <span style={{ marginLeft: "auto", fontSize: "0.66rem", color: isAuto ? "#0e7490" : "#64748b", fontWeight: 600 }}>
                                          {isAuto ? "Tự điền · không hỏi" : "AI hỏi"}
                                        </span>
                                      </div>
                                      {parent && <div style={{ marginTop: 4, fontSize: "0.69rem", color: "#7c3aed" }}>↳ Chỉ hỏi khi trường "{parent.name || parent.key}" thỏa điều kiện</div>}
                                    </div>
                                  </div>
                                );
                              }

                              const { section, members } = entry;
                              const isYesNo = section.mode === "yes_no";
                              const isOneOf = section.mode === "one_of";
                              const memberText = (items: typeof physicalFields) => items.map(f => f.name || f.key).join(" → ") || "chưa có trường";

                              return (
                                <div key={`flow-section-${section.id}`} style={{ position: "relative", zIndex: 1 }}>
                                  <div style={{ position: "absolute", left: -21, top: 6, width: 16, height: 16, borderRadius: "50%", background: isYesNo ? "#2563eb" : isOneOf ? "#ea580c" : "#16a34a", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "0.55rem", fontWeight: 700, boxShadow: "0 0 0 3px #fff" }}>
                                    {index + 1}
                                  </div>
                                  <div style={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 8, padding: "10px 12px", boxShadow: "0 1px 3px rgba(0,0,0,0.03)" }}>
                                    <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 5 }}>
                                      <span style={{ fontSize: "0.68rem", fontWeight: 700, color: isYesNo ? "#2563eb" : isOneOf ? "#ea580c" : "#16a34a" }}>
                                        {isYesNo ? "🔀 Có/Không" : isOneOf ? "◉ Chọn một" : "🟢 Cụm"}
                                      </span>
                                      <strong style={{ fontSize: "0.78rem", color: "#1e293b" }}>{section.name || "(Chưa đặt tên)"}</strong>
                                      <span style={{ marginLeft: "auto", fontSize: "0.66rem", color: "#64748b" }}>{members.length} trường</span>
                                    </div>
                                    <div style={{ fontSize: "0.73rem", color: "#334155", background: "#f8fafc", padding: "6px 8px", borderRadius: 5, marginBottom: 6 }}>
                                      🗣️ AI hỏi một lần: “{section.question || (isYesNo
                                        ? `Bạn có ${section.name || "thông tin này"} không?`
                                        : isOneOf
                                          ? `Bạn muốn chọn ${(section.oneOfStyle === "branches" ? section.branches.map(b => b.name) : members.map(m => m.name)).join(" hay ")}?`
                                          : `Sau đây là ${section.name || "các thông tin cần cung cấp"}:`)}”
                                    </div>
                                    {isYesNo ? (
                                      <div style={{ display: "grid", gap: 4, fontSize: "0.69rem" }}>
                                        <div style={{ padding: "4px 7px", background: "#f0fdf4", borderRadius: 4, color: "#166534" }}><strong>Khi CÓ:</strong> {memberText(members.filter(f => (f.condition_behavior || "yes") === "yes"))}</div>
                                        <div style={{ padding: "4px 7px", background: "#fef2f2", borderRadius: 4, color: "#991b1b" }}><strong>Khi KHÔNG:</strong> {members.some(f => f.condition_behavior === "no") ? memberText(members.filter(f => f.condition_behavior === "no")) : "Bỏ qua"}</div>
                                        {members.some(f => f.condition_behavior === "always") && <div style={{ padding: "4px 7px", background: "#f8fafc", borderRadius: 4, color: "#475569" }}><strong>Luôn hỏi:</strong> {memberText(members.filter(f => f.condition_behavior === "always"))}</div>}
                                      </div>
                                    ) : isOneOf && section.oneOfStyle === "branches" ? (
                                      <div style={{ display: "grid", gap: 4, fontSize: "0.69rem" }}>
                                        {section.branches.map(b => (
                                          <div key={b.id} style={{ padding: "4px 7px", background: "#fff7ed", borderRadius: 4, color: "#9a3412" }}>
                                            <strong>{b.name || "Nhánh chưa đặt tên"}:</strong> {memberText(physicalFields.filter(f => b.fieldIds.includes(f.key)))}
                                          </div>
                                        ))}
                                      </div>
                                    ) : (
                                      <div style={{ fontSize: "0.69rem", color: "#475569", lineHeight: 1.5 }}>
                                        {isOneOf ? "Chọn một trong: " : "Sau câu dẫn, hỏi lần lượt: "}{memberText(members)}
                                      </div>
                                    )}
                                    {section.pdfBehavior === "checkboxes" && <div style={{ marginTop: 5, fontSize: "0.67rem", color: "#0369a1" }}>✓ Câu trả lời tự tick ô Có/Không trên PDF; hai ô kết quả không được hỏi lại.</div>}
                                  </div>
                                </div>
                              );
                            });
                          })()}

                          {/* Completion Node */}
                          <div style={{ position: "relative", zIndex: 1 }}>
                            <div style={{ position: "absolute", left: -21, top: 6, width: 16, height: 16, borderRadius: "50%", background: "#10b981", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", boxShadow: "0 0 0 3px #fff" }}>
                              <Check size={10} />
                            </div>
                            <div style={{ background: "#ecfdf5", border: "1px solid #a7f3d0", borderRadius: 8, padding: "10px 12px" }}>
                              <strong style={{ fontSize: "0.78rem", color: "#047857", display: "block" }}>
                                Hoàn tất kê khai
                              </strong>
                              <p style={{ margin: "2px 0 0", fontSize: "0.72rem", color: "#065f46" }}>
                                AI tổng hợp dữ liệu, tự động điền vào phôi Word và xuất file PDF chuẩn cho người dân.
                              </p>
                            </div>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Panel Footer */}
                  <div style={{ padding: "12px 20px", background: "#ffffff", borderTop: "1px solid #e2e8f0", display: "flex", justifyContent: "space-between", alignItems: "center", flexShrink: 0 }}>
                    <button type="button" className="secondary-button" onClick={closeEdit} style={{ padding: "8px 16px", borderRadius: 6, border: "1px solid #cbd5e1", background: "#fff", color: "#475569", fontWeight: 600, fontSize: "0.8rem", cursor: "pointer" }}>
                      Hủy bỏ
                    </button>
                    <button
                      type="submit"
                      disabled={editSaving}
                      style={{
                        padding: "8px 22px", borderRadius: 8, border: "none",
                        background: "linear-gradient(135deg, #10b981 0%, #059669 100%)",
                        color: "#fff", fontWeight: 700, fontSize: "0.84rem",
                        cursor: editSaving ? "not-allowed" : "pointer",
                        display: "inline-flex", alignItems: "center", gap: 7,
                        boxShadow: "0 2px 8px rgba(16, 185, 129, 0.35)",
                        transition: "all 0.15s ease"
                      }}
                    >
                      <Save size={15} strokeWidth={2.2} />
                      <span>{editSaving ? "Đang lưu..." : "Lưu thay đổi"}</span>
                    </button>
                  </div>
                </form>
              </div>

              {/* Draggable Resizer Bar */}
              {!editPdfOnly && (
                <div
                  onMouseDown={(e) => {
                    e.preventDefault();
                    setEditIsDraggingSplit(true);
                  }}
                  title="Kéo chuột sang trái/phải để điều chỉnh độ rộng tài liệu PDF"
                  style={{
                    width: 7,
                    cursor: "col-resize",
                    background: editIsDraggingSplit ? "#6366f1" : "#cbd5e1",
                    position: "relative",
                    flexShrink: 0,
                    transition: "background 0.15s",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    zIndex: 15,
                    userSelect: "none"
                  }}
                  onMouseOver={(e) => { if (!editIsDraggingSplit) e.currentTarget.style.background = "#94a3b8"; }}
                  onMouseOut={(e) => { if (!editIsDraggingSplit) e.currentTarget.style.background = "#cbd5e1"; }}
                >
                  <div style={{ width: 1.5, height: 28, borderRadius: 1, background: editIsDraggingSplit ? "#ffffff" : "#64748b" }} />
                </div>
              )}

              {/* Right Document Preview Section */}
              <div className="doc-preview-shell" style={{
                flex: 1,
                minWidth: 320,
                position: "relative",
                overflow: "hidden",
                display: "flex",
                flexDirection: "column",
                background: "#0f172a"
              }}>
                <div style={{
                  padding: "10px 16px",
                  background: "#1e293b",
                  color: "#f8fafc",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  flexShrink: 0,
                  borderBottom: "1px solid #334155",
                  flexWrap: "wrap",
                  gap: 8
                }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <FileText size={16} style={{ color: "#38bdf8" }} />
                    <span style={{ fontSize: "0.84rem", fontWeight: 600 }}>Tài liệu xem trước</span>
                    
                    {/* View format switcher (Images vs PDF Reader) */}
                    {editPdfUrl && (
                      <div style={{ display: "inline-flex", alignItems: "center", background: "rgba(255, 255, 255, 0.08)", borderRadius: 6, padding: 2, marginLeft: 4 }}>
                        <button
                          type="button"
                          onClick={() => setEditViewFormat("images")}
                          style={{
                            padding: "3px 8px", fontSize: "0.68rem", borderRadius: 4, border: 0,
                            background: editViewFormat === "images" ? "#38bdf8" : "transparent",
                            color: editViewFormat === "images" ? "#0f172a" : "#94a3b8",
                            fontWeight: editViewFormat === "images" ? 700 : 500, cursor: "pointer"
                          }}
                          title="Hiển thị dạng các trang A4 trực quan"
                        >
                          Trang A4
                        </button>
                        <button
                          type="button"
                          onClick={() => setEditViewFormat("pdf")}
                          style={{
                            padding: "3px 8px", fontSize: "0.68rem", borderRadius: 4, border: 0,
                            background: editViewFormat === "pdf" ? "#38bdf8" : "transparent",
                            color: editViewFormat === "pdf" ? "#0f172a" : "#94a3b8",
                            fontWeight: editViewFormat === "pdf" ? 700 : 500, cursor: "pointer"
                          }}
                          title="Xem bằng trình đọc PDF gốc (hỗ trợ in, tìm kiếm văn bản)"
                        >
                          Trình xem PDF
                        </button>
                      </div>
                    )}
                  </div>

                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    {/* Zoom controls for A4 image mode */}
                    {editViewFormat === "images" && editPageImages.length > 0 && (
                      <div style={{ display: "flex", alignItems: "center", gap: 3, background: "rgba(255, 255, 255, 0.1)", borderRadius: 6, padding: "2px 4px" }}>
                        <button
                          type="button"
                          onClick={() => {
                            setEditZoomMode("a4");
                            setEditZoom(z => Math.max(0.5, Math.round((z - 0.1) * 10) / 10));
                          }}
                          title="Thu nhỏ"
                          style={{ border: 0, background: "transparent", color: "#cbd5e1", cursor: "pointer", padding: "2px 6px", fontSize: "0.85rem", fontWeight: 700 }}
                        >
                          -
                        </button>
                        <span style={{ fontSize: "0.72rem", color: "#f8fafc", fontWeight: 600, minWidth: 38, textAlign: "center" }}>
                          {editZoomMode === "fit" ? "Vừa" : `${Math.round(editZoom * 100)}%`}
                        </span>
                        <button
                          type="button"
                          onClick={() => {
                            setEditZoomMode("a4");
                            setEditZoom(z => Math.min(2.0, Math.round((z + 0.1) * 10) / 10));
                          }}
                          title="Phóng to"
                          style={{ border: 0, background: "transparent", color: "#cbd5e1", cursor: "pointer", padding: "2px 6px", fontSize: "0.85rem", fontWeight: 700 }}
                        >
                          +
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setEditZoomMode("a4");
                            setEditZoom(1);
                          }}
                          title="Đặt kích thước trang chuẩn A4 (100%)"
                          style={{
                            border: 0,
                            background: editZoomMode === "a4" && editZoom === 1 ? "rgba(56, 189, 248, 0.25)" : "transparent",
                            color: editZoomMode === "a4" && editZoom === 1 ? "#38bdf8" : "#cbd5e1",
                            cursor: "pointer", padding: "2px 6px", fontSize: "0.68rem", fontWeight: 600, borderRadius: 4
                          }}
                        >
                          100% A4
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setEditZoomMode(m => m === "fit" ? "a4" : "fit");
                          }}
                          title="Căn vừa vặn khung xem"
                          style={{
                            border: 0,
                            background: editZoomMode === "fit" ? "rgba(56, 189, 248, 0.25)" : "transparent",
                            color: editZoomMode === "fit" ? "#38bdf8" : "#cbd5e1",
                            cursor: "pointer", padding: "2px 6px", fontSize: "0.68rem", fontWeight: 600, borderRadius: 4
                          }}
                        >
                          Vừa khung
                        </button>
                      </div>
                    )}

                    <button
                      type="button"
                      onClick={() => setEditPdfOnly(!editPdfOnly)}
                      title={editPdfOnly ? "Hiện lại bảng cấu hình (chia đôi màn hình)" : "Phóng to toàn bộ màn hình cho tài liệu PDF"}
                      style={{
                        padding: "5px 11px",
                        fontSize: "0.74rem",
                        fontWeight: 600,
                        color: editPdfOnly ? "#38bdf8" : "#f1f5f9",
                        background: editPdfOnly ? "rgba(56, 189, 248, 0.2)" : "rgba(255, 255, 255, 0.1)",
                        border: `1px solid ${editPdfOnly ? "#38bdf8" : "rgba(255, 255, 255, 0.2)"}`,
                        borderRadius: 6,
                        display: "inline-flex",
                        alignItems: "center",
                        gap: 6,
                        cursor: "pointer",
                        transition: "all 0.15s ease"
                      }}
                    >
                      {editPdfOnly ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
                      <span>{editPdfOnly ? "Hiện bảng cấu hình" : "Toàn màn hình"}</span>
                    </button>

                    {editPdfUrl && (
                      <button
                        type="button"
                        onClick={() => window.open(editPdfUrl, "_blank")}
                        title="Mở bản xem trước PDF trong tab mới của trình duyệt để soi chi tiết"
                        style={{
                          padding: "5px 11px",
                          fontSize: "0.74rem",
                          fontWeight: 600,
                          color: "#f1f5f9",
                          background: "rgba(255, 255, 255, 0.1)",
                          border: "1px solid rgba(255, 255, 255, 0.2)",
                          borderRadius: 6,
                          display: "inline-flex",
                          alignItems: "center",
                          gap: 6,
                          cursor: "pointer",
                          transition: "all 0.15s ease"
                        }}
                      >
                        <ExternalLink size={14} />
                        <span>Mở tab mới</span>
                      </button>
                    )}

                    <button type="button" className="icon-button" onClick={closeEdit} title="Đóng" style={{ color: "#cbd5e1", marginLeft: 4 }}>
                      <X size={18} />
                    </button>
                  </div>
                </div>

                {editPdfLoading ? (
                  <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", flex: 1, gap: 10, color: "#94a3b8" }}>
                    <div style={{ width: 28, height: 28, border: "2.5px solid #475569", borderTopColor: "#38bdf8", borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />
                    <span style={{ fontSize: "0.82rem" }}>Đang kết xuất bản xem trước PDF...</span>
                  </div>
                ) : editViewFormat === "pdf" && editPdfUrl ? (
                  <iframe
                    src={`${editPdfUrl}#toolbar=1&navpanes=0&view=FitH`}
                    style={{
                      width: "100%",
                      height: "100%",
                      border: "none",
                      flex: 1,
                      pointerEvents: editIsDraggingSplit ? "none" : "auto",
                      background: "#525659"
                    }}
                  />
                ) : editPageImages.length > 0 ? (
                  <div style={{
                    flex: 1,
                    overflowY: "auto",
                    overflowX: "auto",
                    padding: "24px 20px",
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    gap: 24,
                    background: "#1e293b"
                  }}>
                    {editPageImages.map((src, i) => {
                      const a4BaseWidth = 740;
                      const cardWidth = editZoomMode === "fit" ? "100%" : `${Math.round(editZoom * a4BaseWidth)}px`;
                      return (
                        <div
                          key={i}
                          style={{
                            position: "relative",
                            boxShadow: "0 12px 36px rgba(0,0,0,0.5)",
                            borderRadius: 4,
                            overflow: "hidden",
                            background: "#ffffff",
                            width: cardWidth,
                            maxWidth: editZoomMode === "fit" ? "920px" : "100%",
                            transition: "width 0.15s ease",
                            flexShrink: 0
                          }}
                        >
                          <img
                            src={src}
                            alt={`Trang ${i + 1}`}
                            style={{ display: "block", width: "100%", height: "auto" }}
                          />
                          <div style={{
                            position: "absolute",
                            bottom: 12,
                            right: 14,
                            background: "rgba(15, 23, 42, 0.8)",
                            color: "#f8fafc",
                            padding: "3px 9px",
                            borderRadius: 4,
                            fontSize: "0.72rem",
                            fontWeight: 600,
                            backdropFilter: "blur(4px)",
                            boxShadow: "0 2px 6px rgba(0,0,0,0.3)"
                          }}>
                            Trang {i + 1} / {editPageImages.length}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : editPdfUrl ? (
                  <iframe
                    src={`${editPdfUrl}#toolbar=1&navpanes=0&view=FitH`}
                    style={{
                      width: "100%",
                      height: "100%",
                      border: "none",
                      flex: 1,
                      pointerEvents: editIsDraggingSplit ? "none" : "auto",
                      background: "#525659"
                    }}
                  />
                ) : (
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "center", flex: 1, color: "#94a3b8", fontSize: "0.85rem" }}>
                    Không thể tải bản xem trước.
                  </div>
                )}
              </div>
            </div>
          </div>
        );
      })()}

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

      {/* Create Form Modal */}
      {showModal && (
        <div style={{
          position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: "rgba(0,0,0,0.65)", zIndex: 1000,
          display: "flex",
          alignItems: step === 2 ? "stretch" : "center",
          justifyContent: "center",
          padding: step === 2 ? "0" : "20px"
        }}>
          <div style={{
            backgroundColor: "#fff",
            borderRadius: step === 2 || step === 3 ? "0" : "12px",
            width: step === 2 || step === 3 ? "100%" : "550px",
            maxWidth: step === 2 || step === 3 ? "100%" : "550px",
            boxShadow: "0 10px 40px rgba(0,0,0,0.2)",
            border: step === 2 || step === 3 ? "none" : "1px solid #eee",
            maxHeight: step === 2 || step === 3 ? "100vh" : "90vh",
            overflowY: step === 2 || step === 3 ? "hidden" : "auto",
            display: "flex",
            flexDirection: "column"
          }}>
            {/* Header */}
            <div style={{
              padding: "16px 24px",
              borderBottom: "1px solid #e5e7eb",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              flexShrink: 0,
              background: step === 2 || step === 3 ? "#1e3a5f" : "#fff"
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
                {[1, 2, 3].map(s => (
                  <div key={s} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <div style={{
                      width: 28, height: 28, borderRadius: "50%", display: "flex", alignItems: "center",
                      justifyContent: "center", fontWeight: "bold", fontSize: "0.85rem",
                      background: step === 2 || step === 3 ? (step >= s ? "#3b82f6" : "#334155") : (step >= s ? "#4f46e5" : "#e0e7ff"),
                      color: step === 2 || step === 3 ? "#fff" : (step >= s ? "#fff" : "#6366f1"),
                    }}>{s}</div>
                    <span style={{ fontSize: "0.8rem", color: step === 2 || step === 3 ? "#94a3b8" : "#6b7280", fontWeight: step === s ? 600 : 400 }}>
                      {s === 1 ? "Tải tệp" : s === 2 ? "Dán nhãn" : "Đặt tên"}
                    </span>
                    {s < 3 && <span style={{ color: step === 2 || step === 3 ? "#475569" : "#d1d5db", marginLeft: 8 }}>›</span>}
                  </div>
                ))}
              </div>
              <button type="button" onClick={resetModal} style={{
                background: "none", border: 0, cursor: "pointer",
                color: step === 2 || step === 3 ? "#94a3b8" : "#6b7280", fontSize: "1.5rem", lineHeight: 1
              }}>×</button>
            </div>

            {/* Step 1: Upload File */}
            {step === 1 && (
              <div style={{ padding: "24px", overflowY: "auto" }}>
                <h3 style={{ marginBottom: 8, fontSize: "1.1rem", fontWeight: 700 }}>Bước 1: Tải lên file Word</h3>
                <p style={{ color: "#6b7280", marginBottom: 20, fontSize: "0.9rem" }}>Hệ thống sẽ phân tích tài liệu và xác định các khoảng trống cần điền.</p>
                <form onSubmit={handleAnalyzeDocx}>
                  <div style={{
                    border: "2px dashed #d1d5db", borderRadius: 8, padding: "32px 24px",
                    textAlign: "center", marginBottom: 20, cursor: "pointer"
                  }} onClick={() => document.getElementById("docx-upload-input")?.click()}>
                    <UploadCloud size={32} style={{ color: "#9ca3af", margin: "0 auto 12px" }} />
                    <p style={{ fontWeight: 600, marginBottom: 4 }}>{docxFile ? docxFile.name : "Kéo thả file Word (.docx) hoặc nhấp để chọn"}</p>
                    <p style={{ fontSize: "0.8rem", color: "#9ca3af" }}>{docxFile ? `${(docxFile.size / 1024 / 1024).toFixed(1)} MB` : "Hỗ trợ định dạng .docx"}</p>
                  </div>
                  <input id="docx-upload-input" type="file" accept=".docx,.doc" style={{ display: "none" }}
                    onChange={(e) => setDocxFile(e.target.files?.[0] ?? null)} />
                  <div style={{ display: "flex", justifyContent: "flex-end", gap: 12 }}>
                    <button type="button" onClick={resetModal} style={{ padding: "8px 16px", borderRadius: 6, border: "1px solid #d1d5db", background: "#fff", cursor: "pointer", fontWeight: 500 }}>Hủy</button>
                    <button type="submit" className="primary-button" disabled={!docxFile || uploading}>{uploading ? "Đang phân tích..." : "Phân tích & Tiếp tục"}</button>
                  </div>
                </form>
              </div>
            )}

            {/* Step 2: Label Zones */}
            {(step === 2 || step === 3) && previewData && (
              <div style={{ display: "flex", flex: 1, minHeight: 0, overflow: "hidden" }}>
                {/* Left Panel */}
                <div style={{
                  width: step === 3 ? 380 : 300, minWidth: step === 3 ? 380 : 300,
                  borderRight: "1px solid #e5e7eb", display: "flex", flexDirection: "column",
                  background: "#f9fafb", overflow: "hidden"
                }}>
                  <div style={{ padding: "12px 16px", background: "#f3f4f6", borderBottom: "1px solid #e5e7eb", flexShrink: 0 }}>
                    <div style={{ fontSize: "0.8rem", color: "#6b7280" }}>
                      Đã dán nhãn: <strong style={{ color: "#4f46e5" }}>{labeledCount}</strong> / {editableZones.length} vùng
                    </div>
                  </div>

                  <div style={{ overflowY: "auto", flex: 1, padding: "16px" }}>
                    {step === 3 ? (
                      <form id="save-form" onSubmit={handleSaveVisual}>
                        <label style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 13, fontWeight: 600, marginBottom: 14 }}>
                          Tên Biểu mẫu *
                          <input value={formName} onChange={(e) => setFormName(e.target.value)} placeholder="VD: Đơn đăng ký cấp đổi GCN"
                            style={{ width: "100%", padding: "8px", border: "1px solid #d1d5db", borderRadius: "6px" }} />
                        </label>
                        <label style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 13, fontWeight: 600, marginBottom: 14 }}>
                          Loại thủ tục *
                          <input value={procedureType} onChange={(e) => setProcedureType(e.target.value)} placeholder="VD: cap_doi"
                            style={{ width: "100%", padding: "8px", border: "1px solid #d1d5db", borderRadius: "6px" }} />
                        </label>
                        <hr style={{ margin: "20px 0", borderColor: "#e5e7eb" }} />

                        {/* FIX BUG 1: Show suggested_label hint so user knows which zone = which number */}
                        <h4 style={{ marginBottom: 8, color: "#4f46e5" }}>Thiết lập {labeledList.length} ô thông tin</h4>
                        <div style={{ fontSize: "0.78rem", color: "#475569", background: "#eff6ff", border: "1px solid #bfdbfe", borderRadius: 6, padding: "9px 10px", marginBottom: 16, lineHeight: 1.5 }}>
                          <strong>Cách dùng:</strong> Checkbox là câu <strong>Có/Không</strong>; “Chọn một đáp án” dùng khi chỉ được chọn một trạng thái. Với nhiều ô liên quan, hãy dùng <strong>Cụm thông tin</strong> để AI hỏi đúng một lần rồi mở nhánh phù hợp.
                        </div>
                        <div style={{ marginBottom: 16, padding: 10, border: "1px solid #ddd6fe", borderRadius: 8, background: "#faf5ff" }}>
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}><strong style={{ fontSize: "0.82rem", color: "#6b21a8" }}>Cụm thông tin</strong><button type="button" onClick={() => setFormSections([...formSections, { id: `section_${Date.now()}`, name: "", mode: "always", question: "" }])} style={{ border: 0, borderRadius: 5, padding: "5px 8px", background: "#7c3aed", color: "#fff", cursor: "pointer", fontSize: "0.75rem" }}>+ Thêm cụm</button></div>
                          <p style={{ fontSize: "0.72rem", color: "#6b7280", margin: "6px 0" }}>Cụm luôn hỏi là câu dẫn. Cụm Có/Không sẽ được AI hỏi một lần ngay trước ô con đầu tiên; câu trả lời không xuất hiện trên PDF.</p>
                          {formSections.map(section => <div key={section.id} style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 7 }}><input value={section.name} onChange={e => setFormSections(formSections.map(item => item.id === section.id ? { ...item, name: e.target.value } : item))} placeholder="Tên cụm, ví dụ: Địa chỉ cư trú" style={{ flex: 1, minWidth: 150, padding: "4px 7px", border: "1px solid #c4b5fd", borderRadius: 4, fontSize: "0.75rem" }}/><select value={section.mode} onChange={e => setFormSections(formSections.map(item => item.id === section.id ? { ...item, mode: e.target.value as "always" | "yes_no" } : item))} style={{ padding: 4, border: "1px solid #c4b5fd", borderRadius: 4, fontSize: "0.75rem" }}><option value="always">Không cần hỏi Có/Không</option><option value="yes_no">Hỏi Có/Không trước</option></select>{section.mode === "yes_no" && <input value={section.question} onChange={e => setFormSections(formSections.map(item => item.id === section.id ? { ...item, question: e.target.value } : item))} placeholder="Ví dụ: Có nhà cho thuê không?" style={{ flex: 1, minWidth: 170, padding: "4px 7px", border: "1px solid #c4b5fd", borderRadius: 4, fontSize: "0.75rem" }}/>}<button type="button" onClick={() => { setFormSections(formSections.filter(item => item.id !== section.id)); const next = { ...fieldSectionId }; const nextBranch = { ...fieldSectionBranch }; Object.keys(next).forEach(key => { if (next[key] === section.id) { delete next[key]; delete nextBranch[key]; } }); setFieldSectionId(next); setFieldSectionBranch(nextBranch); }} style={{ border: 0, background: "transparent", color: "#b91c1c", cursor: "pointer" }}>Xóa</button></div>)}
                        </div>
                        {labeledList.map(field => {
                          const zone = editableZones?.find((z: any) => String(z.idx) === field.blankIdx);
                          const isCheckbox = zone?.field_type === 'checkbox';
                          const selectedType = fieldType[field.id] || (isCheckbox ? "checkbox" : "text");
                          // BUG 1 FIX: Get the AI suggested label for this zone
                          const suggestedLabel = zone?.suggested_label || zone?.ai_label || "";

                          return (
                            <div key={field.id} style={{
                              marginBottom: 14, padding: "12px 14px",
                              border: `1px solid ${isCheckbox ? "#a5b4fc" : "#e5e7eb"}`,
                              borderRadius: "8px",
                              backgroundColor: isCheckbox ? "#eef2ff" : "#f9fafb"
                            }}>
                              <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
                                <div style={{ flexShrink: 0 }}>
                                  {/* Zone number badge */}
                                  <div style={{
                                    width: 26, height: 26, borderRadius: "50%",
                                    backgroundColor: isCheckbox ? "#818cf8" : "#4f46e5",
                                    color: "#fff", display: "flex", alignItems: "center",
                                    justifyContent: "center", fontWeight: "bold", fontSize: "0.8rem"
                                  }}>
                                    {field.num}
                                  </div>
                                  {/* BUG 1 FIX: Show the AI suggested label as a hint */}
                                  {suggestedLabel && (
                                    <div style={{
                                      marginTop: 4, fontSize: "0.68rem", color: "#6366f1",
                                      maxWidth: 60, wordBreak: "break-all", textAlign: "center",
                                      lineHeight: 1.2
                                    }} title={`AI gợi ý: ${suggestedLabel}`}>
                                      {suggestedLabel.length > 12 ? suggestedLabel.substring(0, 12) + "…" : suggestedLabel}
                                    </div>
                                  )}
                                </div>
                                <div style={{ flex: 1, minWidth: 0 }}>
                                  {/* BUG 1 FIX: Show full suggested label as placeholder for easier identification */}
                                  <input
                                    type="text"
                                    placeholder={isCheckbox
                                      ? `Nhãn ${field.num}${suggestedLabel ? ` (gợi ý: ${suggestedLabel})` : ""} (VD: ca_nhan_cu_tru...)`
                                      : `Nhãn ${field.num}${suggestedLabel ? ` (gợi ý: ${suggestedLabel})` : ""} (VD: Họ tên, Ngày sinh...)`}
                                    value={fieldData[field.id] !== undefined ? fieldData[field.id] : suggestedLabel}
                                    onChange={(e) => setFieldData({ ...fieldData, [field.id]: e.target.value })}
                                    style={{ width: "100%", padding: "8px", border: "1px solid #d1d5db", borderRadius: "6px" }}
                                  />
                                  
                                                                    {/* Advanced Field Options */}
                                  <div style={{ display: "flex", flexDirection: "column", gap: "10px", marginTop: "10px" }}>
                                    <div style={{ display: "flex", gap: "10px", alignItems: "center", flexWrap: "wrap" }}>
                                      <select value={fieldSectionId[field.id] || ""} onChange={e => { const sectionId = e.target.value; setFieldSectionId({ ...fieldSectionId, [field.id]: sectionId }); if (sectionId && !fieldSectionBranch[field.id]) setFieldSectionBranch({ ...fieldSectionBranch, [field.id]: "yes" }); }} title="Gom ô này vào cụm để AI hiểu đây là phần thông tin liên quan" style={{ padding: "3px 6px", fontSize: "0.75rem", border: "1px solid #c4b5fd", borderRadius: 4, background: "#faf5ff", color: "#6b21a8" }}><option value="">Không thuộc cụm</option>{formSections.filter(section => section.name.trim()).map(section => <option key={section.id} value={section.id}>Cụm: {section.name}</option>)}</select>
                                      <button type="button" title="Tạo cụm mới và đưa ô này vào cụm đó" onClick={() => { const id = `section_${Date.now()}`; setFormSections([...formSections, { id, name: "", mode: "always", question: "" }]); setFieldSectionId({ ...fieldSectionId, [field.id]: id }); }} style={{ border: 0, borderRadius: 4, padding: "3px 6px", background: "#7c3aed", color: "#fff", cursor: "pointer", fontSize: "0.75rem" }}>+ Cụm</button>
                                      {(() => { const section = formSections.find(item => item.id === fieldSectionId[field.id]); return section?.mode === "yes_no" ? <select value={fieldSectionBranch[field.id] || "yes"} onChange={e => setFieldSectionBranch({ ...fieldSectionBranch, [field.id]: e.target.value as "yes" | "no" })} title="Ô này xuất hiện sau câu trả lời Có hay Không" style={{ padding: "3px 6px", fontSize: "0.75rem", border: "1px solid #c4b5fd", borderRadius: 4, background: "#faf5ff", color: "#6b21a8" }}><option value="yes">Khi trả lời Có</option><option value="no">Khi trả lời Không</option></select> : null; })()}
                                      <label style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "0.75rem", cursor: "pointer", flexShrink: 0 }}>
                                        <input
                                          type="checkbox"
                                          checked={fieldRequired[field.id] !== false}
                                          onChange={(e) => setFieldRequired({ ...fieldRequired, [field.id]: e.target.checked })}
                                        />
                                        Bắt buộc trả lời
                                      </label>
                                      
                                      <select
                                        value={selectedType}
                                        onChange={(e) => {
                                          const nextType = e.target.value;
                                          setFieldType({ ...fieldType, [field.id]: nextType });
                                        }}
                                        style={{ padding: "3px 6px", fontSize: "0.75rem", border: "1px solid #d1d5db", borderRadius: "4px", cursor: "pointer", flexShrink: 0 }}
                                      >
                                        <option value="text">📝 Nhập nội dung</option>
                                        <option value="checkbox">☑ Có / Không</option>
                                        <option value="radio">◉ Chọn một đáp án</option>
                                        <option value="digit_group">🔢 Dãy số tách ô</option>
                                      </select>
                                      
                                      <select value={fieldValueSource[field.id] || (fieldAutoFill[field.id] ? "ai_document" : "user_input")} onChange={e => setFieldValueSource({ ...fieldValueSource, [field.id]: e.target.value })} title="Chọn nơi lấy giá trị cho ô này" style={{ padding: "3px 6px", fontSize: "0.75rem", border: "1px solid #10b981", borderRadius: 4, background: "#ecfdf5", color: "#065f46" }}><option value="user_input">Người dùng nhập</option><option value="ai_document">AI đọc từ hồ sơ</option><option value="current_date">Tự lấy ngày lập đơn</option></select>
                                      {fieldValueSource[field.id] === "current_date" && <select value={fieldDatePart[field.id] || "day"} onChange={e => setFieldDatePart({ ...fieldDatePart, [field.id]: e.target.value })} style={{ padding: "3px 6px", fontSize: "0.75rem", border: "1px solid #10b981", borderRadius: 4, background: "#ecfdf5", color: "#065f46" }}><option value="day">Ngày</option><option value="month">Tháng</option><option value="year">Năm</option></select>}
                                      
                                      
                                      {selectedType === 'radio' && (
                                        <input
                                          type="text"
                                          placeholder="Ví dụ: Đã có | Chưa có"
                                          value={fieldOptions[field.id] || ""}
                                          onChange={(e) => setFieldOptions({ ...fieldOptions, [field.id]: e.target.value })}
                                          style={{ minWidth: 190, padding: "3px 8px", fontSize: "0.75rem", border: "1px solid #60a5fa", borderRadius: "4px", background: "#eff6ff" }}
                                          title="Ví dụ: Đã có giấy chứng nhận | Chưa có giấy chứng nhận"
                                        />
                                      )}
                                      {selectedType === 'digit_group' && (
                                          <input
                                            type="text"
                                            placeholder="Tên dãy số (vd: Mã số thuế)"
                                            value={fieldGroupKey[field.id] || ""}
                                            onChange={(e) => setFieldGroupKey({ ...fieldGroupKey, [field.id]: e.target.value })}
                                            style={{ width: 150, padding: "3px 8px", fontSize: "0.75rem", border: "1px solid #f59e0b", borderRadius: "4px", background: "#fffbeb" }}
                                          />
                                      )}
                                    </div>
                                    <div style={{ display: "flex", gap: "10px", alignItems: "center", flexWrap: "wrap" }}>
                                      <input
                                        type="text"
                                        placeholder="Ghi chú cho AI hoặc người dùng (không bắt buộc)"
                                        value={fieldDesc[field.id] || ""}
                                        onChange={(e) => setFieldDesc({ ...fieldDesc, [field.id]: e.target.value })}
                                        style={{ flex: 1, minWidth: 100, padding: "4px 8px", fontSize: "0.75rem", border: "1px solid #d1d5db", borderRadius: "4px" }}
                                      />
                                      
                                      {!fieldSectionId[field.id] ? <div style={{ display: "flex", alignItems: "center", gap: 6, flexShrink: 0 }}>
                                        <Sparkles size={14} color="#a855f7" />
                                        <select
                                          value={fieldDependsOn[field.id] || ""}
                                          onChange={(e) => {
                                            const parentId = e.target.value;
                                            setFieldDependsOn({ ...fieldDependsOn, [field.id]: parentId });
                                            const parentType = virtualConditions.some(condition => condition.id === parentId) ? "checkbox" : fieldType[parentId] || (editableZones?.find((z: any) => String(z.idx) === labeledList.find(l => l.id === parentId)?.blankIdx)?.field_type === "checkbox" ? "checkbox" : "text");
                                            setFieldDependsValue({ ...fieldDependsValue, [field.id]: parentType === "checkbox" ? "true" : "" });
                                          }}
                                          style={{ padding: "3px 6px", fontSize: "0.75rem", border: "1px solid #d8b4fe", borderRadius: "4px", background: "#faf5ff", color: "#6b21a8", cursor: "pointer", maxWidth: 200 }}
                                        >
                                          <option value="">Luôn hiển thị</option>
                                          {virtualConditions.filter(condition => condition.name.trim()).map(condition => <option key={condition.id} value={condition.id}>Chỉ hiển thị khi: {condition.name}</option>)}
                                          {labeledList.filter(l => {
                                            if (l.id === field.id) return false;
                                            const candidateZone = editableZones?.find((z: any) => String(z.idx) === l.blankIdx);
                                            const candidateType = fieldType[l.id] || (candidateZone?.field_type === "checkbox" ? "checkbox" : "text");
                                            return candidateType === "checkbox" || candidateType === "radio";
                                          }).map(l => {
                                            const tgtName = fieldData[l.id] !== undefined ? fieldData[l.id] : (editableZones?.find((z: any) => String(z.idx) === l.blankIdx)?.suggested_label || l.id);
                                            return <option key={l.id} value={l.id}>Chỉ hiển thị khi: {tgtName}</option>;
                                          })}
                                        </select>
                                        {fieldDependsOn[field.id] && (() => {
                                          const parentId = fieldDependsOn[field.id];
                                          const parentType = virtualConditions.some(condition => condition.id === parentId) ? "checkbox" : fieldType[parentId] || (editableZones?.find((z: any) => String(z.idx) === labeledList.find(l => l.id === parentId)?.blankIdx)?.field_type === "checkbox" ? "checkbox" : "text");
                                          const optionText = fieldOptions[parentId] || "";
                                          const options = optionText.split("|").map(v => v.trim()).filter(Boolean);
                                          return parentType === "checkbox" ? (
                                            <select value={fieldDependsValue[field.id] || "true"} onChange={(e) => setFieldDependsValue({ ...fieldDependsValue, [field.id]: e.target.value })} style={{ padding: "3px 6px", fontSize: "0.75rem", border: "1px solid #d8b4fe", borderRadius: 4, background: "#faf5ff", color: "#6b21a8" }}><option value="true">= Có / tick</option><option value="false">= Không</option></select>
                                          ) : parentType === "radio" ? (
                                            <select value={fieldDependsValue[field.id] || ""} onChange={(e) => setFieldDependsValue({ ...fieldDependsValue, [field.id]: e.target.value })} style={{ padding: "3px 6px", fontSize: "0.75rem", border: "1px solid #d8b4fe", borderRadius: 4, background: "#faf5ff", color: "#6b21a8" }}><option value="">Chọn đáp án...</option>{options.map(option => <option key={option} value={option}>= {option}</option>)}</select>
                                          ) : <span style={{ fontSize: "0.72rem", color: "#b45309" }}>Câu điều kiện nên là Có/Không hoặc Chọn một đáp án.</span>;
                                        })()}
                                      </div> : <span style={{ color: "#6b21a8", fontSize: "0.75rem" }}>Điều kiện hiển thị do cụm quyết định</span>}
                                      
                                    </div>
                                  </div>
                                  {/* BUG 1 FIX: Show zone number in a more visible way to correlate with PDF */}
                                  {field.blankIdx && (
                                    <div style={{ fontSize: "0.7rem", color: "#9ca3af", marginTop: 6 }}>
                                      Vùng #{field.blankIdx} trên PDF
                                    </div>
                                  )}
                                </div>
                                {isCheckbox && (
                                  <span style={{
                                    fontSize: "0.75rem", background: "#4f46e5", color: "#fff",
                                    padding: "2px 8px", borderRadius: "12px", flexShrink: 0, fontWeight: 600
                                  }}>☑ Checkbox</span>
                                )}
                              </div>
                            </div>
                          );
                        })}

                        <div style={{ display: "flex", justifyContent: "flex-end", gap: 12, marginTop: 24 }}>
                          <button type="button" onClick={() => setStep(2)} style={{ padding: "8px 16px", borderRadius: "6px", border: "1px solid #d1d5db", backgroundColor: "#fff", cursor: "pointer", fontWeight: 500 }}>Quay lại</button>
                          <button type="submit" className="primary-button" disabled={uploading}>{uploading ? "Đang lưu..." : "Lưu Biểu mẫu"}</button>
                        </div>
                      </form>
                    ) : (
                      <div>
                        <p style={{ color: "#6b7280", fontSize: "0.875rem", marginBottom: 16 }}>
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
                        </button>
                        {labeledCount > 0 && (
                          <>
                            <div style={{ fontSize: "0.8rem", color: "#059669", background: "#ecfdf5", padding: "8px 12px", borderRadius: 6, marginBottom: 12 }}>
                              ✓ Đã chọn {labeledCount} vùng để dán nhãn
                            </div>
                            <div style={{ fontSize: "0.8rem", color: "#4b5563", background: "#f3f4f6", padding: "8px 12px", borderRadius: 6 }}>
                              <strong>Lưu ý:</strong> Bạn có thể xem và chỉnh sửa tên chi tiết của các nhãn này ở <strong>Bước 3 (Tiếp theo)</strong>.
                            </div>
                          </>
                        )}
                      </div>
                    )}
                  </div>
                </div>

                {/* Right Panel - PDF Preview */}
                <div style={{ flex: 1, minHeight: 0, minWidth: 0, display: "flex", flexDirection: "column", position: "relative" }}>
                  {/* Toolbar */}
                  <div style={{
                    padding: "8px 16px",
                    background: "#1e3a5f",
                    borderBottom: "1px solid #1e40af",
                    display: "flex", gap: 8, alignItems: "center", flexShrink: 0, flexWrap: "wrap",
                  }}>
                    {(["label", "add", "adjust", "merge", "remove"] as const).map(m => (
                      <button key={m} onClick={() => setMode(m)} style={{
                        padding: "6px 12px", borderRadius: 6, border: "none", cursor: "pointer",
                        fontSize: "0.8rem", fontWeight: 600,
                        background: mode === m ? "#3b82f6" : "rgba(255,255,255,0.1)",
                        color: mode === m ? "#fff" : "#cbd5e1"
                      }}>
                        {m === "label" ? "🏷 Dán nhãn" : m === "add" ? "➕ Thêm vùng" : m === "adjust" ? "↔ Chỉnh vùng" : m === "merge" ? `🔀 Gộp${mergeCount > 0 ? ` (${mergeCount})` : ""}` : "🗑 Xóa vùng"}
                      </button>
                    ))}
                    {mode === "merge" && mergeCount >= 2 && (
                      <button onClick={handleMerge} style={{ padding: "6px 12px", borderRadius: 6, border: "none", background: "#f59e0b", color: "#fff", cursor: "pointer", fontWeight: 600, fontSize: "0.8rem" }}>
                        Gộp {mergeCount} vùng
                      </button>
                    )}
                    <div style={{ marginLeft: "auto" }}>
                      {step === 2 && labeledCount > 0 && (
                        <button onClick={() => {
                          setLabeledSnapshot({ ...labeledZonesRef.current });
                          setFieldOrderSnapshot([...fieldOrderRef.current]);
                          setStep(3);
                        }} style={{ padding: "6px 16px", borderRadius: 6, border: "none", background: "#10b981", color: "#fff", cursor: "pointer", fontWeight: 600, fontSize: "0.85rem" }}>
                          Tiếp theo →
                        </button>
                      )}
                    </div>
                  </div>

                  {/* PDF Preview */}
                  <div className="doc-preview-shell" style={{ flex: 1, minHeight: 0, minWidth: 0, position: "relative", overflow: "hidden" }}>
                    {(() => {
                      const currentFieldOrder = step === 3 ? fieldOrderSnapshot : fieldOrderRef.current;
                      const currentLabeledZones = step === 3 ? labeledSnapshot : labeledZonesRef.current;
                      let uniqueFields = Array.from(new Set(currentFieldOrder.filter(fid => Object.values(currentLabeledZones).includes(fid))));
                      
                      uniqueFields.sort((a, b) => {
                        const idxA = Object.entries(currentLabeledZones).find(([, v]) => v === a)?.[0] || "";
                        const idxB = Object.entries(currentLabeledZones).find(([, v]) => v === b)?.[0] || "";
                        const zoneA = editableZones?.find((z: any) => String(z.idx) === idxA);
                        const zoneB = editableZones?.find((z: any) => String(z.idx) === idxB);
                        if (!zoneA || !zoneB) return 0;
                        if (zoneA.page !== zoneB.page) return zoneA.page - zoneB.page;
                        const yDiff = zoneA.y - zoneB.y;
                        if (Math.abs(yDiff) > 10) return yDiff;
                        return zoneA.x - zoneB.x;
                      });
                      
                      const fieldDetailsMap = uniqueFields.reduce((acc, fid, i) => {
                        const zoneIdx = Object.entries(currentLabeledZones).find(([, v]) => v === fid)?.[0] || "";
                        const zone = editableZones?.find((z: any) => String(z.idx) === zoneIdx);
                        const suggestedLabel = zone?.suggested_label || zone?.ai_label || "";
                        
                        acc[fid] = { 
                          num: i + 1, 
                          label: fieldData[fid as string] !== undefined ? fieldData[fid as string] : suggestedLabel 
                        };
                        return acc;
                      }, {} as Record<string, { num: number; label: string }>);

                      return (
                        <PdfFormPreview
                          pageImages={previewData.page_images || [previewData.preview_url]}
                          zones={editableZones}
                          mode={mode}
                          labeledZones={labeledZonesRef.current}
                          mergeSelection={mergeSelectionRef.current}
                          readOnly={false}
                          fieldDetails={fieldDetailsMap}
                          onZoneClick={handleZoneClick}
                          onZonesChange={(newZones) => {
                            // Find new zones by checking which idx is not in the old editableZones
                            const oldIdxSet = new Set(editableZones.map((z: any) => String(z.idx)));
                            const newZonesAdded = newZones.filter((z: any) => !oldIdxSet.has(String(z.idx)));

                            setEditableZones(newZones);
                            const newIdxSet = new Set(newZones.map((z: any) => String(z.idx)));
                            
                            // Remove labels for deleted zones
                            Object.keys(labeledZonesRef.current).forEach(k => {
                              if (!newIdxSet.has(k)) delete labeledZonesRef.current[k];
                            });

                            // Auto-label newly drawn zones
                            newZonesAdded.forEach((z: any) => {
                              const newFieldId = `field_${manualCounterRef.current++}`;
                              labeledZonesRef.current[String(z.idx)] = newFieldId;
                              if (!fieldOrderRef.current.includes(newFieldId)) {
                                fieldOrderRef.current.push(newFieldId);
                              }
                            });

                            setLabeledCount(Object.keys(labeledZonesRef.current).length);
                            setLabeledSnapshot({ ...labeledZonesRef.current });
                            setFieldOrderSnapshot([...fieldOrderRef.current]);
                          }}
                          activeZoneIdx={activeZoneIdx}
                          onTextBlockClick={(text) => {
                            if (!activeZoneIdx) return;
                            const fieldId = labeledZonesRef.current[activeZoneIdx];
                            if (fieldId) {
                              const cleanText = text.replace(/[:.\s]+$/, "").trim();
                              setFieldData(prev => ({ ...prev, [fieldId]: cleanText }));
                              showToast(`Đã gán nhãn: ${cleanText}`, "success");
                              setActiveZoneIdx(null);
                            }
                          }}
                        />
                      );
                    })()}
                  </div>

                  {/* Bottom bar for step 2 */}
                  {step === 2 && (
                    <div style={{ padding: "12px 24px", borderTop: "1px solid #e5e7eb", display: "flex", justifyContent: "space-between", alignItems: "center", flexShrink: 0, background: "#f9fafb" }}>
                      <span style={{ fontSize: "0.85rem", color: "#6b7280" }}>
                        Đã chọn <strong style={{ color: "#4f46e5" }}>{labeledCount}</strong> nhãn
                      </span>
                      <button
                        onClick={() => {
                          if (labeledCount === 0) { showToast("Vui lòng dán nhãn ít nhất 1 vùng", "error"); return; }
                          setLabeledSnapshot({ ...labeledZonesRef.current });
                          setFieldOrderSnapshot([...fieldOrderRef.current]);
                          setStep(3);
                        }}
                        style={{ padding: "8px 20px", borderRadius: 6, border: "none", background: "#4f46e5", color: "#fff", cursor: "pointer", fontWeight: 600 }}
                      >
                        Tiếp theo →
                      </button>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {toast && <Toast msg={toast.msg} type={toast.type} onClose={hideToast} />}
    </>
  );
}

// ─── Admin Portal ─────────────────────────────────────────────────
function AdminPortal({ userName, onLogout }: { userName: string; onLogout: () => void }) {
  const [view, setView] = useState<AdminView>("overview");
  const [sidebar, setSidebar] = useState(false);
  const initials = userName.split(" ").map(n => n[0]).join("").substring(0, 2).toUpperCase();
  return (
    <div className="app-shell">
      <AppHeader role="admin" userName={userName} onLogout={onLogout} onMenu={() => setSidebar(true)} />
      <div className="workspace admin-workspace">
        <aside className={`admin-sidebar ${sidebar ? "open" : ""}`}>
          <div className="admin-user">
            <span className="avatar">{initials}</span>
            <div><strong>{userName}</strong><small>Quản trị viên</small></div>
            <button className="icon-button mobile-only" onClick={() => setSidebar(false)}><X /></button>
          </div>
          <p className="section-label">Vận hành</p>
          <nav>
            {adminNav.map(item => (
              <button key={item.id} className={view === item.id ? "active" : ""} onClick={() => { setView(item.id); setSidebar(false); }}>
                <item.icon size={18} />{item.label}
              </button>
            ))}
          </nav>
          <p className="section-label">Hệ thống</p>
          <nav>
            <button className={view === "users" ? "active" : ""} onClick={() => { setView("users"); setSidebar(false); }}>
              <Users size={18} />Người dùng
            </button>
            <button><Settings size={18} />Cấu hình</button>
          </nav>
          <div className="admin-version"><ShieldCheck size={17} /><span><strong>TerraLegalAI</strong><small>Phiên bản 0.1.0</small></span></div>
        </aside>
        {sidebar && <button className="overlay" onClick={() => setSidebar(false)} />}
        <main className="admin-main">
          {view === "overview" && <Overview />}
          {view === "documents" && <DocumentsView />}
          {view === "forms" && <FormsView />}
          {view === "tests" && <TestsView />}
          {view === "reports" && <ReportsView />}
          {view === "users" && <UsersView />}
        </main>
      </div>
    </div>
  );
}

export default function Home() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [authView, setAuthView] = useState<"login" | "register">("login");
  const [authLoading, setAuthLoading] = useState(true);

  useEffect(() => {
    authApi.me()
      .then((u) => {
        if (u) setUser(u);
      })
      .catch(() => {})
      .finally(() => setAuthLoading(false));
  }, []);

  const logout = () => {
    authApi.logout();
    setUser(null);
    setAuthView("login");
  };

  if (authLoading) return <main className="auth-loading">Đang kiểm tra phiên đăng nhập...</main>;
  if (!user) return authView === "login"
    ? <Login onLogin={() => authApi.me().then(u => u && setUser(u))} onRegister={() => setAuthView("register")} />
    : <Register onBack={() => setAuthView("login")} onRegister={() => authApi.me().then(u => u && setUser(u))} />;
  return user.role === "admin" ? <AdminPortal userName={user.full_name} onLogout={logout} /> : <UserPortal userId={user.id} userName={user.full_name} userEmail={user.email} onLogout={logout} />;
}
