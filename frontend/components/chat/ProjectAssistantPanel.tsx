"use client";

import React, { useState, useEffect, useMemo } from "react";
import {
  Sparkles, CheckSquare, FileText, ExternalLink, ChevronRight,
  ShieldCheck, HelpCircle, ArrowUpRight, CheckCircle2, Circle,
  Layers, Info, X, Clock, MapPin
} from "lucide-react";
import type { LegalProject } from "./ProjectSidebar";

interface ProjectAssistantPanelProps {
  isOpen: boolean;
  onClose?: () => void;
  selectedProject: LegalProject | null;
  onSelectSuggestion: (question: string) => void;
  userRegion?: string;
}

interface ChecklistItem {
  id: string;
  title: string;
  desc: string;
  required: boolean;
}

const PROCEDURE_DATA: Record<
  string,
  {
    title: string;
    suggestions: string[];
    checklist: ChecklistItem[];
    legalBases: { title: string; doc: string; article: string }[];
  }
> = {
  chuyen_nhuong: {
    title: "Chuyển nhượng Quyền sử dụng đất",
    suggestions: [
      "Thành phần hồ sơ đăng ký sang tên chuyển nhượng đất gồm những giấy tờ gì?",
      "Cách tính Thuế TNCN (2%) và Lệ phí trước bạ (0.5%) khi mua bán đất?",
      "Cơ quan tiếp nhận và thời hạn giải quyết thủ tục đăng ký biến động chuyển nhượng?",
      "Hợp đồng đặt cọc mua bán đất có bắt buộc phải công chứng theo Luật 2024 không?",
    ],
    checklist: [
      {
        id: "cn_gcn",
        title: "Bản gốc Giấy chứng nhận QSDĐ (Sổ đỏ/Sổ hồng)",
        desc: "Bắt buộc nộp bản gốc để cơ quan đăng ký xác nhận biến động",
        required: true,
      },
      {
        id: "cn_hd",
        title: "Hợp đồng chuyển nhượng quyền sử dụng đất",
        desc: "Đã được công chứng tại Văn phòng công chứng hoặc chứng thực",
        required: true,
      },
      {
        id: "cn_cccd",
        title: "Căn cước công dân / Định danh VNeID của bên bán và mua",
        desc: "Bản sao hoặc thông tin từ cơ sở dữ liệu quốc gia về dân cư",
        required: true,
      },
      {
        id: "cn_honnhan",
        title: "Giấy đăng ký kết hôn / Giấy xác nhận độc thân",
        desc: "Chứng minh tài sản chung hoặc tài sản riêng của bên chuyển nhượng",
        required: true,
      },
      {
        id: "cn_tk_thue",
        title: "Tờ khai Thuế TNCN (Mẫu 03/BĐS-TNCN)",
        desc: "Do bên chuyển nhượng kê khai hoặc bên nhận nộp thay theo thỏa thuận",
        required: true,
      },
      {
        id: "cn_tk_lptb",
        title: "Tờ khai Lệ phí trước bạ nhà đất (Mẫu 01/LPTB)",
        desc: "Kê khai tính lệ phí trước bạ của bên nhận chuyển nhượng",
        required: true,
      },
    ],
    legalBases: [
      { title: "Luật Đất đai 2024", doc: "Luật số 31/2024/QH15", article: "Điều 133 & 157" },
      { title: "Nghị định 101/2024/NĐ-CP", doc: "Quy định về điều tra cơ bản, đăng ký, cấp GCN", article: "Điều 37 & Điều 38" },
      { title: "Nghị định 102/2024/NĐ-CP", doc: "Quy định chi tiết thi hành một số điều Luật Đất đai", article: "Chương VI" },
    ],
  },
  cap_doi: {
    title: "Cấp đổi, cấp lại Giấy chứng nhận",
    suggestions: [
      "Trường hợp nào được cấp đổi Giấy chứng nhận sang mẫu phôi mới theo Luật 2024?",
      "Hồ sơ và thủ tục cấp lại Giấy chứng nhận khi bị mất bao gồm những gì?",
      "Thời hạn giải quyết thủ tục cấp đổi Sổ đỏ là bao nhiêu ngày làm việc?",
      "Mức lệ phí cấp đổi Giấy chứng nhận quyền sử dụng đất hiện nay?",
    ],
    checklist: [
      {
        id: "cd_don",
        title: "Đơn đề nghị cấp đổi/cấp lại Giấy chứng nhận (Mẫu 10/ĐK)",
        desc: "Theo quy định tại Nghị định 101/2024/NĐ-CP",
        required: true,
      },
      {
        id: "cd_gcn_goc",
        title: "Bản gốc Giấy chứng nhận đã cấp (đối với trường hợp cấp đổi)",
        desc: "Nộp lại sổ cũ bị rách nát, ố mờ hoặc có nhu cầu đổi sang mẫu mới",
        required: true,
      },
      {
        id: "cd_mat_so",
        title: "Giấy xác nhận của UBND cấp xã về việc mất sổ (nếu bị mất)",
        desc: "Đối với trường hợp xin cấp lại do bị mất Giấy chứng nhận",
        required: false,
      },
      {
        id: "cd_cccd",
        title: "Căn cước công dân người sử dụng đất",
        desc: "Bản sao có công chứng hoặc xuất trình bản chính đối chiếu",
        required: true,
      },
    ],
    legalBases: [
      { title: "Luật Đất đai 2024", doc: "Luật số 31/2024/QH15", article: "Điều 152 & 153" },
      { title: "Nghị định 101/2024/NĐ-CP", doc: "Cấp đổi, cấp lại Giấy chứng nhận", article: "Điều 38, 39" },
    ],
  },
  thua_ke: {
    title: "Thừa kế, Tặng cho Quyền sử dụng đất",
    suggestions: [
      "Thủ tục khai nhận di sản thừa kế quyền sử dụng đất gồm những bước nào?",
      "Trường hợp nào được miễn thuế TNCN và lệ phí trước bạ khi nhận thừa kế đất?",
      "Đất đai chưa có Sổ đỏ có được phân chia thừa kế theo quy định mới không?",
      "Thời hiệu yêu cầu chia di sản thừa kế là bất động sản theo Bộ luật Dân sự?",
    ],
    checklist: [
      {
        id: "tk_gcn",
        title: "Bản gốc Giấy chứng nhận quyền sử dụng đất của người để lại di sản",
        desc: "Xác thực quyền sử dụng đất hợp pháp",
        required: true,
      },
      {
        id: "tk_van_ban",
        title: "Văn bản khai nhận di sản thừa kế / Văn bản thỏa thuận phân chia di sản",
        desc: "Đã công chứng chứng thực theo quy định",
        required: true,
      },
      {
        id: "tk_tu_tuat",
        title: "Trích lục khai tử của người để lại di sản",
        desc: "Chứng minh thời điểm mở thừa kế",
        required: true,
      },
      {
        id: "tk_quan_he",
        title: "Giấy tờ chứng minh quan hệ hàng thừa kế (Giấy khai sinh, Sổ hộ khẩu cũ)",
        desc: "Cơ sở xác định diện và hàng thừa kế hợp pháp",
        required: true,
      },
      {
        id: "tk_mien_thue",
        title: "Giấy tờ xin miễn thuế TNCN và LPTB (giữa cha mẹ, con cái, vợ chồng)",
        desc: "Áp dụng cho đối tượng thuộc diện miễn theo Luật Thuế TNCN",
        required: false,
      },
    ],
    legalBases: [
      { title: "Luật Đất đai 2024", doc: "Quyền thừa kế QSDĐ", article: "Điều 45 & 133" },
      { title: "Bộ luật Dân sự 2015", doc: "Quy định về thừa kế", article: "Chương XXI - Thừa kế" },
      { title: "Nghị định 101/2024/NĐ-CP", doc: "Đăng ký biến động do thừa kế", article: "Điều 37" },
    ],
  },
  all: {
    title: "Tra cứu pháp lý đất đai chung",
    suggestions: [
      "Thời hạn giải quyết các thủ tục hành chính đất đai theo quy định mới là bao lâu?",
      "Nộp hồ sơ đất đai trực tuyến qua Cổng Dịch vụ công quốc gia như thế nào?",
      "Cách kiểm tra quy hoạch và tình trạng pháp lý của thửa đất?",
      "Các khoản thuế, phí và lệ phí bắt buộc khi đăng ký biến động đất đai?",
    ],
    checklist: [
      {
        id: "all_gcn",
        title: "Giấy chứng nhận quyền sử dụng đất (bản gốc/bản sao)",
        desc: "Giấy tờ chứng minh quyền sở hữu hợp pháp",
        required: true,
      },
      {
        id: "all_cccd",
        title: "Căn cước công dân người yêu cầu thủ tục",
        desc: "Định danh công dân theo VNeID",
        required: true,
      },
      {
        id: "all_don",
        title: "Đơn đăng ký theo mẫu của từng thủ tục cụ thể",
        desc: "Điền đầy đủ thông tin thửa đất và chủ sử dụng",
        required: true,
      },
    ],
    legalBases: [
      { title: "Luật Đất đai 2024", doc: "Luật số 31/2024/QH15", article: "Toàn văn có hiệu lực 01/08/2024" },
      { title: "Nghị định 101/2024/NĐ-CP", doc: "Đăng ký, cấp Giấy chứng nhận QSDĐ", article: "Nghị định Chính phủ" },
      { title: "Nghị định 102/2024/NĐ-CP", doc: "Quy định chi tiết thi hành Luật Đất đai", article: "Nghị định Chính phủ" },
    ],
  },
};

