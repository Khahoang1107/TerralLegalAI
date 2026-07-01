"use client";

import axios from "axios";
import { useEffect, useState, useRef } from "react";
import { authApi, chatApi, conversationApi, type Citation, type Conversation } from "@/lib/api";
import {
  BarChart3, BookOpen, Bot, Check, ChevronDown, CircleAlert, Clock3,
  FileCheck2, FileText, LayoutDashboard, LogOut,
  Menu, MessageSquare, MoreHorizontal, Paperclip, Pencil, Plus, RefreshCw, Search,
  Send, Settings, ShieldCheck, Sparkles, TestTube2, ThumbsDown, ThumbsUp,
  Trash2, UploadCloud, User, Users, X,
} from "lucide-react";

type Role = "citizen" | "admin";
type AdminView = "overview" | "documents" | "tests" | "reports";

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



const documents = [
  { name: "QĐ 1085 - Bộ thủ tục hành chính", type: "PDF", date: "30/06/2026", status: "Hoàn thành", chunks: 184 },
  { name: "QĐ 1467 - Quy trình nội bộ", type: "PDF", date: "30/06/2026", status: "Hoàn thành", chunks: 96 },
  { name: "Biểu mẫu đăng ký biến động", type: "DOCX", date: "01/07/2026", status: "Đang xử lý", chunks: 0 },
];

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
    // Tải danh sách lịch sử khi component mount
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
    if (!window.confirm(`Xóa cuộc trò chuyện “${conversation.title}”?`)) return;

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
    <section className="panel"><div className="panel-title"><div><h2>Cần chú ý</h2><p>Các câu hỏi có độ tin cậy thấp cần cán bộ rà soát</p></div><button className="text-button">Xem tất cả</button></div><div className="issue-list"><div><CircleAlert /><span><strong>“Trường hợp mất sổ đỏ cần làm gì?”</strong><small>Độ tin cậy 43% · Cấp lại GCN</small></span><button>Kiểm tra</button></div><div><CircleAlert /><span><strong>“Có thể nộp hồ sơ trực tuyến không?”</strong><small>Độ tin cậy 51% · Nộp hồ sơ</small></span><button>Kiểm tra</button></div></div></section></>;
}

function DocumentsView() {
  return <><div className="page-heading"><div><span className="eyebrow">Kho tri thức</span><h1>Quản lý tài liệu</h1><p>Cập nhật, kiểm duyệt và theo dõi quá trình lập chỉ mục.</p></div><button className="primary-button fit"><UploadCloud size={17} /> Tải tài liệu lên</button></div>
    <div className="upload-zone"><UploadCloud size={28} /><div><strong>Kéo thả PDF hoặc DOCX vào đây</strong><span>Tối đa 200 MB mỗi tệp · Hệ thống sẽ kiểm tra trước khi index</span></div><button className="secondary-button">Chọn tệp</button></div>
    <section className="panel table-panel"><div className="table-tools"><div className="sidebar-search"><Search size={16} /><input placeholder="Tìm theo tên văn bản" /></div><select className="compact-select"><option>Tất cả trạng thái</option><option>Hoàn thành</option><option>Đang xử lý</option><option>Lỗi</option></select></div><div className="table-wrap"><table><thead><tr><th>Tài liệu</th><th>Ngày cập nhật</th><th>Chunks</th><th>Trạng thái</th><th /></tr></thead><tbody>{documents.map(doc => <tr key={doc.name}><td><div className="document-name"><FileText size={19} /><span><strong>{doc.name}</strong><small>{doc.type}</small></span></div></td><td>{doc.date}</td><td>{doc.chunks || "—"}</td><td><span className={`status ${doc.status === "Hoàn thành" ? "done" : "processing"}`}>{doc.status === "Hoàn thành" ? <Check size={13} /> : <Clock3 size={13} />}{doc.status}</span></td><td><button className="icon-button"><MoreHorizontal size={18} /></button></td></tr>)}</tbody></table></div></section></>;
}

