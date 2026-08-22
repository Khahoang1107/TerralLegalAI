"use client";

import axios from "axios";
import { useEffect, useState, useRef, useCallback } from "react";
import dynamic from "next/dynamic";
import { authApi, chatApi, conversationApi, formsApi, documentsApi, evaluationApi, reportsApi, usersApi, type Citation, type Conversation, type Document, type TestCase, type EvaluationRun } from "@/lib/api";
import {
  AlertCircle, BarChart3, BookOpen, Bot, Check, CheckCircle2, ChevronDown, CircleAlert, Clock3,
  FileCheck2, FileText, LayoutDashboard, LogOut,
  Menu, MessageSquare, MoreHorizontal, Paperclip, Pencil, Plus, RefreshCw, Search,
  Send, Settings, ShieldCheck, Sparkles, TestTube2, ThumbsDown, ThumbsUp,
  Trash2, UploadCloud, User, Users, X,
} from "lucide-react";

import FormReviewModal from "@/components/chat/FormReviewModal";
import UsersView from "@/components/admin/UsersView";

const PdfFormPreview = dynamic(() => import("@/components/PdfFormPreview"), { ssr: false });

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
  if (val == null) return "â€”";
  return `${Math.round(val * 100)}%`;
}

function statusLabel(s: string) {
  if (s === "indexed") return { label: "HoÃ n thÃ nh", cls: "done", icon: <Check size={13} /> };
  if (s === "indexing") return { label: "Äang xá»­ lÃ½", cls: "processing", icon: <Clock3 size={13} /> };
  if (s === "error") return { label: "Lá»—i", cls: "error", icon: <AlertCircle size={13} /> };
  return { label: "Chá» xá»­ lÃ½", cls: "processing", icon: <Clock3 size={13} /> };
}

// â”€â”€â”€ Toast â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

