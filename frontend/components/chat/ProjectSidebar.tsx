"use client";

import React, { useState, useEffect, useMemo } from "react";
import {
  Plus, Search, MessageSquare, MoreHorizontal, Pencil, Trash2,
  FolderPlus, Folder, FolderOpen, ChevronDown, ChevronRight,
  BookOpen, FolderInput, Check, X, ShieldAlert, Sparkles, Layers,
  MessageSquarePlus
} from "lucide-react";
import type { Conversation } from "@/lib/api";

export interface LegalProject {
  id: string;
  name: string;
  procedure_type: string; // e.g. "chuyen_nhuong", "cap_doi", "thua_ke", "all"
  color: string;
  created_at: string;
  conversation_ids: string[];
}

const DEFAULT_PROJECTS: LegalProject[] = [
  {
    id: "proj_chuyen_nhuong",
    name: "Hồ sơ Chuyển nhượng QSDĐ",
    procedure_type: "chuyen_nhuong",
    color: "#166b45",
    created_at: new Date().toISOString(),
    conversation_ids: [],
  },
  {
    id: "proj_cap_doi",
    name: "Cấp đổi & Cấp lại Giấy chứng nhận",
    procedure_type: "cap_doi",
    color: "#2563eb",
    created_at: new Date().toISOString(),
    conversation_ids: [],
  },
];

const PROCEDURE_OPTIONS = [
  { id: "all", label: "Tất cả thủ tục" },
  { id: "chuyen_nhuong", label: "Chuyển nhượng / Mua bán đất" },
  { id: "cap_doi", label: "Cấp đổi / Cấp lại Sổ đỏ" },
  { id: "thua_ke", label: "Thừa kế / Tặng cho đất đai" },
  { id: "tach_thua", label: "Tách thửa / Hợp thửa" },
  { id: "chuyen_muc_dich", label: "Chuyển mục đích sử dụng đất" },
  { id: "dang_ky_bien_dong", label: "Đăng ký biến động đất đai" },
];

interface ProjectSidebarProps {
  isOpen: boolean;
  onClose: () => void;
  conversationsList: Conversation[];
  currentConversationId: string | null;
  onSelectConversation: (id: string) => void;
  onNewChat: () => void;
  onOpenRename: (conv: Conversation) => void;
  onDeleteConversation: (conv: Conversation) => void;
  selectedProjectId: string | null;
  onSelectProject: (projectId: string | null) => void;
}