export default function ProjectAssistantPanel({
  isOpen,
  onClose,
  selectedProject,
  onSelectSuggestion,
  userRegion = "TP. Hồ Chí Minh",
}: ProjectAssistantPanelProps) {
  const [checkedItems, setCheckedItems] = useState<Record<string, boolean>>({});

  // Determine current procedure data
  const procedureKey = selectedProject?.procedure_type || "all";
  const data = PROCEDURE_DATA[procedureKey] || PROCEDURE_DATA.all;

  // Key for persisting checklist for the current project
  const storageKey = `terra_checklist_${selectedProject ? selectedProject.id : "global"}`;

  // Load checklist progress
  useEffect(() => {
    try {
      const saved = localStorage.getItem(storageKey);
      if (saved) {
        setCheckedItems(JSON.parse(saved));
      } else {
        setCheckedItems({});
      }
    } catch {
      setCheckedItems({});
    }
  }, [storageKey]);

  // Toggle checklist item
  const toggleChecklistItem = (itemId: string) => {
    setCheckedItems((prev) => {
      const updated = { ...prev, [itemId]: !prev[itemId] };
      try {
        localStorage.setItem(storageKey, JSON.stringify(updated));
      } catch (err) {
        console.error(err);
      }
      return updated;
    });
  };

  // Progress stats
  const totalItems = data.checklist.length;
  const completedItems = data.checklist.filter((item) => checkedItems[item.id]).length;
  const progressPercent = totalItems > 0 ? Math.round((completedItems / totalItems) * 100) : 0;

  if (!isOpen) return null;

  return (
    <aside className="project-assistant-panel custom-scrollbar">
      {/* Panel Header */}
      <div className="assistant-header">
        <div className="assistant-header-badge">
          <Sparkles size={16} />
          <span>Gợi ý theo Dự án</span>
        </div>
        {onClose && (
          <button
            type="button"
            className="icon-button close-panel-btn"
            onClick={onClose}
            title="Thu gọn đề xuất"
          >
            <X size={17} />
          </button>
        )}
      </div>

      {/* Project Status Card */}
      <div className="project-context-card">
        <div className="context-card-top">
          <div
            className="context-color-pip"
            style={{ background: selectedProject?.color || "#166b45" }}
          />
          <div className="context-card-headings">
            <h5>{selectedProject ? selectedProject.name : "Dự án / Hồ sơ hiện tại"}</h5>
            <span>{data.title}</span>
          </div>
        </div>

        <div className="context-meta-row">
          <div className="meta-tag">
            <MapPin size={12} />
            <span>{userRegion}</span>
          </div>
          <div className="meta-tag active-status">
            <Clock size={12} />
            <span>Luật Đất đai 2024</span>
          </div>
        </div>
      </div>

      {/* Section 1: Smart Question Suggestions */}
      <div className="assistant-section">
        <div className="assistant-section-head">
          <Sparkles size={15} className="text-emerald" />
          <h4>Câu hỏi đề xuất cho dự án này</h4>
        </div>
        <p className="section-subtext">
          Bấm vào câu hỏi để trợ lý AI giải đáp căn cứ pháp lý & quy trình ngay:
        </p>

        <div className="suggestion-buttons-stack">
          {data.suggestions.map((question, idx) => (
            <button
              key={idx}
              type="button"
              className="project-suggestion-btn"
              onClick={() => onSelectSuggestion(question)}
            >
              <span className="suggestion-text">{question}</span>
              <ArrowUpRight size={14} className="suggestion-arrow" />
            </button>
          ))}
        </div>
      </div>

      {/* Section 2: Interactive Checklist */}
      <div className="assistant-section">
        <div className="assistant-section-head">
          <CheckSquare size={15} className="text-emerald" />
          <h4>Giấy tờ & Hồ sơ cần chuẩn bị</h4>
        </div>

        {/* Progress Bar */}
        <div className="checklist-progress-box">
          <div className="progress-info">
            <span>Tiến độ hoàn tất:</span>
            <strong>
              {completedItems}/{totalItems} ({progressPercent}%)
            </strong>
          </div>
          <div className="progress-bar-track">
            <div
              className="progress-bar-fill"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
        </div>

        <div className="checklist-items">
          {data.checklist.map((item) => {
            const isChecked = !!checkedItems[item.id];
            return (
              <div
                key={item.id}
                className={`checklist-item-row ${isChecked ? "checked" : ""}`}
                onClick={() => toggleChecklistItem(item.id)}
              >
                <div className="checklist-checkbox">
                  {isChecked ? (
                    <CheckCircle2 size={18} className="text-emerald check-anim" />
                  ) : (
                    <Circle size={18} className="text-muted" />
                  )}
                </div>
                <div className="checklist-text">
                  <span className="item-title">
                    {item.title}
                    {item.required && <span className="req-star">*</span>}
                  </span>
                  <small className="item-desc">{item.desc}</small>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Section 3: Legal Bases */}
      <div className="assistant-section">
        <div className="assistant-section-head">
          <FileText size={15} className="text-emerald" />
          <h4>Cơ sở pháp lý đối chiếu</h4>
        </div>

        <div className="legal-bases-list">
          {data.legalBases.map((base, idx) => (
            <div key={idx} className="legal-basis-card">
              <strong>{base.title}</strong>
              <span>{base.doc}</span>
              <small>{base.article}</small>
            </div>
          ))}
        </div>
      </div>

      {/* Footer Notice */}
      <div className="assistant-footer-notice">
        <ShieldCheck size={14} />
        <span>Trích lục đối chiếu tự động từ hệ thống RAG TerraLegalAI</span>
      </div>
    </aside>
  );
}
