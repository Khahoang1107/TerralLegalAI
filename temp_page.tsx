"use client";

import axios from "axios";
import { useEffect, useState, useRef, useCallback } from "react";
import dynamic from "next/dynamic";
import { authApi, chatApi, conversationApi, formsApi, documentsApi, evaluationApi, reportsApi, type Citation, type Conversation, type Document, type TestCase, type EvaluationRun } from "@/lib/api";
import {
  AlertCircle, BarChart3, BookOpen, Bot, Check, CheckCircle2, ChevronDown, CircleAlert, Clock3,
  FileCheck2, FileText, LayoutDashboard, LogOut,
  Menu, MessageSquare, MoreHorizontal, Paperclip, Pencil, Plus, RefreshCw, Search,
  Send, Settings, ShieldCheck, Sparkles, TestTube2, ThumbsDown, ThumbsUp,
  Trash2, UploadCloud, User, Users, X,
} from "lucide-react";

const PdfFormPreview = dynamic(() => import("@/components/PdfFormPreview"), { ssr: false });

type Role = "citizen" | "admin";
type AdminView = "overview" | "documents" | "tests" | "reports" | "forms";

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
        <div className="brand-mark"><BookOpen size={25} /></div>
        <div className="brand-name">TerraLegalAI</div>
        <div className="intro-copy">
          <span className="eyebrow">Hệ thống thông tin pháp lý đất đai</span>
          <h1>Tra cứu thủ tục rõ ràng, đúng nguồn.</h1>
          <p>Hỗ trợ người dân và cán bộ tiếp cận quy trình, hồ sơ và căn cứ pháp lý từ tài liệu chính thức.</p>
          <div className="trust-list">
            <span><ShieldCheck size={18} /> Trích dẫn theo văn bản gốc</span>
            <span><FileCheck2 size={18} /> Theo dõi hiệu lực tài liệu</span>
            <span><Clock3 size={18} /> Hỗ trợ tra cứu mọi lúc</span>
          </div>
        </div>
      </section>

      <section className="login-panel">
        <form className="login-form" onSubmit={(e) => { e.preventDefault(); handleLogin(); }}>
          <div className="mobile-brand"><div className="brand-mark"><BookOpen size={22} /></div><strong>TerraLegalAI</strong></div>
          <div>
            <span className="eyebrow">Đăng nhập hệ thống</span>
            <h2>Chào mừng bạn quay lại</h2>
            <p>Sử dụng tài khoản được cấp để tiếp tục.</p>
          </div>

          <label>Email hoặc tên đăng nhập<input value={email} onChange={(e) => { setEmail(e.target.value); setError(""); }} autoComplete="username" placeholder="Nhập tài khoản của bạn" /></label>
          <label>Mật khẩu<input type="password" value={password} onChange={(e) => { setPassword(e.target.value); setError(""); }} autoComplete="current-password" placeholder="Nhập mật khẩu" /></label>
          {error && <div className="login-error" role="alert"><CircleAlert size={16} /> {error}</div>}
          <div className="form-row"><label className="check-label"><input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} /> Ghi nhớ đăng nhập</label><button type="button" className="text-button">Quên mật khẩu?</button></div>
          <button className="primary-button" type="submit" disabled={loading}>{loading ? "Đang đăng nhập..." : "Đăng nhập"}</button>
          <p className="auth-switch">Bạn chưa có tài khoản? <button type="button" className="text-button" onClick={onRegister}>Đăng ký</button></p>
        </form>
      </section>
    </main>
  );
}