// â”€â”€â”€ Upload Modal â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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
    if (!file || !sourceName.trim()) { setError("Vui lÃ²ng chá»n file vÃ  nháº­p tÃªn nguá»“n."); return; }
    setLoading(true); setError("");
    try {
      await documentsApi.uploadDocument(file, sourceName.trim(), groupType, procedureType);
      onSuccess(); onClose();
    } catch (err) {
      const detail = axios.isAxiosError(err) ? err.response?.data?.detail : null;
      setError(typeof detail === "string" ? detail : "Táº£i lÃªn tháº¥t báº¡i, vui lÃ²ng thá»­ láº¡i.");
    } finally { setLoading(false); }
  };

  return (
    <div className="dialog-backdrop" onClick={onClose}>
      <form className="rename-dialog" style={{ maxWidth: 480, width: "95%" }} onSubmit={handleSubmit} onClick={(e) => e.stopPropagation()}>
        <div className="dialog-head">
          <h2>Táº£i tÃ i liá»‡u lÃªn</h2>
          <button type="button" className="icon-button" onClick={onClose}><X size={18} /></button>
        </div>
        <div className="upload-zone" style={{ padding: "1.5rem", marginBottom: "1rem", cursor: "pointer" }}
          onDragOver={(e) => e.preventDefault()} onDrop={handleDrop} onClick={() => fileInputRef.current?.click()}>
          <UploadCloud size={24} />
          <div>
            <strong>{file ? file.name : "KÃ©o tháº£ PDF / DOCX vÃ o Ä‘Ã¢y"}</strong>
            <span>{file ? `${(file.size / 1024 / 1024).toFixed(1)} MB` : "hoáº·c báº¥m Ä‘á»ƒ chá»n file"}</span>
          </div>
          <input ref={fileInputRef} type="file" accept=".pdf,.docx,.doc" style={{ display: "none" }} onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        </div>
        <label style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 13, fontWeight: 600, marginBottom: 12 }}>
          TÃªn nguá»“n tÃ i liá»‡u *
          <input value={sourceName} onChange={(e) => setSourceName(e.target.value)} placeholder="VD: QÄ 1085/QÄ-UBND" required style={{ border: "1px solid #cfd7d1", padding: "10px 12px", borderRadius: 6, fontSize: 14 }} />
        </label>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 12 }}>
          <label style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 13, fontWeight: 600 }}>
            NhÃ³m tÃ i liá»‡u
            <select value={groupType} onChange={(e) => setGroupType(e.target.value)} className="compact-select" style={{ height: 40 }}>
              <option value="quyet_dinh">Quyáº¿t Ä‘á»‹nh</option>
              <option value="luat">Luáº­t / Nghá»‹ Ä‘á»‹nh</option>
              <option value="bieu_mau">Biá»ƒu máº«u</option>
              <option value="faq">FAQ</option>
            </select>
          </label>
          <label style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 13, fontWeight: 600 }}>
            Thá»§ tá»¥c Ã¡p dá»¥ng
            <select value={procedureType} onChange={(e) => setProcedureType(e.target.value)} className="compact-select" style={{ height: 40 }}>
              <option value="all">Táº¥t cáº£</option>
              <option value="chuyen_nhuong">Chuyá»ƒn nhÆ°á»£ng</option>
              <option value="cap_doi">Cáº¥p Ä‘á»•i GCN</option>
              <option value="tang_cho">Táº·ng cho</option>
            </select>
          </label>
        </div>
        {error && <div className="login-error" style={{ marginBottom: 12 }}><AlertCircle size={15} /> {error}</div>}
        <div className="dialog-actions">
          <button type="button" className="secondary-button" onClick={onClose}>Há»§y</button>
          <button type="submit" className="primary-button" disabled={loading}>{loading ? "Äang táº£i lÃªn..." : "Táº£i lÃªn"}</button>
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
        (Array.isArray(detail) && detail[0]?.msg) ? detail[0].msg : "KhÃ´ng thá»ƒ Ä‘Äƒng nháº­p."
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
          <span className="eyebrow">Há»‡ thá»‘ng thÃ´ng tin phÃ¡p lÃ½ Ä‘áº¥t Ä‘ai</span>
          <h1>Tra cá»©u thá»§ tá»¥c rÃµ rÃ ng, Ä‘Ãºng nguá»“n.</h1>
          <p>Há»— trá»£ ngÆ°á»i dÃ¢n vÃ  cÃ¡n bá»™ tiáº¿p cáº­n quy trÃ¬nh, há»“ sÆ¡ vÃ  cÄƒn cá»© phÃ¡p lÃ½ tá»« tÃ i liá»‡u chÃ­nh thá»©c.</p>
          <div className="trust-list">
            <span><ShieldCheck size={18} /> TrÃ­ch dáº«n theo vÄƒn báº£n gá»‘c</span>
            <span><FileCheck2 size={18} /> Theo dÃµi hiá»‡u lá»±c tÃ i liá»‡u</span>
            <span><Clock3 size={18} /> Há»— trá»£ tra cá»©u má»i lÃºc</span>
          </div>
        </div>
      </section>

      <section className="login-panel">
        <form className="login-form" onSubmit={(e) => { e.preventDefault(); handleLogin(); }}>
          <div className="mobile-brand"><div className="brand-mark"><BookOpen size={22} /></div><strong>TerraLegalAI</strong></div>
          <div>
            <span className="eyebrow">ÄÄƒng nháº­p há»‡ thá»‘ng</span>
            <h2>ChÃ o má»«ng báº¡n quay láº¡i</h2>
            <p>Sá»­ dá»¥ng tÃ i khoáº£n Ä‘Æ°á»£c cáº¥p Ä‘á»ƒ tiáº¿p tá»¥c.</p>
          </div>

          <label>Email hoáº·c tÃªn Ä‘Äƒng nháº­p<input value={email} onChange={(e) => { setEmail(e.target.value); setError(""); }} autoComplete="username" placeholder="Nháº­p tÃ i khoáº£n cá»§a báº¡n" /></label>
          <label>Máº­t kháº©u<input type="password" value={password} onChange={(e) => { setPassword(e.target.value); setError(""); }} autoComplete="current-password" placeholder="Nháº­p máº­t kháº©u" /></label>
          {error && <div className="login-error" role="alert"><CircleAlert size={16} /> {error}</div>}
          <div className="form-row"><label className="check-label"><input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} /> Ghi nhá»› Ä‘Äƒng nháº­p</label><button type="button" className="text-button">QuÃªn máº­t kháº©u?</button></div>
          <button className="primary-button" type="submit" disabled={loading}>{loading ? "Äang Ä‘Äƒng nháº­p..." : "ÄÄƒng nháº­p"}</button>
          <p className="auth-switch">Báº¡n chÆ°a cÃ³ tÃ i khoáº£n? <button type="button" className="text-button" onClick={onRegister}>ÄÄƒng kÃ½</button></p>
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
      setError("Máº­t kháº©u xÃ¡c nháº­n khÃ´ng khá»›p.");
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
        (Array.isArray(detail) && detail[0]?.msg) ? detail[0].msg : "KhÃ´ng thá»ƒ táº¡o tÃ i khoáº£n."
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
          <span className="eyebrow">Há»‡ thá»‘ng thÃ´ng tin phÃ¡p lÃ½ Ä‘áº¥t Ä‘ai</span>
          <h1>Tra cá»©u thá»§ tá»¥c rÃµ rÃ ng, Ä‘Ãºng nguá»“n.</h1>
          <p>Táº¡o tÃ i khoáº£n Ä‘á»ƒ lÆ°u lá»‹ch sá»­ tra cá»©u vÃ  tiáº¿p tá»¥c cÃ¡c cuá»™c trÃ² chuyá»‡n cá»§a báº¡n.</p>
          <div className="trust-list">
            <span><ShieldCheck size={18} /> TrÃ­ch dáº«n theo vÄƒn báº£n gá»‘c</span>
            <span><FileCheck2 size={18} /> Theo dÃµi hiá»‡u lá»±c tÃ i liá»‡u</span>
            <span><Clock3 size={18} /> Há»— trá»£ tra cá»©u má»i lÃºc</span>
          </div>
        </div>
      </section>

      <section className="login-panel">
        <form className="login-form" onSubmit={(e) => { e.preventDefault(); handleRegister(); }}>
          <div className="mobile-brand"><div className="brand-mark"><BookOpen size={22} /></div><strong>TerraLegalAI</strong></div>
          <div>
            <span className="eyebrow">ÄÄƒng kÃ½ tÃ i khoáº£n</span>
            <h2>Táº¡o tÃ i khoáº£n má»›i</h2>
            <p>Äiá»n thÃ´ng tin bÃªn dÆ°á»›i Ä‘á»ƒ báº¯t Ä‘áº§u sá»­ dá»¥ng há»‡ thá»‘ng.</p>
          </div>
          <label>Há» vÃ  tÃªn<input value={fullName} onChange={(e) => { setFullName(e.target.value); setError(""); }} autoComplete="name" placeholder="Nháº­p há» vÃ  tÃªn" required minLength={2} /></label>
          <label>Email<input value={email} onChange={(e) => { setEmail(e.target.value); setError(""); }} type="email" autoComplete="email" placeholder="Nháº­p Ä‘á»‹a chá»‰ email" required /></label>
          <label>Máº­t kháº©u<input value={password} onChange={(e) => { setPassword(e.target.value); setError(""); }} type="password" autoComplete="new-password" placeholder="Táº¡o máº­t kháº©u (Ã­t nháº¥t 8 kÃ½ tá»±)" required minLength={8} /></label>
          <label>XÃ¡c nháº­n máº­t kháº©u<input value={confirmation} onChange={(e) => { setConfirmation(e.target.value); setError(""); }} type="password" autoComplete="new-password" placeholder="Nháº­p láº¡i máº­t kháº©u" required minLength={8} /></label>
          {error && <div className="login-error" role="alert"><CircleAlert size={16} /> {error}</div>}
          <button className="primary-button" type="submit" disabled={loading}>{loading ? "Äang táº¡o tÃ i khoáº£n..." : "ÄÄƒng kÃ½"}</button>
          <p className="auth-switch">Báº¡n Ä‘Ã£ cÃ³ tÃ i khoáº£n? <button type="button" className="text-button" onClick={onBack}>ÄÄƒng nháº­p</button></p>
        </form>
      </section>
    </main>
  );
}