function TestsView() { return <><div className="page-heading"><div><span className="eyebrow">Đánh giá định kỳ</span><h1>Bộ kiểm thử</h1><p>Quản lý câu hỏi và câu trả lời chuẩn dùng để đánh giá AI.</p></div><button className="primary-button fit"><Plus size={17} /> Thêm test case</button></div><section className="panel"><div className="test-summary"><div><strong>15</strong><span>Tổng test case</span></div><div><strong>13</strong><span>Đạt yêu cầu</span></div><div><strong>2</strong><span>Cần rà soát</span></div><button className="secondary-button"><TestTube2 size={16} /> Chạy đánh giá</button></div><div className="test-list"><div><span className="test-id">TC-001</span><div><strong>Hồ sơ cấp đổi Giấy chứng nhận gồm những gì?</strong><p>Ground truth: Đơn đăng ký biến động, bản gốc Giấy chứng nhận...</p></div><span className="status done"><Check size={13} /> Đạt</span><button className="icon-button"><MoreHorizontal /></button></div><div><span className="test-id">TC-002</span><div><strong>Thời hạn cấp đổi sổ đỏ là bao lâu?</strong><p>Ground truth: Không quá thời hạn quy định theo từng địa bàn...</p></div><span className="status processing"><Clock3 size={13} /> Rà soát</span><button className="icon-button"><MoreHorizontal /></button></div></div></section></>; }

function ReportsView() { return <><div className="page-heading"><div><span className="eyebrow">Theo dõi sử dụng</span><h1>Nhật ký & báo cáo</h1><p>Phân tích nhu cầu tra cứu và các trường hợp AI chưa giải quyết tốt.</p></div><button className="secondary-button"><FileText size={16} /> Xuất báo cáo</button></div><section className="admin-grid"><div className="panel"><div className="panel-title"><div><h2>Chủ đề được hỏi nhiều</h2><p>30 ngày gần nhất</p></div></div><div className="topic-list"><div><span>Cấp đổi Giấy chứng nhận</span><strong>38%</strong><i style={{ width: "38%" }} /></div><div><span>Chuyển nhượng đất</span><strong>29%</strong><i style={{ width: "29%" }} /></div><div><span>Thời hạn giải quyết</span><strong>18%</strong><i style={{ width: "18%" }} /></div></div></div><div className="panel"><div className="panel-title"><div><h2>Phản hồi người dùng</h2><p>328 lượt đánh giá</p></div></div><div className="feedback-score"><div><ThumbsUp /><strong>91%</strong><span>Hữu ích</span></div><div><ThumbsDown /><strong>9%</strong><span>Chưa hữu ích</span></div></div></div></section><section className="panel"><div className="panel-title"><div><h2>Câu hỏi fallback gần đây</h2><p>Cần bổ sung dữ liệu hoặc điều chỉnh truy xuất</p></div></div><div className="log-list"><div><time>09:42</time><span><strong>Thủ tục tách thửa đối với đất đang tranh chấp?</strong><small>Không tìm thấy ngữ cảnh đủ tin cậy · similarity 0.41</small></span><button>Rà soát</button></div><div><time>08:15</time><span><strong>Lệ phí cấp lại GCN năm 2026?</strong><small>Tài liệu hiện tại chưa có biểu phí · similarity 0.38</small></span><button>Rà soát</button></div></div></section></>; }

function AdminPortal({ userName, onLogout }: { userName: string; onLogout: () => void }) {
  const [view, setView] = useState<AdminView>("overview"); const [sidebar, setSidebar] = useState(false);
  const initials = userName.split(" ").map(n => n[0]).join("").substring(0, 2).toUpperCase();
  return <div className="app-shell"><AppHeader role="admin" userName={userName} onLogout={onLogout} onMenu={() => setSidebar(true)} /><div className="workspace admin-workspace"><aside className={`admin-sidebar ${sidebar ? "open" : ""}`}><div className="admin-user"><span className="avatar">{initials}</span><div><strong>{userName}</strong><small>Quản trị viên</small></div><button className="icon-button mobile-only" onClick={() => setSidebar(false)}><X /></button></div><p className="section-label">Vận hành</p><nav>{adminNav.map(item => <button key={item.id} className={view === item.id ? "active" : ""} onClick={() => { setView(item.id); setSidebar(false); }}><item.icon size={18} />{item.label}</button>)}</nav><p className="section-label">Hệ thống</p><nav><button><Users size={18} />Người dùng</button><button><Settings size={18} />Cấu hình</button></nav><div className="admin-version"><ShieldCheck size={17} /><span><strong>TerraLegalAI</strong><small>Phiên bản 0.1.0</small></span></div></aside>{sidebar && <button className="overlay" onClick={() => setSidebar(false)} />}<main className="admin-main">{view === "overview" && <Overview />}{view === "documents" && <DocumentsView />}{view === "tests" && <TestsView />}{view === "reports" && <ReportsView />}</main></div></div>;
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