function Register({ onBack, onRegister }: { onBack: () => void; onRegister: (role: Role) => void }) {
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
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
        <div className="brand-mark"><BookOpen size={25} /></div>
        <div className="brand-name">TerraLegalAI</div>
        <div className="intro-copy">
          <span className="eyebrow">Hệ thống thông tin pháp lý đất đai</span>
          <h1>Tra cứu thủ tục rõ ràng, đúng nguồn.</h1>
          <p>Tạo tài khoản để lưu lịch sử tra cứu và tiếp tục các cuộc trò chuyện của bạn.</p>
          <div className="trust-list">
            <span><ShieldCheck size={18} /> Trích dẫn theo văn bản gốc</span>
            <span><FileCheck2 size={18} /> Theo dõi hiệu lực tài liệu</span>
            <span><Clock3 size={18} /> Hỗ trợ tra cứu mọi lúc</span>
          </div>
        </div>
      </section>

      <section className="login-panel">
        <form className="login-form" onSubmit={(e) => { e.preventDefault(); handleRegister(); }}>
          <div className="mobile-brand"><div className="brand-mark"><BookOpen size={22} /></div><strong>TerraLegalAI</strong></div>
          <div>
            <span className="eyebrow">Đăng ký tài khoản</span>
            <h2>Tạo tài khoản mới</h2>
            <p>Điền thông tin bên dưới để bắt đầu sử dụng hệ thống.</p>
          </div>
          <label>Họ và tên<input value={fullName} onChange={(e) => { setFullName(e.target.value); setError(""); }} autoComplete="name" placeholder="Nhập họ và tên" required minLength={2} /></label>
          <label>Email<input value={email} onChange={(e) => { setEmail(e.target.value); setError(""); }} type="email" autoComplete="email" placeholder="Nhập địa chỉ email" required /></label>
          <label>Mật khẩu<input value={password} onChange={(e) => { setPassword(e.target.value); setError(""); }} type="password" autoComplete="new-password" placeholder="Tạo mật khẩu (ít nhất 8 ký tự)" required minLength={8} /></label>
          <label>Xác nhận mật khẩu<input value={confirmation} onChange={(e) => { setConfirmation(e.target.value); setError(""); }} type="password" autoComplete="new-password" placeholder="Nhập lại mật khẩu" required minLength={8} /></label>
          {error && <div className="login-error" role="alert"><CircleAlert size={16} /> {error}</div>}
          <button className="primary-button" type="submit" disabled={loading}>{loading ? "Đang tạo tài khoản..." : "Đăng ký"}</button>
          <p className="auth-switch">Bạn đã có tài khoản? <button type="button" className="text-button" onClick={onBack}>Đăng nhập</button></p>
        </form>
      </section>
    </main>
  );
}

function AppHeader({ role, userName = "Người dùng", onLogout, onMenu }: { role: Role; userName?: string; onLogout: () => void; onMenu: () => void }) {
  const initials = userName.split(" ").map(n => n[0]).join("").substring(0, 2).toUpperCase();
  return (
    <header className="app-header">
      <div className="header-brand"><button className="icon-button mobile-only" onClick={onMenu}><Menu /></button><div className="brand-mark small"><BookOpen size={19} /></div><strong>TerraLegalAI</strong><span className="role-badge">{role === "admin" ? "Quản trị" : "Tra cứu"}</span></div>
      <div className="header-actions"><span className="system-status"><i /> Hệ thống hoạt động</span><button className="profile-button"><span className="avatar">{initials}</span><span>{userName}</span><ChevronDown size={15} /></button><button className="icon-button" onClick={onLogout} title="Đăng xuất"><LogOut size={18} /></button></div>
    </header>
  );
}