function AppHeader({ role, userName = "NgÆ°á»i dÃ¹ng", onLogout, onMenu }: { role: Role; userName?: string; onLogout: () => void; onMenu: () => void }) {
  const initials = userName.split(" ").map(n => n[0]).join("").substring(0, 2).toUpperCase();
  return (
    <header className="app-header">
      <div className="header-brand"><button className="icon-button mobile-only" onClick={onMenu}><Menu /></button><div className="brand-mark small"><BookOpen size={19} /></div><strong>TerraLegalAI</strong><span className="role-badge">{role === "admin" ? "Quáº£n trá»‹" : "Tra cá»©u"}</span></div>
      <div className="header-actions"><span className="system-status"><i /> Há»‡ thá»‘ng hoáº¡t Ä‘á»™ng</span><button className="profile-button"><span className="avatar">{initials}</span><span>{userName}</span><ChevronDown size={15} /></button><button className="icon-button" onClick={onLogout} title="ÄÄƒng xuáº¥t"><LogOut size={18} /></button></div>
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
  const [reviewFormId, setReviewFormId] = useState<string | null>(null);
  const [reviewFormData, setReviewFormData] = useState<Record<string, string>>({});
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
      window.alert("KhÃ´ng thá»ƒ Ä‘á»•i tÃªn cuá»™c trÃ² chuyá»‡n. Vui lÃ²ng thá»­ láº¡i.");
    } finally {
      setConversationActionLoading(false);
    }
  };

  const handleDeleteConversation = async (conversation: Conversation) => {
    setConversationMenuId(null);
    if (!window.confirm(`XÃ³a cuá»™c trÃ² chuyá»‡n "${conversation.title}"?`)) return;

    try {
      await conversationApi.deleteConversation(conversation.id);
    } catch (err) {
      if (!axios.isAxiosError(err) || err.response?.status !== 404) {
        window.alert("KhÃ´ng thá»ƒ xÃ³a cuá»™c trÃ² chuyá»‡n. Vui lÃ²ng thá»­ láº¡i.");
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
      
      if (response.form_completed && response.form_id) {
        setReviewFormId(response.form_id);
        setReviewFormData(response.collected_data || {});
      }
    } catch (err) {
      console.error(err);
      setMessages(prev => [...prev, { 
        role: "ai", 
        text: "Xin lá»—i, Ä‘Ã£ cÃ³ lá»—i xáº£y ra khi káº¿t ná»‘i vá»›i mÃ¡y chá»§. Vui lÃ²ng thá»­ láº¡i sau.", 
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
              <Plus size={17} /> Cuá»™c trÃ² chuyá»‡n má»›i
            </button>
            <button className="icon-button mobile-only" onClick={() => setSidebar(false)}>
              <X />
            </button>
          </div>
          <div className="sidebar-search"><Search size={16} /><input placeholder="TÃ¬m lá»‹ch sá»­" /></div>
          {conversationsList.length > 0 && (
            <>
              <p className="section-label">Gáº§n Ä‘Ã¢y</p>
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
                      title="TÃ¹y chá»n cuá»™c trÃ² chuyá»‡n"
                      aria-label={`TÃ¹y chá»n cho ${item.title}`}
                    >
                      <MoreHorizontal size={16} />
                    </button>
                    {conversationMenuId === item.id && (
                      <div className="conversation-menu">
                        <button onClick={() => openRenameConversation(item)}><Pencil size={15} /> Äá»•i tÃªn</button>
                        <button className="danger" onClick={() => handleDeleteConversation(item)}><Trash2 size={15} /> XÃ³a</button>
                      </div>
                    )}
                  </div>
                ))}
              </nav>
            </>
          )}
          <div className="sidebar-help"><BookOpen size={18} /><div><strong>Kho tÃ i liá»‡u</strong><span>2 vÄƒn báº£n Ä‘ang hiá»‡u lá»±c</span></div></div>
        </aside>
        {sidebar && <button className="overlay" onClick={() => setSidebar(false)} />}
        
        {reviewFormId && (
          <FormReviewModal
            formId={reviewFormId}
            initialData={reviewFormData}
            onClose={() => setReviewFormId(null)}
          />
        )}

        <main className="chat-main">
          <div className="chat-toolbar">
            <div><h1>Tra cá»©u thá»§ tá»¥c Ä‘áº¥t Ä‘ai</h1><p>ThÃ´ng tin Ä‘Æ°á»£c Ä‘á»‘i chiáº¿u tá»« vÄƒn báº£n trong há»‡ thá»‘ng</p></div>

          </div>

          <div className="message-stream">
            <div className="date-divider"><span>HÃ´m nay</span></div>
            
            {messages.length === 0 ? (
              <div className="welcome-message" style={{ textAlign: "center", padding: "2rem", color: "var(--text-secondary)" }}>
                HÃ£y Ä‘áº·t cÃ¢u há»i vá» thá»§ tá»¥c Ä‘áº¥t Ä‘ai Ä‘á»ƒ Ä‘Æ°á»£c há»— trá»£.
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
                        <p className="citations-heading">Nguá»“n tham kháº£o</p>
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
                        <span>CÃ¢u tráº£ lá»i nÃ y cÃ³ há»¯u Ã­ch?</span>
                        <button className={feedback === "up" ? "selected" : ""} onClick={() => setFeedback("up")} title="Há»¯u Ã­ch"><ThumbsUp size={16} /></button>
                        <button className={feedback === "down" ? "selected negative" : ""} onClick={() => setFeedback("down")} title="ChÆ°a há»¯u Ã­ch"><ThumbsDown size={16} /></button>
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
                   <div className="answer-label"><Sparkles size={15} /> TerraLegalAI Ä‘ang tÃ¬m kiáº¿m...</div>
                </div>
              </article>
            )}
            <div ref={bottomRef} />
          </div>

          <div className="composer-area">
            {messages.length === 0 && (
              <div className="suggestions">
                <button onClick={() => setInput("Thá»i háº¡n giáº£i quyáº¿t lÃ  bao lÃ¢u?")}>Thá»i háº¡n giáº£i quyáº¿t lÃ  bao lÃ¢u?</button>
                <button onClick={() => setInput("Ná»™p há»“ sÆ¡ á»Ÿ Ä‘Ã¢u?")}>Ná»™p há»“ sÆ¡ á»Ÿ Ä‘Ã¢u?</button>
                <button onClick={() => setInput("Lá»‡ phÃ­ cáº¥p Ä‘á»•i tháº¿ nÃ o?")}>Lá»‡ phÃ­ cáº¥p Ä‘á»•i tháº¿ nÃ o?</button>
              </div>
            )}
            <form className="composer" onSubmit={handleSend}>
              <button type="button" className="icon-button" title="ÄÃ­nh kÃ¨m"><Paperclip size={19} /></button>
              <textarea 
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Nháº­p cÃ¢u há»i vá» thá»§ tá»¥c Ä‘áº¥t Ä‘ai..." 
                rows={1} 
                disabled={loading}
              />
              <button type="submit" className="send-button" title="Gá»­i cÃ¢u há»i" disabled={!input.trim() || loading}>
                <Send size={18} />
              </button>
            </form>
            <p>ThÃ´ng tin mang tÃ­nh tham kháº£o. Vui lÃ²ng kiá»ƒm tra láº¡i vá»›i cÆ¡ quan cÃ³ tháº©m quyá»n.</p>
          </div>
        </main>
      </div>
      {renamingConversation && (
        <div className="dialog-backdrop" onClick={() => setRenamingConversation(null)}>
          <form className="rename-dialog" onSubmit={handleRenameConversation} onClick={(e) => e.stopPropagation()}>
            <div className="dialog-head">
              <h2>Äá»•i tÃªn cuá»™c trÃ² chuyá»‡n</h2>
              <button type="button" className="icon-button" onClick={() => setRenamingConversation(null)} title="ÄÃ³ng"><X size={18} /></button>
            </div>
            <label>TÃªn cuá»™c trÃ² chuyá»‡n<input autoFocus value={renameTitle} onChange={(e) => setRenameTitle(e.target.value)} maxLength={200} /></label>
            <div className="dialog-actions">
              <button type="button" className="secondary-button" onClick={() => setRenamingConversation(null)}>Há»§y</button>
              <button type="submit" className="primary-button" disabled={!renameTitle.trim() || conversationActionLoading}>{conversationActionLoading ? "Äang lÆ°u..." : "LÆ°u"}</button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}

const adminNav = [
  { id: "overview", label: "Tá»•ng quan", icon: LayoutDashboard },
  { id: "documents", label: "TÃ i liá»‡u", icon: FileText },
  { id: "forms", label: "Biá»ƒu máº«u", icon: FileCheck2 },
  { id: "tests", label: "Bá»™ kiá»ƒm thá»­", icon: TestTube2 },
  { id: "reports", label: "Nháº­t kÃ½ & bÃ¡o cÃ¡o", icon: BarChart3 },
] as const;

function Metric({ label, value, note, tone }: { label: string; value: string; note: string; tone?: string }) {
  return <article className="metric"><div className={`metric-icon ${tone ?? ""}`}><BarChart3 size={19} /></div><span>{label}</span><strong>{value}</strong><small>{note}</small></article>;
}

function Overview() {
  return <><div className="page-heading"><div><span className="eyebrow">Cháº¥t lÆ°á»£ng há»‡ thá»‘ng</span><h1>Báº£ng Ä‘iá»u khiá»ƒn</h1><p>Theo dÃµi hiá»‡u quáº£ tráº£ lá»i vÃ  tÃ¬nh tráº¡ng kho tri thá»©c.</p></div><select className="compact-select"><option>30 ngÃ y gáº§n nháº¥t</option><option>7 ngÃ y gáº§n nháº¥t</option></select></div>
    <section className="metric-grid"><Metric label="Faithfulness" value="92.4%" note="+2.1% so vá»›i ká»³ trÆ°á»›c" tone="green" /><Metric label="Answer Relevancy" value="88.7%" note="+1.3% so vá»›i ká»³ trÆ°á»›c" tone="blue" /><Metric label="Context Precision" value="86.1%" note="-0.8% cáº§n theo dÃµi" tone="amber" /><Metric label="Tá»· lá»‡ fallback" value="4.8%" note="38 / 792 cÃ¢u há»i" tone="red" /></section>
    <section className="admin-grid"><div className="panel chart-panel"><div className="panel-title"><div><h2>Cháº¥t lÆ°á»£ng tráº£ lá»i</h2><p>Äiá»ƒm RAGAS theo 6 tuáº§n gáº§n nháº¥t</p></div><MoreHorizontal /></div><div className="chart"><div className="y-labels"><span>100</span><span>75</span><span>50</span><span>25</span><span>0</span></div><div className="chart-body"><div className="chart-lines"><i /><i /><i /><i /></div><svg viewBox="0 0 600 190" preserveAspectRatio="none" aria-label="Biá»ƒu Ä‘á»“ Ä‘iá»ƒm cháº¥t lÆ°á»£ng"><polyline points="0,88 100,78 200,84 300,60 400,66 500,45 600,50" fill="none" stroke="#157347" strokeWidth="4" /><polyline points="0,110 100,100 200,106 300,90 400,84 500,78 600,72" fill="none" stroke="#315f9b" strokeWidth="4" /></svg><div className="x-labels"><span>Tuáº§n 1</span><span>Tuáº§n 2</span><span>Tuáº§n 3</span><span>Tuáº§n 4</span><span>Tuáº§n 5</span><span>Tuáº§n 6</span></div></div></div><div className="legend"><span><i className="green-dot" /> Faithfulness</span><span><i className="blue-dot" /> Relevancy</span></div></div>
      <div className="panel"><div className="panel-title"><div><h2>TÃ¬nh tráº¡ng dá»¯ liá»‡u</h2><p>Cáº­p nháº­t lÃºc 10:30 hÃ´m nay</p></div></div><div className="data-stats"><div><span>TÃ i liá»‡u Ä‘Ã£ index</span><strong>2</strong></div><div><span>Tá»•ng sá»‘ chunks</span><strong>280</strong></div><div><span>CÃ¢u há»i hÃ´m nay</span><strong>64</strong></div><div><span>Pháº£n há»“i tÃ­ch cá»±c</span><strong>91%</strong></div></div><button className="secondary-button"><RefreshCw size={16} /> Äá»“ng bá»™ dá»¯ liá»‡u</button></div></section>
    <section className="panel"><div className="panel-title"><div><h2>Cáº§n chÃº Ã½</h2><p>CÃ¡c cÃ¢u há»i cÃ³ Ä‘á»™ tin cáº­y tháº¥p cáº§n cÃ¡n bá»™ rÃ  soÃ¡t</p></div><button className="text-button">Xem táº¥t cáº£</button></div><div className="issue-list"><div><CircleAlert /><span><strong>"TrÆ°á»ng há»£p máº¥t sá»• Ä‘á» cáº§n lÃ m gÃ¬?"</strong><small>Äá»™ tin cáº­y 43% Â· Cáº¥p láº¡i GCN</small></span><button>Kiá»ƒm tra</button></div><div><CircleAlert /><span><strong>"CÃ³ thá»ƒ ná»™p há»“ sÆ¡ trá»±c tuyáº¿n khÃ´ng?"</strong><small>Äá»™ tin cáº­y 51% Â· Ná»™p há»“ sÆ¡</small></span><button>Kiá»ƒm tra</button></div></div></section></>;
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
    if (!window.confirm("Báº¡n cÃ³ cháº¯c muá»‘n xÃ³a tÃ i liá»‡u nÃ y?")) return;
    try {
      await documentsApi.deleteDocument(id);
      setDocs(prev => prev.filter(d => d.id !== id));
      showToast("ÄÃ£ xÃ³a tÃ i liá»‡u.", "success");
    } catch { showToast("Lá»—i khi xÃ³a.", "error"); }
  };

  return <><div className="page-heading"><div><span className="eyebrow">Kho tri thá»©c</span><h1>Quáº£n lÃ½ tÃ i liá»‡u</h1><p>Cáº­p nháº­t, kiá»ƒm duyá»‡t vÃ  theo dÃµi quÃ¡ trÃ¬nh láº­p chá»‰ má»¥c.</p></div><button className="primary-button fit" onClick={() => setShowUpload(true)}><UploadCloud size={17} /> Táº£i tÃ i liá»‡u lÃªn</button></div>
    <section className="panel table-panel"><div className="table-wrap"><table><thead><tr><th>TÃ i liá»‡u</th><th>NgÃ y cáº­p nháº­t</th><th>Chunks</th><th>Tráº¡ng thÃ¡i</th><th /></tr></thead><tbody>
      {loading ? <tr><td colSpan={5} style={{ textAlign: "center", padding: "20px" }}>Äang táº£i...</td></tr>
      : docs.length === 0 ? <tr><td colSpan={5} style={{ textAlign: "center", padding: "20px" }}>ChÆ°a cÃ³ tÃ i liá»‡u nÃ o.</td></tr>
      : docs.map(doc => { const sl = statusLabel(doc.status); return <tr key={doc.id}><td><div className="document-name"><FileText size={19} /><span><strong>{doc.source_name}</strong><small>{doc.group_type}</small></span></div></td><td>{new Date(doc.created_at).toLocaleDateString("vi-VN")}</td><td>{doc.chunk_count || "â€”"}</td><td><span className={`status ${sl.cls}`}>{sl.icon}{sl.label}</span></td><td><button className="icon-button" style={{ color: "red" }} onClick={() => handleDelete(doc.id)} title="XÃ³a"><Trash2 size={17} /></button></td></tr>; })
      }
    </tbody></table></div></section>
    {showUpload && <UploadModal onClose={() => setShowUpload(false)} onSuccess={() => { documentsApi.getDocuments().then(setDocs).catch(console.error); showToast("Táº£i lÃªn thÃ nh cÃ´ng!", "success"); }} />}
    {toast && <Toast msg={toast.msg} type={toast.type} onClose={hideToast} />}
  </>;
}

function TestsView() { return <><div className="page-heading"><div><span className="eyebrow">ÄÃ¡nh giÃ¡ Ä‘á»‹nh ká»³</span><h1>Bá»™ kiá»ƒm thá»­</h1><p>Quáº£n lÃ½ cÃ¢u há»i vÃ  cÃ¢u tráº£ lá»i chuáº©n dÃ¹ng Ä‘á»ƒ Ä‘Ã¡nh giÃ¡ AI.</p></div><button className="primary-button fit"><Plus size={17} /> ThÃªm test case</button></div><section className="panel"><div className="test-summary"><div><strong>15</strong><span>Tá»•ng test case</span></div><div><strong>13</strong><span>Äáº¡t yÃªu cáº§u</span></div><div><strong>2</strong><span>Cáº§n rÃ  soÃ¡t</span></div><button className="secondary-button"><TestTube2 size={16} /> Cháº¡y Ä‘Ã¡nh giÃ¡</button></div><div className="test-list"><div><span className="test-id">TC-001</span><div><strong>Há»“ sÆ¡ cáº¥p Ä‘á»•i Giáº¥y chá»©ng nháº­n gá»“m nhá»¯ng gÃ¬?</strong><p>Ground truth: ÄÆ¡n Ä‘Äƒng kÃ½ biáº¿n Ä‘á»™ng, báº£n gá»‘c Giáº¥y chá»©ng nháº­n...</p></div><span className="status done"><Check size={13} /> Äáº¡t</span><button className="icon-button"><MoreHorizontal /></button></div><div><span className="test-id">TC-002</span><div><strong>Thá»i háº¡n cáº¥p Ä‘á»•i sá»• Ä‘á» lÃ  bao lÃ¢u?</strong><p>Ground truth: KhÃ´ng quÃ¡ thá»i háº¡n quy Ä‘á»‹nh theo tá»«ng Ä‘á»‹a bÃ n...</p></div><span className="status processing"><Clock3 size={13} /> RÃ  soÃ¡t</span><button className="icon-button"><MoreHorizontal /></button></div></div></section></>; }

function ReportsView() { return <><div className="page-heading"><div><span className="eyebrow">Theo dÃµi sá»­ dá»¥ng</span><h1>Nháº­t kÃ½ & bÃ¡o cÃ¡o</h1><p>PhÃ¢n tÃ­ch nhu cáº§u tra cá»©u vÃ  cÃ¡c trÆ°á»ng há»£p AI chÆ°a giáº£i quyáº¿t tá»‘t.</p></div><button className="secondary-button"><FileText size={16} /> Xuáº¥t bÃ¡o cÃ¡o</button></div><section className="admin-grid"><div className="panel"><div className="panel-title"><div><h2>Chá»§ Ä‘á» Ä‘Æ°á»£c há»i nhiá»u</h2><p>30 ngÃ y gáº§n nháº¥t</p></div></div><div className="topic-list"><div><span>Cáº¥p Ä‘á»•i Giáº¥y chá»©ng nháº­n</span><strong>38%</strong><i style={{ width: "38%" }} /></div><div><span>Chuyá»ƒn nhÆ°á»£ng Ä‘áº¥t</span><strong>29%</strong><i style={{ width: "29%" }} /></div><div><span>Thá»i háº¡n giáº£i quyáº¿t</span><strong>18%</strong><i style={{ width: "18%" }} /></div></div></div><div className="panel"><div className="panel-title"><div><h2>Pháº£n há»“i ngÆ°á»i dÃ¹ng</h2><p>328 lÆ°á»£t Ä‘Ã¡nh giÃ¡</p></div></div><div className="feedback-score"><div><ThumbsUp /><strong>91%</strong><span>Há»¯u Ã­ch</span></div><div><ThumbsDown /><strong>9%</strong><span>ChÆ°a há»¯u Ã­ch</span></div></div></div></section><section className="panel"><div className="panel-title"><div><h2>CÃ¢u há»i fallback gáº§n Ä‘Ã¢y</h2><p>Cáº§n bá»• sung dá»¯ liá»‡u hoáº·c Ä‘iá»u chá»‰nh truy xuáº¥t</p></div></div><div className="log-list"><div><time>09:42</time><span><strong>Thá»§ tá»¥c tÃ¡ch thá»­a Ä‘á»‘i vá»›i Ä‘áº¥t Ä‘ang tranh cháº¥p?</strong><small>KhÃ´ng tÃ¬m tháº¥y ngá»¯ cáº£nh Ä‘á»§ tin cáº­y Â· similarity 0.41</small></span><button>RÃ  soÃ¡t</button></div><div><time>08:15</time><span><strong>Lá»‡ phÃ­ cáº¥p láº¡i GCN nÄƒm 2026?</strong><small>TÃ i liá»‡u hiá»‡n táº¡i chÆ°a cÃ³ biá»ƒu phÃ­ Â· similarity 0.38</small></span><button>RÃ  soÃ¡t</button></div></div></section></>; }

// â”€â”€â”€ Forms View â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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
  const [editFields, setEditFields] = useState<any[]>([]);

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
      showToast(`ÄÃ£ gá»™p ${items.length} vÃ¹ng vÃ o chung nhÃ£n!`, "success");
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
    if (!docxFile) return showToast("Vui lÃ²ng chá»n file Word (.docx)", "error");
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
        ? `PhÃ¡t hiá»‡n ${res.total_blanks} Ã´ trá»‘ng. ÄÃ£ tá»± Ä‘á»™ng dÃ¡n nhÃ£n ${autoCount} vÃ¹ng!`
        : `Táº£i lÃªn thÃ nh cÃ´ng! BÃ´i Ä‘en vÄƒn báº£n hoáº·c nháº¥p vÃ o vÃ¹ng trá»‘ng Ä‘á»ƒ dÃ¡n nhÃ£n.`, "success");
    } catch (err) {
      const detail = axios.isAxiosError(err) ? err.response?.data?.detail : null;
      showToast(typeof detail === "string" ? detail : "Lá»—i phÃ¢n tÃ­ch file Word", "error");
    } finally {
      setUploading(false);
    }
  };

  const handleSaveVisual = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formName || !procedureType) {
      showToast("Vui lÃ²ng nháº­p TÃªn Biá»ƒu máº«u vÃ  Loáº¡i thá»§ tá»¥c", "error");
      return;
    }
    const allFilled = labeledList.every(f => {
      const zone = previewData?.zones?.find((z: any) => String(z.idx) === f.blankIdx);
      const suggested = zone?.suggested_label || zone?.ai_label || "";
      const val = fieldData[f.id] !== undefined ? fieldData[f.id] : suggested;
      return val && val.trim() !== "";
    });
    if (!allFilled) {
      showToast("Vui lÃ²ng nháº­p TÃªn trÆ°á»ng dá»¯ liá»‡u cho Táº¤T Cáº¢ cÃ¡c nhÃ£n", "error");
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
      const defaultDesc = isCheckbox ? `CÃ³ hay khÃ´ng: ${finalName}?` : `Nháº­p thÃ´ng tin cho ${finalName}`;
      
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
      showToast("Táº¡o biá»ƒu máº«u thÃ nh cÃ´ng!", "success");
      fetchForms();
      resetModal();
    } catch {
      showToast("Lá»—i lÆ°u biá»ƒu máº«u", "error");
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
    if (!window.confirm("Báº¡n cÃ³ cháº¯c cháº¯n muá»‘n xÃ³a biá»ƒu máº«u nÃ y khÃ´ng?")) return;
    try {
      await formsApi.deleteForm(formId);
      fetchForms();
      showToast("ÄÃ£ xÃ³a biá»ƒu máº«u.", "success");
    } catch {
      console.error("Lá»—i khi xÃ³a");
    }
  };

  const openEdit = (form: any) => {
    setEditingForm(form);
    setEditName(form.name);
    setEditProcedure(form.procedure_type);
    setEditDesc(form.description || "");
    setEditFields(form.fields || []);
  };

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingForm || !editName.trim() || !editProcedure.trim()) {
      showToast("Vui lÃ²ng Ä‘iá»n Ä‘á»§ TÃªn vÃ  Loáº¡i thá»§ tá»¥c", "error");
      return;
    }
    setEditSaving(true);
    try {
      await formsApi.updateForm(editingForm.id, { name: editName, procedure_type: editProcedure, description: editDesc });
      showToast("Cáº­p nháº­t biá»ƒu máº«u thÃ nh cÃ´ng!", "success");
      setEditingForm(null);
      fetchForms();
    } catch {
      showToast("Lá»—i cáº­p nháº­t biá»ƒu máº«u", "error");
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
        .blank-zone::after { content: 'â†—'; font-size: 9px; color: #f59e0b; position: absolute; top: -4px; right: -2px; opacity: 0.7; }
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
          <span className="eyebrow">Há»‡ thá»‘ng</span>
          <h1>Quáº£n lÃ½ Biá»ƒu máº«u</h1>
          <p>Táº£i lÃªn file Word vÃ  AI sáº½ tá»± Ä‘á»™ng nháº­n diá»‡n khoáº£ng trá»‘ng.</p>
        </div>
        <div>
          <button className="primary-button fit" onClick={() => setShowModal(true)} style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
            <UploadCloud size={17} /> ThÃªm Biá»ƒu máº«u thÃ´ng minh
          </button>
        </div>
      </div>

      <section className="panel table-panel">
        <div className="table-wrap">
          <table>
            <thead><tr><th>TÃªn Biá»ƒu máº«u</th><th>Loáº¡i Thá»§ tá»¥c</th><th>NgÃ y táº¡o</th><th /></tr></thead>
            <tbody>
              {loading
                ? <tr><td colSpan={4} style={{ textAlign: "center", padding: "20px" }}>Äang táº£i...</td></tr>
                : forms.length === 0
                  ? <tr><td colSpan={4} style={{ textAlign: "center", padding: "20px" }}>ChÆ°a cÃ³ biá»ƒu máº«u nÃ o trong há»‡ thá»‘ng.</td></tr>
                  : forms.map(form => (
                    <tr key={form.id}>
                      <td><strong>{form.name}</strong></td>
                      <td><span className="status done">{form.procedure_type}</span></td>
                      <td>{new Date(form.created_at).toLocaleDateString("vi-VN")}</td>
                      <td>
                        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
                          <button onClick={() => openEdit(form)} className="icon-button" title="Chá»‰nh sá»­a" style={{ color: "#4f46e5" }}><Pencil size={17} /></button>
                          <button onClick={() => handleDelete(form.id)} className="icon-button" title="XÃ³a" style={{ color: "red" }}><Trash2 size={17} /></button>
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
              <h2>Chá»‰nh sá»­a Biá»ƒu máº«u</h2>
              <button type="button" className="icon-button" onClick={() => setEditingForm(null)}><X size={18} /></button>
            </div>
            <label style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 13, fontWeight: 600, marginBottom: 14 }}>
              TÃªn Biá»ƒu máº«u *
              <input value={editName} onChange={(e) => setEditName(e.target.value)} style={{ border: "1px solid #cfd7d1", padding: "10px 12px", borderRadius: 6, fontSize: 14 }} />
            </label>
            <label style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 13, fontWeight: 600, marginBottom: 14 }}>
              Loáº¡i thá»§ tá»¥c *
              <input value={editProcedure} onChange={(e) => setEditProcedure(e.target.value)} style={{ border: "1px solid #cfd7d1", padding: "10px 12px", borderRadius: 6, fontSize: 14 }} />
            </label>
            <label style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 13, fontWeight: 600, marginBottom: 14 }}>
              MÃ´ táº£ ngáº¯n
              <input value={editDesc} onChange={(e) => setEditDesc(e.target.value)} placeholder="MÃ´ táº£ tÃ¹y chá»n..." style={{ border: "1px solid #cfd7d1", padding: "10px 12px", borderRadius: 6, fontSize: 14 }} />
            </label>
            
            <div style={{ marginBottom: 20, display: "flex", flexDirection: "column", gap: 8 }}>
              <span style={{ fontSize: 13, fontWeight: 600 }}>NhÃ£n biá»ƒu máº«u (Fields)</span>
              <div style={{ maxHeight: "250px", overflowY: "auto", border: "1px solid #e2e8f0", borderRadius: 6, padding: "10px", display: "flex", flexDirection: "column", gap: 12, background: "#f8fafc" }}>
                {editFields.length === 0 && <span style={{ fontSize: 12, color: "#64748b" }}>KhÃ´ng cÃ³ nhÃ£n nÃ o.</span>}
                {editFields.map((field, idx) => (
                  <div key={idx} style={{ display: "flex", flexDirection: "column", gap: 6, padding: "8px", background: "white", border: "1px solid #cbd5e1", borderRadius: 6 }}>
                    <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                      <input 
                        value={field.name} 
                        onChange={(e) => {
                          const newFields = [...editFields];
                          newFields[idx].name = e.target.value;
                          setEditFields(newFields);
                        }}
                        placeholder="TÃªn hiá»ƒn thá»‹"
                        style={{ flex: 1, border: "1px solid #cbd5e1", padding: "6px", borderRadius: 4, fontSize: 12 }} 
                      />
                      <label style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 12, cursor: "pointer" }}>
                        <input 
                          type="checkbox" 
                          checked={field.required}
                          onChange={(e) => {
                            const newFields = [...editFields];
                            newFields[idx].required = e.target.checked;
                            setEditFields(newFields);
                          }}
                        /> Báº¯t buá»™c
                      </label>
                    </div>
                    <input 
                      value={field.description} 
                      onChange={(e) => {
                        const newFields = [...editFields];
                        newFields[idx].description = e.target.value;
                        setEditFields(newFields);
                      }}
                      placeholder="MÃ´ táº£ / HÆ°á»›ng dáº«n (thÃªm [TU_DONG_DIEN] náº¿u muá»‘n AI tá»± Ä‘á»™ng tra cá»©u KTT)"
                      style={{ border: "1px solid #cbd5e1", padding: "6px", borderRadius: 4, fontSize: 12 }} 
                    />
                  </div>
                ))}
              </div>
            </div>

            <div className="dialog-actions">
              <button type="button" className="secondary-button" onClick={() => setEditingForm(null)}>Há»§y</button>
              <button type="submit" className="primary-button" disabled={editSaving}>{editSaving ? "Äang lÆ°u..." : "LÆ°u thay Ä‘á»•i"}</button>
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
                      {s === 1 ? "Táº£i tá»‡p" : s === 2 ? "DÃ¡n nhÃ£n" : "Äáº·t tÃªn"}
                    </span>
                    {s < 3 && <span style={{ color: step === 2 || step === 3 ? "#475569" : "#d1d5db", marginLeft: 8 }}>â€º</span>}
                  </div>
                ))}
              </div>
              <button type="button" onClick={resetModal} style={{
                background: "none", border: 0, cursor: "pointer",
                color: step === 2 || step === 3 ? "#94a3b8" : "#6b7280", fontSize: "1.5rem", lineHeight: 1
              }}>Ã—</button>
            </div>

            {/* Step 1: Upload File */}
            {step === 1 && (
              <div style={{ padding: "24px", overflowY: "auto" }}>
                <h3 style={{ marginBottom: 8, fontSize: "1.1rem", fontWeight: 700 }}>BÆ°á»›c 1: Táº£i lÃªn file Word</h3>
                <p style={{ color: "#6b7280", marginBottom: 20, fontSize: "0.9rem" }}>Há»‡ thá»‘ng sáº½ phÃ¢n tÃ­ch tÃ i liá»‡u vÃ  xÃ¡c Ä‘á»‹nh cÃ¡c khoáº£ng trá»‘ng cáº§n Ä‘iá»n.</p>
                <form onSubmit={handleAnalyzeDocx}>
                  <div style={{
                    border: "2px dashed #d1d5db", borderRadius: 8, padding: "32px 24px",
                    textAlign: "center", marginBottom: 20, cursor: "pointer"
                  }} onClick={() => document.getElementById("docx-upload-input")?.click()}>
                    <UploadCloud size={32} style={{ color: "#9ca3af", margin: "0 auto 12px" }} />
                    <p style={{ fontWeight: 600, marginBottom: 4 }}>{docxFile ? docxFile.name : "KÃ©o tháº£ file Word (.docx) hoáº·c nháº¥p Ä‘á»ƒ chá»n"}</p>
                    <p style={{ fontSize: "0.8rem", color: "#9ca3af" }}>{docxFile ? `${(docxFile.size / 1024 / 1024).toFixed(1)} MB` : "Há»— trá»£ Ä‘á»‹nh dáº¡ng .docx"}</p>
                  </div>
                  <input id="docx-upload-input" type="file" accept=".docx,.doc" style={{ display: "none" }}
                    onChange={(e) => setDocxFile(e.target.files?.[0] ?? null)} />
                  <div style={{ display: "flex", justifyContent: "flex-end", gap: 12 }}>
                    <button type="button" onClick={resetModal} style={{ padding: "8px 16px", borderRadius: 6, border: "1px solid #d1d5db", background: "#fff", cursor: "pointer", fontWeight: 500 }}>Há»§y</button>
                    <button type="submit" className="primary-button" disabled={!docxFile || uploading}>{uploading ? "Äang phÃ¢n tÃ­ch..." : "PhÃ¢n tÃ­ch & Tiáº¿p tá»¥c"}</button>
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
                      ÄÃ£ dÃ¡n nhÃ£n: <strong style={{ color: "#4f46e5" }}>{labeledCount}</strong> / {editableZones.length} vÃ¹ng
                    </div>
                  </div>

                  <div style={{ overflowY: "auto", flex: 1, padding: "16px" }}>
                    {step === 3 ? (
                      <form id="save-form" onSubmit={handleSaveVisual}>
                        <label style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 13, fontWeight: 600, marginBottom: 14 }}>
                          TÃªn Biá»ƒu máº«u *
                          <input value={formName} onChange={(e) => setFormName(e.target.value)} placeholder="VD: ÄÆ¡n Ä‘Äƒng kÃ½ cáº¥p Ä‘á»•i GCN"
                            style={{ width: "100%", padding: "8px", border: "1px solid #d1d5db", borderRadius: "6px" }} />
                        </label>
                        <label style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 13, fontWeight: 600, marginBottom: 14 }}>
                          Loáº¡i thá»§ tá»¥c *
                          <input value={procedureType} onChange={(e) => setProcedureType(e.target.value)} placeholder="VD: cap_doi"
                            style={{ width: "100%", padding: "8px", border: "1px solid #d1d5db", borderRadius: "6px" }} />
                        </label>
                        <hr style={{ margin: "20px 0", borderColor: "#e5e7eb" }} />

                        {/* FIX BUG 1: Show suggested_label hint so user knows which zone = which number */}
                        <h4 style={{ marginBottom: 16, color: "#4f46e5" }}>
                          Nháº­p TÃªn trÆ°á»ng dá»¯ liá»‡u cho {labeledList.length} nhÃ£n Ä‘Ã£ chá»n:
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
                                    }} title={`AI gá»£i Ã½: ${suggestedLabel}`}>
                                      {suggestedLabel.length > 12 ? suggestedLabel.substring(0, 12) + "â€¦" : suggestedLabel}
                                    </div>
                                  )}
                                </div>
                                <div style={{ flex: 1, minWidth: 0 }}>
                                  {/* BUG 1 FIX: Show full suggested label as placeholder for easier identification */}
                                  <input
                                    type="text"
                                    placeholder={isCheckbox
                                      ? `NhÃ£n ${field.num}${suggestedLabel ? ` (gá»£i Ã½: ${suggestedLabel})` : ""} (VD: ca_nhan_cu_tru...)`
                                      : `NhÃ£n ${field.num}${suggestedLabel ? ` (gá»£i Ã½: ${suggestedLabel})` : ""} (VD: Há» tÃªn, NgÃ y sinh...)`}
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
                                      Báº¯t buá»™c Ä‘iá»n
                                    </label>
                                    <input 
                                      type="text" 
                                      placeholder="MÃ´ táº£ / Äiá»u kiá»‡n (vd: Chá»‰ Ä‘iá»n khi khÃ´ng cÃ³ MST)"
                                      value={fieldDesc[field.id] || ""}
                                      onChange={(e) => setFieldDesc({ ...fieldDesc, [field.id]: e.target.value })}
                                      style={{ flex: 1, padding: "4px 8px", fontSize: "0.75rem", border: "1px solid #d1d5db", borderRadius: "4px" }}
                                    />
                                  </div>

                                  {/* BUG 1 FIX: Show zone number in a more visible way to correlate with PDF */}
                                  {field.blankIdx && (
                                    <div style={{ fontSize: "0.7rem", color: "#9ca3af", marginTop: 6 }}>
                                      VÃ¹ng #{field.blankIdx} trÃªn PDF
                                    </div>
                                  )}
                                </div>
                                {isCheckbox && (
                                  <span style={{
                                    fontSize: "0.75rem", background: "#4f46e5", color: "#fff",
                                    padding: "2px 8px", borderRadius: "12px", flexShrink: 0, fontWeight: 600
                                  }}>â˜‘ Checkbox</span>
                                )}
                              </div>
                            </div>
                          );
                        })}

                        <div style={{ display: "flex", justifyContent: "flex-end", gap: 12, marginTop: 24 }}>
                          <button type="button" onClick={() => setStep(2)} style={{ padding: "8px 16px", borderRadius: "6px", border: "1px solid #d1d5db", backgroundColor: "#fff", cursor: "pointer", fontWeight: 500 }}>Quay láº¡i</button>
                          <button type="submit" className="primary-button" disabled={uploading}>{uploading ? "Äang lÆ°u..." : "LÆ°u Biá»ƒu máº«u"}</button>
                        </div>
                      </form>
                    ) : (
                      <div>
                        <p style={{ color: "#6b7280", fontSize: "0.875rem", marginBottom: 16 }}>
                          Nháº¥p vÃ o vÃ¹ng trá»‘ng trÃªn PDF bÃªn pháº£i Ä‘á»ƒ dÃ¡n nhÃ£n. Sau khi xong, nháº¥n "Tiáº¿p theo".
                        </p>
                        {labeledCount > 0 && (
                          <>
                            <div style={{ fontSize: "0.8rem", color: "#059669", background: "#ecfdf5", padding: "8px 12px", borderRadius: 6, marginBottom: 12 }}>
                              âœ“ ÄÃ£ chá»n {labeledCount} vÃ¹ng Ä‘á»ƒ dÃ¡n nhÃ£n
                            </div>
                            <div style={{ fontSize: "0.8rem", color: "#4b5563", background: "#f3f4f6", padding: "8px 12px", borderRadius: 6 }}>
                              <strong>LÆ°u Ã½:</strong> Báº¡n cÃ³ thá»ƒ xem vÃ  chá»‰nh sá»­a tÃªn chi tiáº¿t cá»§a cÃ¡c nhÃ£n nÃ y á»Ÿ <strong>BÆ°á»›c 3 (Tiáº¿p theo)</strong>.
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
                        {m === "label" ? "ðŸ· DÃ¡n nhÃ£n" : m === "add" ? "âž• ThÃªm vÃ¹ng" : m === "merge" ? `ðŸ”€ Gá»™p${mergeCount > 0 ? ` (${mergeCount})` : ""}` : "ðŸ—‘ XÃ³a vÃ¹ng"}
                      </button>
                    ))}
                    {mode === "merge" && mergeCount >= 2 && (
                      <button onClick={handleMerge} style={{ padding: "6px 12px", borderRadius: 6, border: "none", background: "#f59e0b", color: "#fff", cursor: "pointer", fontWeight: 600, fontSize: "0.8rem" }}>
                        Gá»™p {mergeCount} vÃ¹ng
                      </button>
                    )}
                    <div style={{ marginLeft: "auto" }}>
                      {step === 2 && labeledCount > 0 && (
                        <button onClick={() => {
                          setLabeledSnapshot({ ...labeledZonesRef.current });
                          setFieldOrderSnapshot([...fieldOrderRef.current]);
                          setStep(3);
                        }} style={{ padding: "6px 16px", borderRadius: 6, border: "none", background: "#10b981", color: "#fff", cursor: "pointer", fontWeight: 600, fontSize: "0.85rem" }}>
                          Tiáº¿p theo â†’
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
                              showToast(`ÄÃ£ gÃ¡n nhÃ£n: ${cleanText}`, "success");
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
                        ÄÃ£ chá»n <strong style={{ color: "#4f46e5" }}>{labeledCount}</strong> nhÃ£n
                      </span>
                      <button
                        onClick={() => {
                          if (labeledCount === 0) { showToast("Vui lÃ²ng dÃ¡n nhÃ£n Ã­t nháº¥t 1 vÃ¹ng", "error"); return; }
                          setLabeledSnapshot({ ...labeledZonesRef.current });
                          setFieldOrderSnapshot([...fieldOrderRef.current]);
                          setStep(3);
                        }}
                        style={{ padding: "8px 20px", borderRadius: 6, border: "none", background: "#4f46e5", color: "#fff", cursor: "pointer", fontWeight: 600 }}
                      >
                        Tiáº¿p theo â†’
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

// â”€â”€â”€ Admin Portal â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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
            <div><strong>{userName}</strong><small>Quáº£n trá»‹ viÃªn</small></div>
            <button className="icon-button mobile-only" onClick={() => setSidebar(false)}><X /></button>
          </div>
          <p className="section-label">Váº­n hÃ nh</p>
          <nav>
            {adminNav.map(item => (
              <button key={item.id} className={view === item.id ? "active" : ""} onClick={() => { setView(item.id); setSidebar(false); }}>
                <item.icon size={18} />{item.label}
              </button>
            ))}
          </nav>
          <p className="section-label">Há»‡ thá»‘ng</p>
          <nav>
            <button className={view === "users" ? "active" : ""} onClick={() => { setView("users"); setSidebar(false); }}><Users size={18} />NgÆ°á»i dÃ¹ng</button>
            <button><Settings size={18} />Cáº¥u hÃ¬nh</button>
          </nav>
          <div className="admin-version"><ShieldCheck size={17} /><span><strong>TerraLegalAI</strong><small>PhiÃªn báº£n 0.1.0</small></span></div>
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

  if (authLoading) return <main className="auth-loading">Äang kiá»ƒm tra phiÃªn Ä‘Äƒng nháº­p...</main>;
  if (!user) return authView === "login"
    ? <Login onLogin={(role) => authApi.me().then(u => u && setUser({ role, full_name: u.full_name }))} onRegister={() => setAuthView("register")} />
    : <Register onBack={() => setAuthView("login")} onRegister={(role) => authApi.me().then(u => u && setUser({ role, full_name: u.full_name }))} />;
  return user.role === "admin" ? <AdminPortal userName={user.full_name} onLogout={logout} /> : <UserPortal userName={user.full_name} onLogout={logout} />;
}