export default function ProjectSidebar({
  isOpen,
  onClose,
  conversationsList,
  currentConversationId,
  onSelectConversation,
  onNewChat,
  onOpenRename,
  onDeleteConversation,
  selectedProjectId,
  onSelectProject,
}: ProjectSidebarProps) {
  const [projects, setProjects] = useState<LegalProject[]>([]);
  const [expandedProjects, setExpandedProjects] = useState<Record<string, boolean>>({
    proj_chuyen_nhuong: true,
    proj_cap_doi: true,
  });
  const [searchQuery, setSearchQuery] = useState("");
  const [activeMenuId, setActiveMenuId] = useState<string | null>(null);
  const [moveMenuId, setMoveMenuId] = useState<string | null>(null);

  // New Project Dialog State
  const [isCreatingProject, setIsCreatingProject] = useState(false);
  const [newProjectName, setNewProjectName] = useState("");
  const [newProjectProcedure, setNewProjectProcedure] = useState("all");
  const [newProjectColor, setNewProjectColor] = useState("#166b45");

  // Project Rename Dialog
  const [renamingProject, setRenamingProject] = useState<LegalProject | null>(null);
  const [projectRenameTitle, setProjectRenameTitle] = useState("");

  // Load projects from localStorage
  useEffect(() => {
    try {
      const saved = localStorage.getItem("terra_legal_projects");
      if (saved) {
        const parsed: LegalProject[] = JSON.parse(saved);
        if (Array.isArray(parsed) && parsed.length > 0) {
          setProjects(parsed);
          return;
        }
      }
      // If no saved projects, init default
      setProjects(DEFAULT_PROJECTS);
      localStorage.setItem("terra_legal_projects", JSON.stringify(DEFAULT_PROJECTS));
    } catch {
      setProjects(DEFAULT_PROJECTS);
    }
  }, []);

  // Save projects to localStorage
  const saveProjects = (updated: LegalProject[]) => {
    setProjects(updated);
    try {
      localStorage.setItem("terra_legal_projects", JSON.stringify(updated));
    } catch (err) {
      console.error("Failed to save projects:", err);
    }
  };

  // Toggle project expansion
  const toggleProject = (projectId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setExpandedProjects((prev) => ({
      ...prev,
      [projectId]: prev[projectId] === undefined ? false : !prev[projectId],
    }));
  };

  // Auto assign current conversation if project is active and conversation is not assigned
  useEffect(() => {
    if (!currentConversationId || !selectedProjectId) return;
    setProjects((prev) => {
      const targetProj = prev.find((p) => p.id === selectedProjectId);
      if (!targetProj) return prev;
      if (targetProj.conversation_ids.includes(currentConversationId)) return prev;

      // Remove from other projects and add to target
      const updated = prev.map((p) => {
        if (p.id === selectedProjectId) {
          return { ...p, conversation_ids: [...p.conversation_ids, currentConversationId] };
        }
        return {
          ...p,
          conversation_ids: p.conversation_ids.filter((id) => id !== currentConversationId),
        };
      });
      try {
        localStorage.setItem("terra_legal_projects", JSON.stringify(updated));
      } catch (e) {
        console.error(e);
      }
      return updated;
    });
  }, [currentConversationId, selectedProjectId]);

  // Handle create project
  const handleCreateProject = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newProjectName.trim()) return;

    const newProj: LegalProject = {
      id: "proj_" + Date.now().toString(36),
      name: newProjectName.trim(),
      procedure_type: newProjectProcedure,
      color: newProjectColor,
      created_at: new Date().toISOString(),
      conversation_ids: currentConversationId ? [currentConversationId] : [],
    };

    const updated = [newProj, ...projects];
    saveProjects(updated);
    setExpandedProjects((prev) => ({ ...prev, [newProj.id]: true }));
    onSelectProject(newProj.id);
    setIsCreatingProject(false);
    setNewProjectName("");
  };

  // Handle rename project
  const handleRenameProject = (e: React.FormEvent) => {
    e.preventDefault();
    if (!renamingProject || !projectRenameTitle.trim()) return;

    const updated = projects.map((p) =>
      p.id === renamingProject.id ? { ...p, name: projectRenameTitle.trim() } : p
    );
    saveProjects(updated);
    setRenamingProject(null);
  };

  // Handle delete project
  const handleDeleteProject = (proj: LegalProject) => {
    if (!window.confirm(`Xác nhận xóa dự án "${proj.name}"? (Các cuộc trò chuyện vẫn được giữ lại trong mục Chung)`)) {
      return;
    }
    const updated = projects.filter((p) => p.id !== proj.id);
    saveProjects(updated);
    if (selectedProjectId === proj.id) {
      onSelectProject(null);
    }
  };

  // Move conversation to project
  const handleMoveToProject = (convId: string, targetProjectId: string | null) => {
    const updated = projects.map((p) => {
      if (targetProjectId && p.id === targetProjectId) {
        const exists = p.conversation_ids.includes(convId);
        return exists ? p : { ...p, conversation_ids: [...p.conversation_ids, convId] };
      }
      return {
        ...p,
        conversation_ids: p.conversation_ids.filter((id) => id !== convId),
      };
    });
    saveProjects(updated);
    setMoveMenuId(null);
    setActiveMenuId(null);
    if (targetProjectId) {
      onSelectProject(targetProjectId);
      setExpandedProjects((prev) => ({ ...prev, [targetProjectId]: true }));
    }
  };

  // Create new chat specifically inside a project
  const handleNewChatInProject = (projectId: string, e?: React.MouseEvent) => {
    e?.stopPropagation();
    onSelectProject(projectId);
    setExpandedProjects((prev) => ({ ...prev, [projectId]: true }));
    onNewChat();
  };

  // Prevent the browser's address-bar search shortcut and use Ctrl/Cmd + K
  // for the action advertised on the new-chat button.
  useEffect(() => {
    const handleShortcut = (event: KeyboardEvent) => {
      if (!(event.ctrlKey || event.metaKey) || event.key.toLowerCase() !== "k") return;

      const target = event.target as HTMLElement | null;
      if (target?.matches("input, textarea, select, [contenteditable='true']")) return;

      event.preventDefault();
      onSelectProject(null);
      onNewChat();
    };

    window.addEventListener("keydown", handleShortcut);
    return () => window.removeEventListener("keydown", handleShortcut);
  }, [onNewChat, onSelectProject]);

  // Filter conversations
  const filteredConversations = useMemo(() => {
    if (!searchQuery.trim()) return conversationsList;
    const q = searchQuery.toLowerCase();
    return conversationsList.filter((c) => c.title.toLowerCase().includes(q));
  }, [conversationsList, searchQuery]);

  // Unassigned conversations (conversations not inside any project)
  const assignedConvIds = useMemo(() => {
    const set = new Set<string>();
    projects.forEach((p) => p.conversation_ids.forEach((id) => set.add(id)));
    return set;
  }, [projects]);

  const unassignedConversations = useMemo(() => {
    return filteredConversations.filter((c) => !assignedConvIds.has(c.id));
  }, [filteredConversations, assignedConvIds]);

  return (
    <>
      <aside className={`chat-sidebar modern-sidebar ${isOpen ? "open" : ""}`}>
        {/* Top Actions: Redesigned modern, balanced & elegant */}
        <div className="sidebar-top-actions">
          <button 
            type="button" 
            className="new-chat-btn-modern" 
            onClick={() => {
              onSelectProject(null);
              onNewChat();
            }} 
            title="Tạo cuộc trò chuyện mới (Phím tắt: Ctrl + K)"
          >
            <div className="new-chat-icon-wrap">
              <Plus size={15} />
            </div>
            <span className="new-chat-text">Cuộc trò chuyện mới</span>
            <kbd className="new-chat-shortcut">Ctrl K</kbd>
          </button>

          <button
            type="button"
            className="create-project-btn-modern"
            onClick={() => setIsCreatingProject(true)}
            title="Tạo Dự án / Hồ sơ đất đai mới"
          >
            <FolderPlus size={15} className="folder-add-icon" />
            <span>Tạo Dự án / Hồ sơ mới</span>
          </button>
        </div>

        {/* Search Bar */}
        <div className="sidebar-search">
          <Search size={15} />
          <input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Tìm kiếm dự án & lịch sử..."
          />
          {searchQuery && (
            <button
              type="button"
              className="clear-search-btn"
              onClick={() => setSearchQuery("")}
            >
              <X size={13} />
            </button>
          )}
        </div>

        {/* Scrollable Body containing Projects & Conversations */}
        <div className="sidebar-scrollable-content custom-scrollbar">
          {/* Projects Section */}
          <div className="sidebar-section">
            <div className="section-header-row">
              <span className="section-label">
                <Layers size={13} style={{ display: "inline", marginRight: 5 }} />
                Dự án của bạn ({projects.length})
              </span>
            </div>

            <div className="projects-container">
              {projects.map((proj) => {
                const isSelected = selectedProjectId === proj.id;
                const isExpanded = expandedProjects[proj.id] !== false;
                const projConversations = filteredConversations.filter((c) =>
                  proj.conversation_ids.includes(c.id)
                );

                return (
                  <div
                    key={proj.id}
                    className={`project-group-item ${isSelected ? "active-project" : ""}`}
                  >
                    {/* Project Folder Bar */}
                    <div
                      className="project-folder-row"
                      onClick={() => {
                        onSelectProject(proj.id);
                        if (!isExpanded) {
                          setExpandedProjects((prev) => ({ ...prev, [proj.id]: true }));
                        }
                      }}
                    >
                      <button
                        type="button"
                        className="folder-toggle-btn"
                        onClick={(e) => toggleProject(proj.id, e)}
                        title={isExpanded ? "Thu gọn" : "Mở rộng"}
                      >
                        {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                      </button>

                      <div className="project-icon-box" style={{ color: proj.color }}>
                        {isExpanded ? <FolderOpen size={16} /> : <Folder size={16} />}
                      </div>

                      <div className="project-info-text">
                        <span className="project-title" title={proj.name}>
                          {proj.name}
                        </span>
                        <span className="project-sub">
                          {projConversations.length} cuộc trò chuyện
                        </span>
                      </div>

                      {/* Quick Add Chat directly in this Project */}
                      <button
                        type="button"
                        className="project-quick-add-btn"
                        onClick={(e) => handleNewChatInProject(proj.id, e)}
                        title={`Tạo cuộc trò chuyện mới trong dự án ${proj.name}`}
                      >
                        <Plus size={14} strokeWidth={2.5} />
                      </button>

                      {/* Project Options Menu */}
                      <div className="project-options-container" onClick={(e) => e.stopPropagation()}>
                        <button
                          type="button"
                          className="project-menu-btn"
                          onClick={() =>
                            setActiveMenuId(activeMenuId === proj.id ? null : proj.id)
                          }
                          title="Tùy chọn dự án"
                        >
                          <MoreHorizontal size={14} />
                        </button>
                        {activeMenuId === proj.id && (
                          <div className="conversation-menu proj-menu">
                            <button
                              type="button"
                              className="proj-add-chat-item"
                              onClick={() => {
                                handleNewChatInProject(proj.id);
                                setActiveMenuId(null);
                              }}
                            >
                              <MessageSquarePlus size={14} /> Thêm chat vào dự án
                            </button>
                            <button
                              type="button"
                              onClick={() => {
                                setRenamingProject(proj);
                                setProjectRenameTitle(proj.name);
                                setActiveMenuId(null);
                              }}
                            >
                              <Pencil size={14} /> Đổi tên dự án
                            </button>
                            <button
                              type="button"
                              className="danger"
                              onClick={() => {
                                handleDeleteProject(proj);
                                setActiveMenuId(null);
                              }}
                            >
                              <Trash2 size={14} /> Xóa dự án
                            </button>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Sub-conversations in this project */}
                    {isExpanded && (
                      <div className="project-conv-children">
                        {projConversations.length === 0 ? (
                          <div className="empty-project-conv-box">
                            <span className="empty-conv-hint">Chưa có đoạn chat trong dự án này</span>
                            <button
                              type="button"
                              className="btn-create-chat-in-proj"
                              onClick={() => handleNewChatInProject(proj.id)}
                            >
                              <MessageSquarePlus size={14} color="#ffffff" />
                              <span>+ Bắt đầu chat trong dự án</span>
                            </button>
                          </div>
                        ) : (
                          <>
                            {projConversations.map((item) => {
                              const isActiveChat = currentConversationId === item.id;
                              return (
                                <div
                                  key={item.id}
                                  className={`conversation-item child-item ${isActiveChat ? "active" : ""}`}
                                >
                                  <button
                                    className="conversation-select"
                                    onClick={() => {
                                      onSelectConversation(item.id);
                                      onSelectProject(proj.id);
                                    }}
                                    title={item.title}
                                  >
                                    <MessageSquare size={14} className="conv-icon" />
                                    <span>
                                      <strong>{item.title}</strong>
                                      <small>{new Date(item.created_at).toLocaleDateString("vi-VN")}</small>
                                    </span>
                                  </button>

                                  <button
                                    type="button"
                                    className="conversation-menu-trigger"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      setActiveMenuId(activeMenuId === item.id ? null : item.id);
                                    }}
                                    title="Tùy chọn cuộc trò chuyện"
                                  >
                                    <MoreHorizontal size={15} />
                                  </button>

                                  {activeMenuId === item.id && (
                                    <div
                                      className="conversation-menu"
                                      onClick={(e) => e.stopPropagation()}
                                    >
                                      <button
                                        type="button"
                                        onClick={() => {
                                          onOpenRename(item);
                                          setActiveMenuId(null);
                                        }}
                                      >
                                        <Pencil size={14} /> Đổi tên
                                      </button>
                                      <button
                                        type="button"
                                        onClick={() => setMoveMenuId(item.id)}
                                      >
                                        <FolderInput size={14} /> Chuyển dự án...
                                      </button>
                                      <button
                                        type="button"
                                        className="danger"
                                        onClick={() => {
                                          onDeleteConversation(item);
                                          setActiveMenuId(null);
                                        }}
                                      >
                                        <Trash2 size={14} /> Xóa
                                      </button>
                                    </div>
                                  )}
                                </div>
                              );
                            })}

                            <button
                              type="button"
                              className="btn-add-more-chat-in-proj"
                              onClick={() => handleNewChatInProject(proj.id)}
                              title="Tạo cuộc trò chuyện mới trong dự án này"
                            >
                              <Plus size={13} />
                              <span>Thêm cuộc trò chuyện mới</span>
                            </button>
                          </>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Unassigned / Recent Conversations */}
          <div className="sidebar-section" style={{ marginTop: "16px" }}>
            <div className="section-header-row">
              <span className="section-label">Cuộc trò chuyện chung / Gần đây</span>
            </div>

            <nav className="conversation-list">
              {unassignedConversations.length === 0 ? (
                <div className="empty-state-notice">
                  {searchQuery
                    ? "Không tìm thấy cuộc trò chuyện phù hợp"
                    : "Mọi cuộc trò chuyện đã được phân loại vào các Dự án."}
                </div>
              ) : (
                unassignedConversations.map((item, index) => {
                  const isActiveChat = currentConversationId === item.id;
                  // The last rows sit next to the sidebar footer. Open their
                  // contextual menu upward so it remains inside the scroll area.
                  const menuOpensUpward = index >= unassignedConversations.length - 2;
                  return (
                    <div
                      className={`conversation-item ${isActiveChat ? "active" : ""}`}
                      key={item.id}
                    >
                      <button
                        className="conversation-select"
                        onClick={() => {
                          onSelectConversation(item.id);
                          onSelectProject(null);
                        }}
                      >
                        <MessageSquare size={15} className="conv-icon" />
                        <span>
                          <strong>{item.title}</strong>
                          <small>{new Date(item.created_at).toLocaleDateString("vi-VN")}</small>
                        </span>
                      </button>

                      <button
                        type="button"
                        className="conversation-menu-trigger"
                        onClick={(e) => {
                          e.stopPropagation();
                          setActiveMenuId(activeMenuId === item.id ? null : item.id);
                        }}
                        title="Tùy chọn cuộc trò chuyện"
                      >
                        <MoreHorizontal size={15} />
                      </button>

                      {activeMenuId === item.id && (
                        <div
                          className={`conversation-menu ${menuOpensUpward ? "opens-upward" : ""}`}
                          onClick={(e) => e.stopPropagation()}
                        >
                          <button
                            type="button"
                            onClick={() => {
                              onOpenRename(item);
                              setActiveMenuId(null);
                            }}
                          >
                            <Pencil size={14} /> Đổi tên
                          </button>
                          <button
                            type="button"
                            onClick={() => setMoveMenuId(item.id)}
                          >
                            <FolderInput size={14} /> Thêm vào dự án...
                          </button>
                          <button
                            type="button"
                            className="danger"
                            onClick={() => {
                              onDeleteConversation(item);
                              setActiveMenuId(null);
                            }}
                          >
                            <Trash2 size={14} /> Xóa
                          </button>
                        </div>
                      )}
                    </div>
                  );
                })
              )}
            </nav>
          </div>
        </div>

        {/* Sidebar Footer Help Widget */}
        <div className="sidebar-help">
          <BookOpen size={18} className="help-icon" />
          <div>
            <strong>Kho tri thức pháp lý</strong>
            <span>Luật Đất đai 2024 & Nghị định 101/2024</span>
          </div>
        </div>
      </aside>

      {/* Modal Move to Project */}
      {moveMenuId && (
        <div className="dialog-backdrop" onClick={() => setMoveMenuId(null)}>
          <div
            className="rename-dialog move-dialog"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="dialog-head">
              <h2>Chọn Dự án cho cuộc trò chuyện</h2>
              <button
                type="button"
                className="icon-button"
                onClick={() => setMoveMenuId(null)}
              >
                <X size={17} />
              </button>
            </div>
            <p className="dialog-desc">
              Phân loại cuộc trò chuyện để hệ thống đưa ra các gợi ý và văn bản đối chiếu chính xác theo hồ sơ dự án.
            </p>

            <div className="project-select-list">
              <button
                type="button"
                className="project-option-btn"
                onClick={() => handleMoveToProject(moveMenuId, null)}
              >
                <div className="proj-dot" style={{ background: "#8a948e" }} />
                <span>Không gán (Mục Chung / Gần đây)</span>
              </button>

              {projects.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  className="project-option-btn"
                  onClick={() => handleMoveToProject(moveMenuId, p.id)}
                >
                  <div className="proj-dot" style={{ background: p.color }} />
                  <div style={{ textAlign: "left", flex: 1 }}>
                    <strong>{p.name}</strong>
                    <small style={{ display: "block", color: "#6a7870" }}>
                      {PROCEDURE_OPTIONS.find((o) => o.id === p.procedure_type)?.label ||
                        p.procedure_type}
                    </small>
                  </div>
                </button>
              ))}
            </div>

            <div className="dialog-actions">
              <button
                type="button"
                className="secondary-button"
                onClick={() => setMoveMenuId(null)}
              >
                Đóng
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal Create Project */}
      {isCreatingProject && (
        <div className="dialog-backdrop" onClick={() => setIsCreatingProject(false)}>
          <form
            className="rename-dialog"
            onSubmit={handleCreateProject}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="dialog-head">
              <h2>Tạo Dự án / Hồ sơ đất đai mới</h2>
              <button
                type="button"
                className="icon-button"
                onClick={() => setIsCreatingProject(false)}
              >
                <X size={18} />
              </button>
            </div>

            <label>
              Tên Dự án / Hồ sơ
              <input
                autoFocus
                placeholder="VD: Mua bán căn hộ chung cư, Thừa kế đất gia đình..."
                value={newProjectName}
                onChange={(e) => setNewProjectName(e.target.value)}
                maxLength={120}
                required
              />
            </label>

            <label>
              Nhóm thủ tục đất đai chính
              <select
                value={newProjectProcedure}
                onChange={(e) => setNewProjectProcedure(e.target.value)}
                className="procedure-modal-select"
              >
                {PROCEDURE_OPTIONS.map((opt) => (
                  <option key={opt.id} value={opt.id}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </label>

            <div className="dialog-actions">
              <button
                type="button"
                className="secondary-button"
                onClick={() => setIsCreatingProject(false)}
              >
                Hủy
              </button>
              <button
                type="submit"
                className="primary-button"
                disabled={!newProjectName.trim()}
              >
                Tạo dự án
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Modal Rename Project */}
      {renamingProject && (
        <div className="dialog-backdrop" onClick={() => setRenamingProject(null)}>
          <form
            className="rename-dialog"
            onSubmit={handleRenameProject}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="dialog-head">
              <h2>Đổi tên dự án</h2>
              <button
                type="button"
                className="icon-button"
                onClick={() => setRenamingProject(null)}
              >
                <X size={18} />
              </button>
            </div>

            <label>
              Tên dự án mới
              <input
                autoFocus
                value={projectRenameTitle}
                onChange={(e) => setProjectRenameTitle(e.target.value)}
                maxLength={120}
                required
              />
            </label>

            <div className="dialog-actions">
              <button
                type="button"
                className="secondary-button"
                onClick={() => setRenamingProject(null)}
              >
                Hủy
              </button>
              <button
                type="submit"
                className="primary-button"
                disabled={!projectRenameTitle.trim()}
              >
                Lưu
              </button>
            </div>
          </form>
        </div>
      )}
    </>
  );
}