function UserPortal({ userName, onLogout }: { userName: string; onLogout: () => void }) {
  const [sidebar, setSidebar] = useState(false);
  const [feedback, setFeedback] = useState<"up" | "down" | null>(null);
  const [conversationsList, setConversationsList] = useState<Conversation[]>([]);
  const [currentConversationId, setCurrentConversationId] = useState<string | null>(null);
  const [conversationMenuId, setConversationMenuId] = useState<string | null>(null);
  const [renamingConversation, setRenamingConversation] = useState<Conversation | null>(null);
  const [renameTitle, setRenameTitle] = useState("");
  const [conversationActionLoading, setConversationActionLoading] = useState(false);
  const [messages, setMessages] = useState<Array<{role: "user" | "ai", text: string, time: string, citations?: Citation[]}>>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const procedureFilter = "all";
  
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    conversationApi.getConversations().then(data => {
      setConversationsList(data);
    }).catch(console.error);
  }, []);

  const handleSelectConversation = async (id: string) => {
    try {
      const detail = await conversationApi.getConversation(id);
      setCurrentConversationId(detail.id);
      setMessages(detail.messages.map(m => ({
        role: m.role as "user" | "ai",
        text: m.content,
        time: new Date(m.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        citations: m.citations
      })));
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
    setConversationMenuId(null);
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
    setConversationMenuId(null);
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

  const handleSend = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!input.trim() || loading) return;
    
    const userMessage = input.trim();
    setInput("");
    
    const now = new Date();
    const timeString = `${now.getHours().toString().padStart(2, "0")}:${now.getMinutes().toString().padStart(2, "0")}`;
    
    setMessages(prev => [...prev, { role: "user", text: userMessage, time: timeString }]);
    setLoading(true);
    
    try {
      const response = await chatApi.sendMessage({
        question: userMessage,
        procedure_filter: procedureFilter === "all" ? undefined : procedureFilter,
        conversation_id: currentConversationId || undefined,
      });
      
      if (!currentConversationId && response.conversation_id) {
        setCurrentConversationId(response.conversation_id);
      }
      
      setMessages(prev => [...prev, { 
        role: "ai", 
        text: response.answer, 
        time: timeString,
        citations: response.citations
      }]);
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
    <div className="app-shell">
      <AppHeader role="citizen" userName={userName} onLogout={onLogout} onMenu={() => setSidebar(true)} />
      <div className="workspace">
        <aside className={`chat-sidebar ${sidebar ? "open" : ""}`}>
          <div className="sidebar-head">
            <button className="new-chat" onClick={handleNewChat}>
              <Plus size={17} /> Cuộc trò chuyện mới
            </button>
            <button className="icon-button mobile-only" onClick={() => setSidebar(false)}>
              <X />
            </button>
          </div>
          <div className="sidebar-search"><Search size={16} /><input placeholder="Tìm lịch sử" /></div>
          {conversationsList.length > 0 && (
            <>
              <p className="section-label">Gần đây</p>
              <nav className="conversation-list">
                {conversationsList.map((item) => (
                  <div className={`conversation-item ${currentConversationId === item.id ? "active" : ""}`} key={item.id}>
                    <button className="conversation-select" onClick={() => handleSelectConversation(item.id)}>
                      <MessageSquare size={16} />
                      <span>
                        <strong>{item.title}</strong>
                        <small>{new Date(item.created_at).toLocaleDateString()}</small>
                      </span>
                    </button>
                    <button
                      className="conversation-menu-trigger"
                      onClick={() => setConversationMenuId((id) => id === item.id ? null : item.id)}
                      title="Tùy chọn cuộc trò chuyện"
                      aria-label={`Tùy chọn cho ${item.title}`}
                    >
                      <MoreHorizontal size={16} />
                    </button>
                    {conversationMenuId === item.id && (
                      <div className="conversation-menu">
                        <button onClick={() => openRenameConversation(item)}><Pencil size={15} /> Đổi tên</button>
                        <button className="danger" onClick={() => handleDeleteConversation(item)}><Trash2 size={15} /> Xóa</button>
                      </div>
                    )}
                  </div>
                ))}
              </nav>
            </>
          )}
          <div className="sidebar-help"><BookOpen size={18} /><div><strong>Kho tài liệu</strong><span>2 văn bản đang hiệu lực</span></div></div>
        </aside>
        {sidebar && <button className="overlay" onClick={() => setSidebar(false)} />}

        <main className="chat-main">
          <div className="chat-toolbar">
            <div><h1>Tra cứu thủ tục đất đai</h1><p>Thông tin được đối chiếu từ văn bản trong hệ thống</p></div>

          </div>

          <div className="message-stream">
            <div className="date-divider"><span>Hôm nay</span></div>
            
            {messages.length === 0 ? (
              <div className="welcome-message" style={{ textAlign: "center", padding: "2rem", color: "var(--text-secondary)" }}>
                Hãy đặt câu hỏi về thủ tục đất đai để được hỗ trợ.
              </div>
            ) : (
              messages.map((msg, idx) => (
                <article key={idx} className={`message-row ${msg.role === "user" ? "user-message" : "ai-message"}`}>
                  <div className={`message-avatar ${msg.role}`} >
                    {msg.role === "user" ? <User size={17} /> : <Bot size={18} />}
                  </div>
                  <div className={msg.role === "user" ? "bubble" : "answer-block"}>
                    {msg.role === "ai" && <div className="answer-label"><Sparkles size={15} /> TerraLegalAI</div>}
                    <div style={{ whiteSpace: "pre-wrap" }}>{msg.text}</div>
                    
                    {msg.citations && msg.citations.length > 0 && (
                      <div className="citations-list" style={{ marginTop: "1rem" }}>
                        <p className="citations-heading">Nguồn tham khảo</p>
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
                        <button className={feedback === "up" ? "selected" : ""} onClick={() => setFeedback("up")} title="Hữu ích"><ThumbsUp size={16} /></button>
                        <button className={feedback === "down" ? "selected negative" : ""} onClick={() => setFeedback("down")} title="Chưa hữu ích"><ThumbsDown size={16} /></button>
                        <span className="answer-time">{msg.time}</span>
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
                   <div className="answer-label"><Sparkles size={15} /> TerraLegalAI đang tìm kiếm...</div>
                </div>
              </article>
            )}
            <div ref={bottomRef} />
          </div>

          <div className="composer-area">
            {messages.length === 0 && (
              <div className="suggestions">
                <button onClick={() => setInput("Thời hạn giải quyết là bao lâu?")}>Thời hạn giải quyết là bao lâu?</button>
                <button onClick={() => setInput("Nộp hồ sơ ở đâu?")}>Nộp hồ sơ ở đâu?</button>
                <button onClick={() => setInput("Lệ phí cấp đổi thế nào?")}>Lệ phí cấp đổi thế nào?</button>
              </div>
            )}
            <form className="composer" onSubmit={handleSend}>
              <button type="button" className="icon-button" title="Đính kèm"><Paperclip size={19} /></button>
              <textarea 
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Nhập câu hỏi về thủ tục đất đai..." 
                rows={1} 
                disabled={loading}
              />
              <button type="submit" className="send-button" title="Gửi câu hỏi" disabled={!input.trim() || loading}>
                <Send size={18} />
              </button>
            </form>
            <p>Thông tin mang tính tham khảo. Vui lòng kiểm tra lại với cơ quan có thẩm quyền.</p>
          </div>
        </main>
      </div>
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

  return <><div className="page-heading"><div><span className="eyebrow">Kho tri thức</span><h1>Quản lý tài liệu</h1><p>Cập nhật, kiểm duyệt và theo dõi quá trình lập chỉ mục.</p></div><button className="primary-button fit" onClick={() => setShowUpload(true)}><UploadCloud size={17} /> Tải tài liệu lên</button></div>
    <section className="panel table-panel"><div className="table-wrap"><table><thead><tr><th>Tài liệu</th><th>Ngày cập nhật</th><th>Chunks</th><th>Trạng thái</th><th /></tr></thead><tbody>
      {loading ? <tr><td colSpan={5} style={{ textAlign: "center", padding: "20px" }}>Đang tải...</td></tr>
      : docs.length === 0 ? <tr><td colSpan={5} style={{ textAlign: "center", padding: "20px" }}>Chưa có tài liệu nào.</td></tr>
      : docs.map(doc => { const sl = statusLabel(doc.status); return <tr key={doc.id}><td><div className="document-name"><FileText size={19} /><span><strong>{doc.source_name}</strong><small>{doc.group_type}</small></span></div></td><td>{new Date(doc.created_at).toLocaleDateString("vi-VN")}</td><td>{doc.chunk_count || "—"}</td><td><span className={`status ${sl.cls}`}>{sl.icon}{sl.label}</span></td><td><button className="icon-button" style={{ color: "red" }} onClick={() => handleDelete(doc.id)} title="Xóa"><Trash2 size={17} /></button></td></tr>; })
      }
    </tbody></table></div></section>
    {showUpload && <UploadModal onClose={() => setShowUpload(false)} onSuccess={() => { documentsApi.getDocuments().then(setDocs).catch(console.error); showToast("Tải lên thành công!", "success"); }} />}
    {toast && <Toast msg={toast.msg} type={toast.type} onClose={hideToast} />}
  </>;
}

function TestsView() { return <><div className="page-heading"><div><span className="eyebrow">Đánh giá định kỳ</span><h1>Bộ kiểm thử</h1><p>Quản lý câu hỏi và câu trả lời chuẩn dùng để đánh giá AI.</p></div><button className="primary-button fit"><Plus size={17} /> Thêm test case</button></div><section className="panel"><div className="test-summary"><div><strong>15</strong><span>Tổng test case</span></div><div><strong>13</strong><span>Đạt yêu cầu</span></div><div><strong>2</strong><span>Cần rà soát</span></div><button className="secondary-button"><TestTube2 size={16} /> Chạy đánh giá</button></div><div className="test-list"><div><span className="test-id">TC-001</span><div><strong>Hồ sơ cấp đổi Giấy chứng nhận gồm những gì?</strong><p>Ground truth: Đơn đăng ký biến động, bản gốc Giấy chứng nhận...</p></div><span className="status done"><Check size={13} /> Đạt</span><button className="icon-button"><MoreHorizontal /></button></div><div><span className="test-id">TC-002</span><div><strong>Thời hạn cấp đổi sổ đỏ là bao lâu?</strong><p>Ground truth: Không quá thời hạn quy định theo từng địa bàn...</p></div><span className="status processing"><Clock3 size={13} /> Rà soát</span><button className="icon-button"><MoreHorizontal /></button></div></div></section></>; }

function ReportsView() { return <><div className="page-heading"><div><span className="eyebrow">Theo dõi sử dụng</span><h1>Nhật ký & báo cáo</h1><p>Phân tích nhu cầu tra cứu và các trường hợp AI chưa giải quyết tốt.</p></div><button className="secondary-button"><FileText size={16} /> Xuất báo cáo</button></div><section className="admin-grid"><div className="panel"><div className="panel-title"><div><h2>Chủ đề được hỏi nhiều</h2><p>30 ngày gần nhất</p></div></div><div className="topic-list"><div><span>Cấp đổi Giấy chứng nhận</span><strong>38%</strong><i style={{ width: "38%" }} /></div><div><span>Chuyển nhượng đất</span><strong>29%</strong><i style={{ width: "29%" }} /></div><div><span>Thời hạn giải quyết</span><strong>18%</strong><i style={{ width: "18%" }} /></div></div></div><div className="panel"><div className="panel-title"><div><h2>Phản hồi người dùng</h2><p>328 lượt đánh giá</p></div></div><div className="feedback-score"><div><ThumbsUp /><strong>91%</strong><span>Hữu ích</span></div><div><ThumbsDown /><strong>9%</strong><span>Chưa hữu ích</span></div></div></div></section><section className="panel"><div className="panel-title"><div><h2>Câu hỏi fallback gần đây</h2><p>Cần bổ sung dữ liệu hoặc điều chỉnh truy xuất</p></div></div><div className="log-list"><div><time>09:42</time><span><strong>Thủ tục tách thửa đối với đất đang tranh chấp?</strong><small>Không tìm thấy ngữ cảnh đủ tin cậy · similarity 0.41</small></span><button>Rà soát</button></div><div><time>08:15</time><span><strong>Lệ phí cấp lại GCN năm 2026?</strong><small>Tài liệu hiện tại chưa có biểu phí · similarity 0.38</small></span><button>Rà soát</button></div></div></section></>; }

// ─── Forms View ───────────────────────────────────────────────────
function FormsView() {
  const [forms, setForms] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [editingForm, setEditingForm] = useState<any | null>(null);
  const [editName, setEditName] = useState("");
  const [editProcedure, setEditProcedure] = useState("");
  const [editDesc, setEditDesc] = useState("");
  const [editSaving, setEditSaving] = useState(false);

  // Visual Builder State
  const [step, setStep] = useState(1);
  const [docxFile, setDocxFile] = useState<File | null>(null);
  const [previewData, setPreviewData] = useState<any | null>(null);
  const [editableZones, setEditableZones] = useState<any[]>([]);
  const [mode, setMode] = useState<'label' | 'merge' | 'remove' | 'add'>('label');
  const modeRef = useRef<'label' | 'merge' | 'remove' | 'add'>('label');
  const [mergeCount, setMergeCount] = useState(0);
  const [labeledCount, setLabeledCount] = useState(0);
  const [activeZoneIdx, setActiveZoneIdx] = useState<string | null>(null);

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
    if (!targetField && fieldOrderRef.current.length > 0) {
      targetField = fieldOrderRef.current[0];
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

  const uniqueFieldsSnapshot = Array.from(new Set(
    fieldOrderSnapshot.filter(fid => Object.values(labeledSnapshot).includes(fid))
  ));
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
      let fieldCounter = 1;

      // Auto-assign labels for zones with suggestions
      zones.forEach((zone: any) => {
        const suggestion = zone.suggested_label || zone.ai_label;
        if (suggestion) {
          const fieldId = `field_${9000 + fieldCounter++}`;
          initialLabeledZones[String(zone.idx)] = fieldId;
          initialFieldOrder.push(fieldId);
        }
      });

      labeledZonesRef.current = initialLabeledZones;
      fieldOrderRef.current = initialFieldOrder;
      setFieldData({});
      setLabeledCount(Object.keys(initialLabeledZones).length);
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
      const zone = previewData?.zones?.find((z: any) => String(z.idx) === f.blankIdx);
      const suggested = zone?.suggested_label || zone?.ai_label || "";
      const val = fieldData[f.id] !== undefined ? fieldData[f.id] : suggested;
      return val && val.trim() !== "";
    });
    if (!allFilled) {
      showToast("Vui lòng nhập Tên trường dữ liệu cho TẤT CẢ các nhãn", "error");
      return;
    }
    setUploading(true);
    const fields = labeledList.map(f => {
      const zone = previewData?.zones?.find((z: any) => String(z.idx) === f.blankIdx);
      const isCheckbox = zone?.field_type === 'checkbox';
      const suggested = zone?.suggested_label || zone?.ai_label || "";
      const finalName = fieldData[f.id] !== undefined ? fieldData[f.id] : (suggested || f.id);
      
      const isRequired = fieldRequired[f.id] !== undefined ? fieldRequired[f.id] : true;
      const customDesc = fieldDesc[f.id];
      const defaultDesc = isCheckbox ? `Có hay không: ${finalName}?` : `Nhập thông tin cho ${finalName}`;
      
      return {
        key: f.id,
        name: finalName,
        description: customDesc || defaultDesc,
        required: isRequired,
        type: isCheckbox ? "boolean" : "string"
      };
    });
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

  const openEdit = (form: any) => {
    setEditingForm(form);
    setEditName(form.name);
    setEditProcedure(form.procedure_type);
    setEditDesc(form.description || "");
  };

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingForm || !editName.trim() || !editProcedure.trim()) {
      showToast("Vui lòng điền đủ Tên và Loại thủ tục", "error");
      return;
    }
    setEditSaving(true);
    try {
      await formsApi.updateForm(editingForm.id, { name: editName, procedure_type: editProcedure, description: editDesc });
      showToast("Cập nhật biểu mẫu thành công!", "success");
      setEditingForm(null);
      fetchForms();
    } catch {
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
          <button className="primary-button fit" onClick={() => setShowModal(true)} style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
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
      {editingForm && (
        <div className="dialog-backdrop" onClick={() => setEditingForm(null)}>
          <form className="rename-dialog" style={{ maxWidth: 480, width: "95%" }} onSubmit={handleUpdate} onClick={(e) => e.stopPropagation()}>
            <div className="dialog-head">
              <h2>Chỉnh sửa Biểu mẫu</h2>
              <button type="button" className="icon-button" onClick={() => setEditingForm(null)}><X size={18} /></button>
            </div>
            <label style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 13, fontWeight: 600, marginBottom: 14 }}>
              Tên Biểu mẫu *
              <input value={editName} onChange={(e) => setEditName(e.target.value)} style={{ border: "1px solid #cfd7d1", padding: "10px 12px", borderRadius: 6, fontSize: 14 }} />
            </label>
            <label style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 13, fontWeight: 600, marginBottom: 14 }}>
              Loại thủ tục *
              <input value={editProcedure} onChange={(e) => setEditProcedure(e.target.value)} style={{ border: "1px solid #cfd7d1", padding: "10px 12px", borderRadius: 6, fontSize: 14 }} />
            </label>
            <label style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 13, fontWeight: 600, marginBottom: 20 }}>
              Mô tả ngắn
              <input value={editDesc} onChange={(e) => setEditDesc(e.target.value)} placeholder="Mô tả tùy chọn..." style={{ border: "1px solid #cfd7d1", padding: "10px 12px", borderRadius: 6, fontSize: 14 }} />
            </label>
            <div className="dialog-actions">
              <button type="button" className="secondary-button" onClick={() => setEditingForm(null)}>Hủy</button>
              <button type="submit" className="primary-button" disabled={editSaving}>{editSaving ? "Đang lưu..." : "Lưu thay đổi"}</button>
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
                        <h4 style={{ marginBottom: 16, color: "#4f46e5" }}>
                          Nhập Tên trường dữ liệu cho {labeledList.length} nhãn đã chọn:
                        </h4>
                        {labeledList.map(field => {
                          const zone = previewData?.zones?.find((z: any) => String(z.idx) === field.blankIdx);
                          const isCheckbox = zone?.field_type === 'checkbox';
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
                                  <div style={{ display: "flex", gap: "12px", marginTop: "10px", alignItems: "center" }}>
                                    <label style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "0.75rem", cursor: "pointer" }}>
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
                                      style={{ flex: 1, padding: "4px 8px", fontSize: "0.75rem", border: "1px solid #d1d5db", borderRadius: "4px" }}
                                    />
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
                    {(["label", "add", "merge", "remove"] as const).map(m => (
                      <button key={m} onClick={() => setMode(m)} style={{
                        padding: "6px 12px", borderRadius: 6, border: "none", cursor: "pointer",
                        fontSize: "0.8rem", fontWeight: 600,
                        background: mode === m ? "#3b82f6" : "rgba(255,255,255,0.1)",
                        color: mode === m ? "#fff" : "#cbd5e1"
                      }}>
                        {m === "label" ? "🏷 Dán nhãn" : m === "add" ? "➕ Thêm vùng" : m === "merge" ? `🔀 Gộp${mergeCount > 0 ? ` (${mergeCount})` : ""}` : "🗑 Xóa vùng"}
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
                      const uniqueFields = Array.from(new Set(currentFieldOrder.filter(fid => Object.values(currentLabeledZones).includes(fid))));
                      
                      const fieldDetailsMap = uniqueFields.reduce((acc, fid, i) => {
                        const zoneIdx = Object.entries(currentLabeledZones).find(([, v]) => v === fid)?.[0] || "";
                        const zone = previewData?.zones?.find((z: any) => String(z.idx) === zoneIdx);
                        const suggestedLabel = zone?.suggested_label || zone?.ai_label || "";
                        
                        acc[fid] = { 
                          num: i + 1, 
                          label: fieldData[fid] !== undefined ? fieldData[fid] : suggestedLabel 
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
            <button><Users size={18} />Người dùng</button>
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
        </main>
      </div>
    </div>
  );
}

export default function Home() {
  const [user, setUser] = useState<{ role: Role; full_name: string } | null>(null);
  const [authView, setAuthView] = useState<"login" | "register">("login");
  const [authLoading, setAuthLoading] = useState(true);

  useEffect(() => {
    authApi.me().then((u) => {
      if (u) setUser({ role: u.role, full_name: u.full_name });
      setAuthLoading(false);
    });
  }, []);

  const logout = () => {
    authApi.logout();
    setUser(null);
    setAuthView("login");
  };

  if (authLoading) return <main className="auth-loading">Đang kiểm tra phiên đăng nhập...</main>;
  if (!user) return authView === "login"
    ? <Login onLogin={(role) => authApi.me().then(u => u && setUser({ role, full_name: u.full_name }))} onRegister={() => setAuthView("register")} />
    : <Register onBack={() => setAuthView("login")} onRegister={(role) => authApi.me().then(u => u && setUser({ role, full_name: u.full_name }))} />;
  return user.role === "admin" ? <AdminPortal userName={user.full_name} onLogout={logout} /> : <UserPortal userName={user.full_name} onLogout={logout} />;
}
