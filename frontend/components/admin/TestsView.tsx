import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  evaluationApi,
  type EvaluationCaseResult,
  type EvaluationRun,
  type TestCase,
} from "@/lib/api";
import {
  FileUp,
  Loader2,
  Plus,
  Search,
  TestTube2,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Scale,
  Database,
  ShieldCheck,
  Target,
  FileSearch,
  BookOpen,
  Filter,
  Check,
  X,
  Sparkles,
  Trash2,
  Zap,
  Edit3,
  CheckSquare,
  Square,
} from "lucide-react";

export default function TestsView() {
  // Navigation & Data States
  const [activeTab, setActiveTab] = useState<"evaluate" | "bank">("evaluate");
  const [items, setItems] = useState<TestCase[]>([]);
  const [runs, setRuns] = useState<EvaluationRun[]>([]);
  const [cases, setCases] = useState<EvaluationCaseResult[]>([]);
  const [selectedRun, setSelectedRun] = useState<EvaluationRun | null>(null);
  const [selectedCase, setSelectedCase] = useState<EvaluationCaseResult | null>(null);

  // Filter & Search States
  const [query, setQuery] = useState("");
  const [levelFilter, setLevelFilter] = useState<number | "all">("all");
  const [procFilter, setProcFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<"all" | "pass" | "fail" | "pending">("all");
  const [selectedIds, setSelectedIds] = useState<string[]>([]);

  // Run Controls
  const [runMaxQuestions, setRunMaxQuestions] = useState<number>(20);
  const [runLevel, setRunLevel] = useState<number | "all">("all");
  const [runProcedure, setRunProcedure] = useState<string>("all");
  const [runUseRagas, setRunUseRagas] = useState<boolean>(true);

  // Status & UI States
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [expertNote, setExpertNote] = useState("");

  // Add Modal State
  const [showAdd, setShowAdd] = useState(false);
  const [newQuestion, setNewQuestion] = useState("");
  const [newAnswer, setNewAnswer] = useState("");
  const [newSource, setNewSource] = useState("");
  const [newProcedure, setNewProcedure] = useState("chuyen_nhuong");
  const [newLevel, setNewLevel] = useState<number>(1);

  // Edit Modal State (Expert edit)
  const [editingCase, setEditingCase] = useState<TestCase | null>(null);
  const [editQuestion, setEditQuestion] = useState("");
  const [editAnswer, setEditAnswer] = useState("");
  const [editSource, setEditSource] = useState("");
  const [editProcedure, setEditProcedure] = useState("chuyen_nhuong");
  const [editLevel, setEditLevel] = useState<number>(1);

  const input = useRef<HTMLInputElement>(null);

  // Drag-to-select and range-select states
  const isDragging = useRef(false);
  const dragMode = useRef<"select" | "deselect">("select");
  const lastClickedIndex = useRef<number | null>(null);

  useEffect(() => {
    const handleMouseUp = () => {
      isDragging.current = false;
    };
    window.addEventListener("mouseup", handleMouseUp);
    return () => window.removeEventListener("mouseup", handleMouseUp);
  }, []);

  // Initial Load
  const load = async () => {
    try {
      const [testCases, evaluationRuns] = await Promise.all([
        evaluationApi.getTestCases(),
        evaluationApi.getResults(),
      ]);
      setItems(testCases);
      setRuns(evaluationRuns);

      // Auto select the latest run if available
      if (evaluationRuns && evaluationRuns.length > 0 && !selectedRun) {
        const latest = evaluationRuns[0];
        setSelectedRun(latest);
        const caseRes = await evaluationApi.getResultCases(latest.id);
        setCases(caseRes.items);
      }
    } catch {
      setNotice("Không thể tải danh sách bộ kiểm thử.");
    }
  };

  useEffect(() => {
    load();
  }, []);

  // Filtered Test Cases for Bank Tab
  const filteredBank = useMemo(() => {
    return items.filter((x) => {
      const matchQuery = `${x.question} ${x.expected_answer} ${x.source_doc || ""}`
        .toLowerCase()
        .includes(query.toLowerCase());
      const matchLevel = levelFilter === "all" || Number(x.level) === Number(levelFilter);
      const matchProc = procFilter === "all" || x.procedure_group === procFilter;
      return matchQuery && matchLevel && matchProc;
    });
  }, [items, query, levelFilter, procFilter]);

  // Filtered Cases for Evaluation Tab
  const filteredCases = useMemo(() => {
    return cases.filter((c) => {
      const matchStatus =
        statusFilter === "all" ||
        (statusFilter === "pass" && c.manual_status === "pass") ||
        (statusFilter === "fail" && c.manual_status === "fail") ||
        (statusFilter === "pending" && c.manual_status === "pending");
      const matchQuery = `${c.question} ${c.expected_answer} ${c.actual_answer || ""}`
        .toLowerCase()
        .includes(query.toLowerCase());
      return matchStatus && matchQuery;
    });
  }, [cases, statusFilter, query]);

  // Selection Helpers
  const toggleSelect = (id: string) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const selectAll = () => {
    setSelectedIds(filteredBank.map((x) => x.id));
  };

  const clearSelection = () => {
    setSelectedIds([]);
  };

  const selectFirstN = (n: number) => {
    setSelectedIds(filteredBank.slice(0, n).map((x) => x.id));
  };

  const handleItemMouseDown = (index: number, id: string, e: React.MouseEvent) => {
    const target = e.target as HTMLElement;
    // Don't drag if clicking buttons or links
    if (target.closest("button") || target.closest("a")) return;

    if (e.shiftKey && lastClickedIndex.current !== null) {
      // Shift + Click: Select range
      const start = Math.min(lastClickedIndex.current, index);
      const end = Math.max(lastClickedIndex.current, index);
      const rangeIds = filteredBank.slice(start, end + 1).map((x) => x.id);
      setSelectedIds((prev) => {
        const next = new Set(prev);
        rangeIds.forEach((rid) => next.add(rid));
        return Array.from(next);
      });
      lastClickedIndex.current = index;
      return;
    }

    // Start mouse drag selection
    isDragging.current = true;
    lastClickedIndex.current = index;
    const currentlySelected = selectedIds.includes(id);
    const mode = currentlySelected ? "deselect" : "select";
    dragMode.current = mode;

    setSelectedIds((prev) =>
      mode === "select"
        ? (prev.includes(id) ? prev : [...prev, id])
        : prev.filter((x) => x !== id)
    );
  };

  const handleItemMouseEnter = (id: string) => {
    if (!isDragging.current) return;
    const mode = dragMode.current;
    setSelectedIds((prev) => {
      if (mode === "select") {
        return prev.includes(id) ? prev : [...prev, id];
      } else {
        return prev.filter((x) => x !== id);
      }
    });
  };

  // Actions
  const runEvaluation = async (overrideIds?: string[]) => {
    const idsToRun = overrideIds || (selectedIds.length > 0 ? selectedIds : undefined);
    const count = idsToRun ? idsToRun.length : runMaxQuestions;
    setBusy(true);
    try {
      const out = await evaluationApi.runEvaluation({
        test_case_ids: idsToRun,
        max_questions: count,
        procedure_group: idsToRun ? undefined : (runProcedure === "all" ? undefined : runProcedure),
        level: idsToRun ? undefined : (runLevel === "all" ? undefined : Number(runLevel)),
        use_ragas: runUseRagas,
        notes: idsToRun
          ? `Đánh giá ${idsToRun.length} câu đã chọn (${runUseRagas ? "RAGAS" : "Heuristic"})`
          : `Đánh giá ${runUseRagas ? "RAGAS" : "Heuristic"} (${count} câu)`,
      });
      setNotice(
        `Đã khởi chạy đánh giá ${out.total_questions || count} câu. Hệ thống đang xử lý...`
      );
      setActiveTab("evaluate");
      setTimeout(async () => {
        const updatedRuns = await evaluationApi.getResults();
        setRuns(updatedRuns);
        if (updatedRuns.length > 0) {
          openRun(updatedRuns[0]);
        }
        setBusy(false);
      }, 2500);
    } catch {
      setNotice("Khởi chạy đánh giá thất bại. Vui lòng kiểm tra lại dịch vụ.");
      setBusy(false);
    }
  };

  const openRun = async (run: EvaluationRun) => {
    setBusy(true);
    try {
      const result = await evaluationApi.getResultCases(run.id);
      setSelectedRun(run);
      setCases(result.items);
      setSelectedCase(null);
    } finally {
      setBusy(false);
    }
  };

  const openReviewModal = (item: EvaluationCaseResult) => {
    setSelectedCase(item);
    setExpertNote(item.manual_note || "");
  };

  const reviewCase = async (status: "pass" | "fail") => {
    if (!selectedCase || !selectedRun) return;
    setBusy(true);
    try {
      await evaluationApi.reviewResultCase(selectedCase.id, status, expertNote);
      const result = await evaluationApi.getResultCases(selectedRun.id);
      setCases(result.items);
      const updated = result.items.find((x) => x.id === selectedCase.id) || null;
      setSelectedCase(updated);
      setNotice(`Đã cập nhật đánh giá của chuyên gia: ${status === "pass" ? "ĐẠT" : "KHÔNG ĐẠT"}`);
    } finally {
      setBusy(false);
    }
  };

  const importCsv = async (file?: File) => {
    if (!file) return;
    setBusy(true);
    try {
      const out = await evaluationApi.importTestCases(file);
      setNotice(
        `Đã nhập thành công ${out.created} câu hỏi${
          out.errors.length ? ` (${out.errors.length} dòng lỗi)` : ""
        }.`
      );
      await load();
    } finally {
      setBusy(false);
      if (input.current) input.current.value = "";
    }
  };

  const addTestCase = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    try {
      await evaluationApi.createTestCase({
        question: newQuestion,
        expected_answer: newAnswer,
        source_doc: newSource,
        procedure_group: newProcedure,
        level: newLevel,
      });
      setNewQuestion("");
      setNewAnswer("");
      setNewSource("");
      setShowAdd(false);
      setNotice("Đã thêm test case mới vào bộ kiểm thử.");
      await load();
    } finally {
      setBusy(false);
    }
  };

  const openEditModal = (tc: TestCase, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    setEditingCase(tc);
    setEditQuestion(tc.question);
    setEditAnswer(tc.expected_answer);
    setEditSource(tc.source_doc || "");
    setEditProcedure(tc.procedure_group || "chuyen_nhuong");
    setEditLevel(Number(tc.level) || 1);
  };

  const saveEditTestCase = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!editingCase) return;
    setBusy(true);
    try {
      await evaluationApi.updateTestCase(editingCase.id, {
        question: editQuestion,
        expected_answer: editAnswer,
        source_doc: editSource,
        procedure_group: editProcedure,
        level: editLevel,
      });
      setNotice(`Đã cập nhật câu hỏi TC-${editingCase.id.slice(0, 6)} thành công.`);
      setEditingCase(null);
      await load();
    } catch {
      setNotice("Cập nhật câu hỏi thất bại. Vui lòng kiểm tra lại quyền admin.");
    } finally {
      setBusy(false);
    }
  };

  const clearAll = async () => {
    if (
      !window.confirm(
        "Bạn có chắc chắn muốn XÓA TOÀN BỘ câu hỏi và các lần chạy đánh giá cũ? Thao tác này sẽ làm sạch bộ kiểm thử để bạn nạp lại số lượng ít hơn."
      )
    )
      return;
    setBusy(true);
    try {
      await evaluationApi.clearAllTestCases();
      setSelectedIds([]);
      setNotice("Đã xóa sạch bộ câu hỏi và các lần chạy cũ. Bây giờ bạn có thể nạp hoặc test mẻ mới.");
      setSelectedRun(null);
      setCases([]);
      await load();
    } catch {
      setNotice("Xóa thất bại. Vui lòng kiểm tra lại quyền admin.");
    } finally {
      setBusy(false);
    }
  };

  const deleteSingleCase = async (id: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    if (!window.confirm("Bạn có chắc chắn muốn xóa câu hỏi này khỏi bộ kiểm thử?")) return;
    setBusy(true);
    try {
      await evaluationApi.deleteTestCase(id);
      setSelectedIds((prev) => prev.filter((x) => x !== id));
      setNotice("Đã xóa câu hỏi khỏi bộ kiểm thử.");
      await load();
    } catch {
      setNotice("Xóa câu hỏi thất bại.");
    } finally {
      setBusy(false);
    }
  };

  const deleteSelectedCases = async () => {
    if (selectedIds.length === 0) return;
    if (
      !window.confirm(
        `Bạn có chắc chắn muốn XÓA ${selectedIds.length} câu hỏi đã chọn? Thao tác này không thể hoàn tác.`
      )
    ) {
      return;
    }
    setBusy(true);
    try {
      const res = await evaluationApi.bulkDeleteTestCases(selectedIds);
      setNotice(`Đã xóa thành công ${res.deleted} câu hỏi khỏi bộ kiểm thử.`);
      setSelectedIds([]);
      await load();
    } catch {
      setNotice("Xóa các câu hỏi đã chọn thất bại. Vui lòng thử lại.");
    } finally {
      setBusy(false);
    }
  };

  // Helper Labels & Badges
  const getLevelBadge = (lvl?: number) => {
    switch (Number(lvl)) {
      case 1:
        return (
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 4,
              padding: "2px 8px",
              borderRadius: 12,
              fontSize: 11,
              fontWeight: 700,
              background: "#e8f5ed",
              color: "#166b45",
              border: "1px solid #b7e8ce",
            }}
          >
            Level 1: Cơ bản
          </span>
        );
      case 2:
        return (
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 4,
              padding: "2px 8px",
              borderRadius: 12,
              fontSize: 11,
              fontWeight: 700,
              background: "#fffbeb",
              color: "#b45309",
              border: "1px solid #fde68a",
            }}
          >
            Level 2: Đời thường
          </span>
        );
      case 3:
      default:
        return (
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 4,
              padding: "2px 8px",
              borderRadius: 12,
              fontSize: 11,
              fontWeight: 700,
              background: "#fef2f2",
              color: "#dc2626",
              border: "1px solid #fecaca",
            }}
          >
            Level 3: Bẫy / Khó
          </span>
        );
    }
  };

  const getProcedureLabel = (code?: string) => {
    const map: Record<string, string> = {
      chuyen_nhuong: "Chuyển nhượng",
      tang_cho: "Tặng cho",
      bien_dong: "ĐK Biến động",
      cap_doi_cap_lai: "Cấp đổi / Cấp lại",
      cap_doi: "Cấp đổi",
      tach_hop_thua: "Tách / Hợp thửa",
      trinh_tu_thu_tuc: "Trình tự thủ tục",
      thanh_phan_ho_so: "Thành phần hồ sơ",
      bieu_mau: "Biểu mẫu",
      da_y: "Đa ý (Multi-hop)",
      cau_hoi_kho: "Câu hỏi bẫy / Khó",
    };
    return map[code || ""] || code || "Chung";
  };

  return (
    <>
      {/* Page Header */}
      <div className="page-heading">
        <div>
          <span className="eyebrow">Trung tâm Kiểm định Chất lượng AI & Thẩm định Pháp lý</span>
          <h1>Bộ kiểm thử RAGAS & Chuyên gia</h1>
          <p>
            Đo lường tự động 4 chỉ số RAGAS chuẩn mực (Faithfulness, Relevancy, Precision, Recall)
            kết hợp quy trình Chuyên gia pháp lý phê duyệt (Human-in-the-loop).
          </p>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          {items.length > 0 && (
            <button
              className="secondary-button"
              onClick={clearAll}
              disabled={busy}
              style={{
                color: "#dc2626",
                borderColor: "#fecaca",
                background: "#fff",
              }}
              title="Xóa toàn bộ câu hỏi và kết quả để nạp mẻ mới"
            >
              <Trash2 size={16} /> Xóa tất cả ({items.length})
            </button>
          )}
          <button className="secondary-button" onClick={() => input.current?.click()}>
            <FileUp size={16} /> Nhập CSV
          </button>
          <button className="primary-button fit" onClick={() => setShowAdd(true)}>
            <Plus size={17} /> Thêm câu hỏi
          </button>
          <input
            ref={input}
            hidden
            type="file"
            accept=".csv"
            onChange={(e) => importCsv(e.target.files?.[0])}
          />
        </div>
      </div>

      {notice && (
        <div
          style={{
            background: "#e8f5ed",
            border: "1px solid #b7e8ce",
            color: "#0f766e",
            padding: "10px 16px",
            borderRadius: 8,
            marginBottom: 16,
            display: "flex",
            alignItems: "center",
            gap: 8,
            fontSize: 13.5,
          }}
        >
          <Sparkles size={16} />
          {notice}
        </div>
      )}

      {/* Modern Tabs Bar */}
      <div
        style={{
          display: "flex",
          gap: 12,
          borderBottom: "1px solid #dfe5e1",
          marginBottom: 20,
        }}
      >
        <button
          onClick={() => setActiveTab("evaluate")}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
            padding: "12px 18px",
            fontSize: 14,
            fontWeight: 700,
            border: "none",
            borderBottom: activeTab === "evaluate" ? "3px solid #166b45" : "3px solid transparent",
            color: activeTab === "evaluate" ? "#166b45" : "#5e6d64",
            background: "none",
            cursor: "pointer",
          }}
        >
          <TestTube2 size={18} />
          🧪 Chấm điểm RAGAS & Duyệt chuyên gia
          {runs.length > 0 && (
            <span
              style={{
                fontSize: 11,
                padding: "2px 7px",
                borderRadius: 10,
                background: activeTab === "evaluate" ? "#166b45" : "#dfe5e1",
                color: activeTab === "evaluate" ? "#fff" : "#5e6d64",
              }}
            >
              {runs.length} lần chạy
            </span>
          )}
        </button>

        <button
          onClick={() => setActiveTab("bank")}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
            padding: "12px 18px",
            fontSize: 14,
            fontWeight: 700,
            border: "none",
            borderBottom: activeTab === "bank" ? "3px solid #166b45" : "3px solid transparent",
            color: activeTab === "bank" ? "#166b45" : "#5e6d64",
            background: "none",
            cursor: "pointer",
          }}
        >
          <Database size={18} />
          📋 Ngân hàng Test Cases
          <span
            style={{
              fontSize: 11,
              padding: "2px 7px",
              borderRadius: 10,
              background: activeTab === "bank" ? "#166b45" : "#dfe5e1",
              color: activeTab === "bank" ? "#fff" : "#5e6d64",
            }}
          >
            {items.length} câu
          </span>
        </button>
      </div>

      {/* ========================================================================= */}
      {/* TAB 1: EVALUATION & EXPERT AUDIT WORKBENCH                                */}
      {/* ========================================================================= */}
      {activeTab === "evaluate" && (
        <>
          {/* Run Control Panel */}
          <section
            className="panel"
            style={{
              marginBottom: 20,
              padding: 20,
              borderRadius: 12,
              border: "1px solid #dfe5e1",
              background: "#fff",
            }}
          >
            {selectedIds.length > 0 && (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  background: "#eff6ff",
                  border: "1px solid #bfdbfe",
                  color: "#1e40af",
                  padding: "10px 16px",
                  borderRadius: 8,
                  marginBottom: 16,
                  fontSize: 13,
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <Zap size={16} color="#2563eb" />
                  <span>
                    <strong>Chế độ chọn lọc tiết kiệm Token:</strong> Đang chọn{" "}
                    <strong>{selectedIds.length}</strong> câu hỏi từ ngân hàng để kiểm thử.
                  </span>
                </div>
                <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
                  <button
                    type="button"
                    onClick={clearSelection}
                    style={{
                      background: "none",
                      border: "none",
                      color: "#dc2626",
                      cursor: "pointer",
                      fontSize: 12.5,
                      fontWeight: 600,
                      padding: 0,
                    }}
                  >
                    Bỏ chọn
                  </button>
                  <button
                    type="button"
                    onClick={() => setActiveTab("bank")}
                    style={{
                      background: "#2563eb",
                      color: "#fff",
                      border: "none",
                      borderRadius: 6,
                      cursor: "pointer",
                      fontSize: 12,
                      fontWeight: 600,
                      padding: "4px 10px",
                    }}
                  >
                    Quản lý danh sách đã chọn →
                  </button>
                </div>
              </div>
            )}

            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                flexWrap: "wrap",
                gap: 16,
              }}
            >
              <div>
                <h2 style={{ margin: 0, fontSize: 16, fontWeight: 700 }}>
                  🚀 Khởi chạy đợt kiểm thử mới
                </h2>
                <p style={{ margin: "4px 0 0", fontSize: 13, color: "#64748b" }}>
                  Đưa các câu hỏi qua RAG pipeline và kích hoạt RAGAS LLM-Judge tự động chấm điểm.
                </p>
              </div>

              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 12,
                  flexWrap: "wrap",
                }}
              >
                {/* Max questions selector (hidden or disabled if selectedIds > 0) */}
                {selectedIds.length === 0 ? (
                  <>
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <label style={{ fontSize: 12, color: "#475569", fontWeight: 600 }}>
                        Số câu:
                      </label>
                      <select
                        value={runMaxQuestions}
                        onChange={(e) => setRunMaxQuestions(Number(e.target.value))}
                        style={{
                          padding: "6px 10px",
                          borderRadius: 6,
                          border: "1px solid #cbd5e1",
                          fontSize: 13,
                          background: "#fff",
                        }}
                      >
                        <option value={5}>5 câu (Test cực nhanh)</option>
                        <option value={10}>10 câu (Test nhanh)</option>
                        <option value={25}>25 câu (Mẫu chuẩn)</option>
                        <option value={50}>50 câu (Nửa bộ)</option>
                        <option value={items.length || 115}>
                          Toàn bộ ({items.length || 115} câu)
                        </option>
                      </select>
                    </div>

                    {/* Level selector */}
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <label style={{ fontSize: 12, color: "#475569", fontWeight: 600 }}>
                        Độ khó:
                      </label>
                      <select
                        value={runLevel}
                        onChange={(e) =>
                          setRunLevel(e.target.value === "all" ? "all" : Number(e.target.value))
                        }
                        style={{
                          padding: "6px 10px",
                          borderRadius: 6,
                          border: "1px solid #cbd5e1",
                          fontSize: 13,
                          background: "#fff",
                        }}
                      >
                        <option value="all">Tất cả mức độ</option>
                        <option value={1}>Level 1: Cơ bản</option>
                        <option value={2}>Level 2: Đời thường</option>
                        <option value={3}>Level 3: Bẫy / Khó</option>
                      </select>
                    </div>

                    {/* Procedure Selector */}
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <label style={{ fontSize: 12, color: "#475569", fontWeight: 600 }}>
                        Thủ tục:
                      </label>
                      <select
                        value={runProcedure}
                        onChange={(e) => setRunProcedure(e.target.value)}
                        style={{
                          padding: "6px 10px",
                          borderRadius: 6,
                          border: "1px solid #cbd5e1",
                          fontSize: 13,
                          background: "#fff",
                        }}
                      >
                        <option value="all">Tất cả nhóm</option>
                        <option value="chuyen_nhuong">Chuyển nhượng</option>
                        <option value="tang_cho">Tặng cho</option>
                        <option value="bien_dong">ĐK Biến động</option>
                        <option value="tach_hop_thua">Tách / Hợp thửa</option>
                        <option value="cap_doi_cap_lai">Cấp đổi / Cấp lại</option>
                        <option value="cau_hoi_kho">Câu hỏi khó / Bẫy</option>
                      </select>
                    </div>
                  </>
                ) : (
                  <span
                    style={{
                      background: "#f0fdf4",
                      border: "1px solid #bbf7d0",
                      color: "#15803d",
                      padding: "5px 12px",
                      borderRadius: 6,
                      fontSize: 12.5,
                      fontWeight: 600,
                    }}
                  >
                    Đang chọn {selectedIds.length} câu tùy chỉnh
                  </span>
                )}

                {/* Toggle RAGAS */}
                <label
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    fontSize: 12,
                    fontWeight: 600,
                    cursor: "pointer",
                    color: runUseRagas ? "#166b45" : "#64748b",
                  }}
                >
                  <input
                    type="checkbox"
                    checked={runUseRagas}
                    onChange={(e) => setRunUseRagas(e.target.checked)}
                  />
                  Bật RAGAS LLM-Judge
                </label>

                <button
                  className="primary-button"
                  disabled={!items.length || busy}
                  onClick={() => runEvaluation()}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    padding: "8px 16px",
                    fontWeight: 700,
                  }}
                >
                  {busy ? (
                    <>
                      <Loader2 className="spinner" size={16} /> Đang chạy...
                    </>
                  ) : (
                    <>
                      <TestTube2 size={16} />{" "}
                      {selectedIds.length > 0
                        ? `Đánh giá ${selectedIds.length} câu đã chọn`
                        : "Bắt đầu đánh giá"}
                    </>
                  )}
                </button>
              </div>
            </div>
          </section>

          {/* RAGAS 4-METRIC DASHBOARD CARDS */}
          {selectedRun ? (
            <div style={{ marginBottom: 24 }}>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  marginBottom: 12,
                }}
              >
                <div>
                  <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700 }}>
                    📊 Kết quả đợt chạy:{" "}
                    {new Date(selectedRun.run_date).toLocaleDateString("vi-VN")}{" "}
                    <span style={{ fontSize: 13, color: "#64748b", fontWeight: 400 }}>
                      ({selectedRun.total_questions || 0} câu hỏi · Đạt{" "}
                      {selectedRun.passed_questions || 0} câu)
                    </span>
                  </h3>
                  <span style={{ fontSize: 12, color: "#64748b" }}>
                    Phương pháp chấm:{" "}
                    <strong style={{ color: "#166b45" }}>
                      {selectedRun.notes?.includes('evaluation_type": "ragas')
                        ? "RAGAS LLM Judge (Gemini)"
                        : "Heuristic Token Overlap"}
                    </strong>
                  </span>
                </div>

                {/* Run history chip selector */}
                {runs.length > 1 && (
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{ fontSize: 12, color: "#64748b" }}>Chọn lần chạy:</span>
                    <select
                      value={selectedRun.id}
                      onChange={(e) => {
                        const target = runs.find((r) => r.id === e.target.value);
                        if (target) openRun(target);
                      }}
                      style={{
                        padding: "4px 8px",
                        borderRadius: 6,
                        border: "1px solid #cbd5e1",
                        fontSize: 12,
                      }}
                    >
                      {runs.map((r, i) => (
                        <option key={r.id} value={r.id}>
                          Lần #{runs.length - i}: {new Date(r.run_date).toLocaleDateString("vi-VN")}{" "}
                          ({r.total_questions} câu)
                        </option>
                      ))}
                    </select>
                  </div>
                )}
              </div>

              {/* 4 Ragas Core Metric Cards Grid */}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
                  gap: 14,
                }}
              >
                {/* Metric 1: Faithfulness */}
                <div
                  style={{
                    background: "#fff",
                    border: "1px solid #dfe5e1",
                    borderRadius: 10,
                    padding: 16,
                    display: "flex",
                    flexDirection: "column",
                    gap: 8,
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                    }}
                  >
                    <span
                      style={{
                        fontSize: 12,
                        fontWeight: 600,
                        color: "#475569",
                        display: "flex",
                        alignItems: "center",
                        gap: 6,
                      }}
                    >
                      <ShieldCheck size={16} color="#166b45" /> Faithfulness
                    </span>
                    <span
                      style={{
                        fontSize: 10.5,
                        padding: "1px 6px",
                        borderRadius: 8,
                        background:
                          (selectedRun.faithfulness ?? 0) >= 0.8 ? "#e8f5ed" : "#fffbeb",
                        color: (selectedRun.faithfulness ?? 0) >= 0.8 ? "#166b45" : "#b45309",
                        fontWeight: 700,
                      }}
                    >
                      Mục tiêu &ge; 0.85
                    </span>
                  </div>
                  <strong style={{ fontSize: 28, color: "#166b45" }}>
                    {selectedRun.faithfulness !== undefined && selectedRun.faithfulness !== null
                      ? (selectedRun.faithfulness * 100).toFixed(1) + "%"
                      : "—"}
                  </strong>
                  <div
                    style={{
                      height: 6,
                      borderRadius: 3,
                      background: "#e2e8f0",
                      overflow: "hidden",
                    }}
                  >
                    <div
                      style={{
                        width: `${Math.min(100, (selectedRun.faithfulness ?? 0) * 100)}%`,
                        height: "100%",
                        background: "#166b45",
                      }}
                    />
                  </div>
                  <small style={{ fontSize: 11, color: "#64748b" }}>
                    Độ trung thực: Câu trả lời bám sát luật, không bịa đặt.
                  </small>
                </div>

                {/* Metric 2: Answer Relevancy */}
                <div
                  style={{
                    background: "#fff",
                    border: "1px solid #dfe5e1",
                    borderRadius: 10,
                    padding: 16,
                    display: "flex",
                    flexDirection: "column",
                    gap: 8,
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                    }}
                  >
                    <span
                      style={{
                        fontSize: 12,
                        fontWeight: 600,
                        color: "#475569",
                        display: "flex",
                        alignItems: "center",
                        gap: 6,
                      }}
                    >
                      <Target size={16} color="#2563eb" /> Answer Relevancy
                    </span>
                    <span
                      style={{
                        fontSize: 10.5,
                        padding: "1px 6px",
                        borderRadius: 8,
                        background:
                          (selectedRun.answer_relevancy ?? 0) >= 0.75 ? "#eff6ff" : "#fffbeb",
                        color: (selectedRun.answer_relevancy ?? 0) >= 0.75 ? "#2563eb" : "#b45309",
                        fontWeight: 700,
                      }}
                    >
                      Mục tiêu &ge; 0.80
                    </span>
                  </div>
                  <strong style={{ fontSize: 28, color: "#2563eb" }}>
                    {selectedRun.answer_relevancy !== undefined &&
                    selectedRun.answer_relevancy !== null
                      ? (selectedRun.answer_relevancy * 100).toFixed(1) + "%"
                      : "—"}
                  </strong>
                  <div
                    style={{
                      height: 6,
                      borderRadius: 3,
                      background: "#e2e8f0",
                      overflow: "hidden",
                    }}
                  >
                    <div
                      style={{
                        width: `${Math.min(100, (selectedRun.answer_relevancy ?? 0) * 100)}%`,
                        height: "100%",
                        background: "#2563eb",
                      }}
                    />
                  </div>
                  <small style={{ fontSize: 11, color: "#64748b" }}>
                    Đúng trọng tâm: Trả lời trúng vướng mắc người dân hỏi.
                  </small>
                </div>

                {/* Metric 3: Context Precision */}
                <div
                  style={{
                    background: "#fff",
                    border: "1px solid #dfe5e1",
                    borderRadius: 10,
                    padding: 16,
                    display: "flex",
                    flexDirection: "column",
                    gap: 8,
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                    }}
                  >
                    <span
                      style={{
                        fontSize: 12,
                        fontWeight: 600,
                        color: "#475569",
                        display: "flex",
                        alignItems: "center",
                        gap: 6,
                      }}
                    >
                      <FileSearch size={16} color="#7c3aed" /> Context Precision
                    </span>
                    <span
                      style={{
                        fontSize: 10.5,
                        padding: "1px 6px",
                        borderRadius: 8,
                        background:
                          (selectedRun.context_precision ?? 0) >= 0.7 ? "#f5f3ff" : "#fffbeb",
                        color:
                          (selectedRun.context_precision ?? 0) >= 0.7 ? "#7c3aed" : "#b45309",
                        fontWeight: 700,
                      }}
                    >
                      Mục tiêu &ge; 0.75
                    </span>
                  </div>
                  <strong style={{ fontSize: 28, color: "#7c3aed" }}>
                    {selectedRun.context_precision !== undefined &&
                    selectedRun.context_precision !== null
                      ? (selectedRun.context_precision * 100).toFixed(1) + "%"
                      : "—"}
                  </strong>
                  <div
                    style={{
                      height: 6,
                      borderRadius: 3,
                      background: "#e2e8f0",
                      overflow: "hidden",
                    }}
                  >
                    <div
                      style={{
                        width: `${Math.min(100, (selectedRun.context_precision ?? 0) * 100)}%`,
                        height: "100%",
                        background: "#7c3aed",
                      }}
                    />
                  </div>
                  <small style={{ fontSize: 11, color: "#64748b" }}>
                    Độ chính xác truy xuất: Các đoạn chunk chứa đúng căn cứ luật.
                  </small>
                </div>

                {/* Metric 4: Context Recall */}
                <div
                  style={{
                    background: "#fff",
                    border: "1px solid #dfe5e1",
                    borderRadius: 10,
                    padding: 16,
                    display: "flex",
                    flexDirection: "column",
                    gap: 8,
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                    }}
                  >
                    <span
                      style={{
                        fontSize: 12,
                        fontWeight: 600,
                        color: "#475569",
                        display: "flex",
                        alignItems: "center",
                        gap: 6,
                      }}
                    >
                      <BookOpen size={16} color="#0891b2" /> Context Recall
                    </span>
                    <span
                      style={{
                        fontSize: 10.5,
                        padding: "1px 6px",
                        borderRadius: 8,
                        background:
                          (selectedRun.context_recall ?? 0) >= 0.75 ? "#ecfeff" : "#fffbeb",
                        color: (selectedRun.context_recall ?? 0) >= 0.75 ? "#0891b2" : "#b45309",
                        fontWeight: 700,
                      }}
                    >
                      Mục tiêu &ge; 0.80
                    </span>
                  </div>
                  <strong style={{ fontSize: 28, color: "#0891b2" }}>
                    {selectedRun.context_recall !== undefined &&
                    selectedRun.context_recall !== null
                      ? (selectedRun.context_recall * 100).toFixed(1) + "%"
                      : "—"}
                  </strong>
                  <div
                    style={{
                      height: 6,
                      borderRadius: 3,
                      background: "#e2e8f0",
                      overflow: "hidden",
                    }}
                  >
                    <div
                      style={{
                        width: `${Math.min(100, (selectedRun.context_recall ?? 0) * 100)}%`,
                        height: "100%",
                        background: "#0891b2",
                      }}
                    />
                  </div>
                  <small style={{ fontSize: 11, color: "#64748b" }}>
                    Độ bao phủ: Tài liệu tìm được bao quát đủ ý so với đáp án chuẩn.
                  </small>
                </div>
              </div>
            </div>
          ) : (
            <div
              style={{
                padding: "36px 20px",
                textAlign: "center",
                background: "#fff",
                borderRadius: 12,
                border: "1px dashed #cbd5e1",
                marginBottom: 24,
              }}
            >
              <TestTube2 size={36} color="#94a3b8" style={{ margin: "0 auto 12px" }} />
              <h3 style={{ margin: "0 0 6px", fontSize: 16 }}>Chưa có kết quả đánh giá</h3>
              <p style={{ color: "#64748b", fontSize: 13, margin: 0 }}>
                Hãy cấu hình số câu hỏi ở trên và bấm <strong>"Bắt đầu đánh giá"</strong> để AI thực
                hiện kiểm thử.
              </p>
            </div>
          )}

          {/* Expert Audit Workbench (Danh sách câu đã chấm) */}
          {selectedRun && (
            <section
              className="panel"
              style={{
                borderRadius: 12,
                border: "1px solid #dfe5e1",
                background: "#fff",
                padding: 20,
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  flexWrap: "wrap",
                  gap: 12,
                  marginBottom: 16,
                }}
              >
                <div>
                  <h2 style={{ margin: 0, fontSize: 16, fontWeight: 700 }}>
                    ⚖️ Bàn làm việc của Chuyên gia Pháp lý
                  </h2>
                  <p style={{ margin: "4px 0 0", fontSize: 13, color: "#64748b" }}>
                    Rà soát câu trả lời thực tế của AI đối chiếu với đáp án chuẩn và xác nhận Đạt /
                    Không đạt.
                  </p>
                </div>

                {/* Filter by status */}
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ fontSize: 12, color: "#64748b" }}>Lọc trạng thái:</span>
                  <div
                    style={{
                      display: "flex",
                      background: "#f1f5f9",
                      padding: 3,
                      borderRadius: 8,
                    }}
                  >
                    <button
                      onClick={() => setStatusFilter("all")}
                      style={{
                        padding: "4px 10px",
                        fontSize: 12,
                        borderRadius: 6,
                        border: "none",
                        background: statusFilter === "all" ? "#fff" : "transparent",
                        fontWeight: statusFilter === "all" ? 700 : 500,
                        cursor: "pointer",
                      }}
                    >
                      Tất cả ({cases.length})
                    </button>
                    <button
                      onClick={() => setStatusFilter("pass")}
                      style={{
                        padding: "4px 10px",
                        fontSize: 12,
                        borderRadius: 6,
                        border: "none",
                        background: statusFilter === "pass" ? "#fff" : "transparent",
                        color: "#166b45",
                        fontWeight: statusFilter === "pass" ? 700 : 500,
                        cursor: "pointer",
                      }}
                    >
                      🟢 Đạt ({cases.filter((c) => c.manual_status === "pass").length})
                    </button>
                    <button
                      onClick={() => setStatusFilter("pending")}
                      style={{
                        padding: "4px 10px",
                        fontSize: 12,
                        borderRadius: 6,
                        border: "none",
                        background: statusFilter === "pending" ? "#fff" : "transparent",
                        color: "#b45309",
                        fontWeight: statusFilter === "pending" ? 700 : 500,
                        cursor: "pointer",
                      }}
                    >
                      🟠 Chờ duyệt ({cases.filter((c) => c.manual_status === "pending").length})
                    </button>
                    <button
                      onClick={() => setStatusFilter("fail")}
                      style={{
                        padding: "4px 10px",
                        fontSize: 12,
                        borderRadius: 6,
                        border: "none",
                        background: statusFilter === "fail" ? "#fff" : "transparent",
                        color: "#dc2626",
                        fontWeight: statusFilter === "fail" ? 700 : 500,
                        cursor: "pointer",
                      }}
                    >
                      🔴 Không đạt ({cases.filter((c) => c.manual_status === "fail").length})
                    </button>
                  </div>
                </div>
              </div>

              {/* Cases Table List */}
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {filteredCases.map((item, idx) => (
                  <div
                    key={item.id}
                    style={{
                      display: "grid",
                      gridTemplateColumns: "110px 1fr 180px 140px",
                      alignItems: "center",
                      gap: 16,
                      padding: "14px 16px",
                      borderRadius: 8,
                      border: "1px solid #f1f5f9",
                      background: idx % 2 === 0 ? "#f8faf8" : "#fff",
                    }}
                  >
                    {/* Status badge */}
                    <div>
                      {item.manual_status === "pass" ? (
                        <span
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: 4,
                            padding: "3px 8px",
                            borderRadius: 12,
                            fontSize: 11.5,
                            fontWeight: 700,
                            background: "#e8f5ed",
                            color: "#166b45",
                            border: "1px solid #b7e8ce",
                          }}
                        >
                          <CheckCircle2 size={13} /> ĐẠT
                        </span>
                      ) : item.manual_status === "fail" ? (
                        <span
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: 4,
                            padding: "3px 8px",
                            borderRadius: 12,
                            fontSize: 11.5,
                            fontWeight: 700,
                            background: "#fef2f2",
                            color: "#dc2626",
                            border: "1px solid #fecaca",
                          }}
                        >
                          <XCircle size={13} /> KHÔNG ĐẠT
                        </span>
                      ) : (
                        <span
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: 4,
                            padding: "3px 8px",
                            borderRadius: 12,
                            fontSize: 11.5,
                            fontWeight: 700,
                            background: "#fffbeb",
                            color: "#b45309",
                            border: "1px solid #fde68a",
                          }}
                        >
                          <AlertCircle size={13} /> Chờ duyệt
                        </span>
                      )}
                    </div>

                    {/* Question & actual answer snippet */}
                    <div>
                      <strong style={{ fontSize: 13.5, color: "#1e293b", display: "block" }}>
                        {item.question}
                      </strong>
                      <p
                        style={{
                          margin: "4px 0 0",
                          fontSize: 12,
                          color: "#64748b",
                          display: "-webkit-box",
                          WebkitLineClamp: 2,
                          WebkitBoxOrient: "vertical",
                          overflow: "hidden",
                        }}
                      >
                        <strong>AI:</strong> {item.actual_answer || "Không có câu trả lời"}
                      </p>
                      {item.manual_note && (
                        <span style={{ fontSize: 11, color: "#166b45", fontStyle: "italic" }}>
                          💬 Ghi chú chuyên gia: {item.manual_note}
                        </span>
                      )}
                    </div>

                    {/* Scores */}
                    <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          fontSize: 11,
                          color: "#64748b",
                        }}
                      >
                        <span>Tương đồng:</span>
                        <strong style={{ color: "#1e293b" }}>
                          {item.answer_similarity !== undefined
                            ? (item.answer_similarity * 100).toFixed(0) + "%"
                            : "—"}
                        </strong>
                      </div>
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          fontSize: 11,
                          color: "#64748b",
                        }}
                      >
                        <span>Bám nguồn:</span>
                        <strong style={{ color: "#166b45" }}>
                          {item.grounding_score !== undefined
                            ? (item.grounding_score * 100).toFixed(0) + "%"
                            : "—"}
                        </strong>
                      </div>
                    </div>

                    {/* Action */}
                    <button
                      className="secondary-button"
                      onClick={() => openReviewModal(item)}
                      style={{
                        padding: "6px 12px",
                        fontSize: 12,
                        fontWeight: 600,
                        justifyContent: "center",
                      }}
                    >
                      <Scale size={14} /> Thẩm định
                    </button>
                  </div>
                ))}
              </div>
            </section>
          )}
        </>
      )}

      {/* ========================================================================= */}
      {/* TAB 2: TEST CASES BANK (115 CÂU HỎI ĐẦU VÀO)                              */}
      {/* ========================================================================= */}
      {activeTab === "bank" && (
        <section
          className="panel"
          style={{
            borderRadius: 12,
            border: "1px solid #dfe5e1",
            background: "#fff",
            padding: 20,
          }}
        >
          {/* Filters Bar */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              flexWrap: "wrap",
              gap: 12,
              marginBottom: 18,
            }}
          >
            <div className="sidebar-search" style={{ minWidth: 280 }}>
              <Search size={16} />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Tìm câu hỏi, từ khóa, căn cứ luật..."
              />
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
              {/* Level Filter */}
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <Filter size={14} color="#64748b" />
                <select
                  value={levelFilter}
                  onChange={(e) =>
                    setLevelFilter(e.target.value === "all" ? "all" : Number(e.target.value))
                  }
                  style={{
                    padding: "6px 10px",
                    borderRadius: 6,
                    border: "1px solid #cbd5e1",
                    fontSize: 12.5,
                  }}
                >
                  <option value="all">Tất cả mức độ</option>
                  <option value={1}>Level 1: Cơ bản</option>
                  <option value={2}>Level 2: Đời thường</option>
                  <option value={3}>Level 3: Khó / Bẫy</option>
                </select>
              </div>

              {/* Procedure Filter */}
              <select
                value={procFilter}
                onChange={(e) => setProcFilter(e.target.value)}
                style={{
                  padding: "6px 10px",
                  borderRadius: 6,
                  border: "1px solid #cbd5e1",
                  fontSize: 12.5,
                }}
              >
                <option value="all">Tất cả nhóm thủ tục</option>
                <option value="chuyen_nhuong">Chuyển nhượng</option>
                <option value="tang_cho">Tặng cho</option>
                <option value="bien_dong">Đăng ký biến động</option>
                <option value="tach_hop_thua">Tách / Hợp thửa</option>
                <option value="cap_doi_cap_lai">Cấp đổi / Cấp lại</option>
                <option value="cau_hoi_kho">Câu hỏi khó / Bẫy</option>
              </select>

              <span style={{ fontSize: 12, color: "#64748b" }}>
                Hiển thị: <strong>{filteredBank.length}</strong> / {items.length} câu
              </span>
            </div>
          </div>

          {/* Quick Selection Guide Banner */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              flexWrap: "wrap",
              gap: 8,
              background: "#f0fdf4",
              border: "1px dashed #86efac",
              borderRadius: 8,
              padding: "8px 14px",
              marginBottom: 12,
              fontSize: 12.5,
              color: "#166534",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <Sparkles size={15} color="#16a34a" />
              <span>
                <strong>Thao tác kéo chọn nhanh:</strong> Nhấp giữ chuột và <strong>kéo lướt</strong> qua các câu hỏi để chọn / bỏ chọn liên tục. Hoặc giữ phím <strong>Shift + Click</strong> để chọn dải nhiều câu.
              </span>
            </div>
            {items.length > 0 && (
              <button
                type="button"
                onClick={clearAll}
                disabled={busy}
                style={{
                  border: "none",
                  background: "transparent",
                  color: "#dc2626",
                  fontSize: 12,
                  fontWeight: 700,
                  cursor: "pointer",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 4,
                  textDecoration: "underline",
                }}
                title="Xóa toàn bộ 115 câu hỏi và kết quả để nạp mẻ mới"
              >
                <Trash2 size={13} /> Xóa toàn bộ ({items.length} câu)
              </button>
            )}
          </div>

          {/* Selection & Batch Action Toolbar */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              flexWrap: "wrap",
              gap: 12,
              background: "#f8fafc",
              border: "1px solid #e2e8f0",
              borderRadius: 8,
              padding: "10px 14px",
              marginBottom: 14,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
              <label
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 8,
                  cursor: "pointer",
                  fontSize: 13,
                  fontWeight: 700,
                  color: "#1e293b",
                }}
              >
                <input
                  type="checkbox"
                  checked={filteredBank.length > 0 && selectedIds.length === filteredBank.length}
                  onChange={(e) => {
                    if (e.target.checked) {
                      selectAll();
                    } else {
                      clearSelection();
                    }
                  }}
                  style={{ width: 17, height: 17, accentColor: "#166b45", cursor: "pointer" }}
                />
                Chọn tất cả ({filteredBank.length} câu)
              </label>

              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                <button
                  type="button"
                  onClick={() => selectFirstN(3)}
                  style={{
                    padding: "4px 10px",
                    borderRadius: 6,
                    border: "1px solid #cbd5e1",
                    background: "#fff",
                    fontSize: 12,
                    cursor: "pointer",
                    fontWeight: 600,
                    color: "#334155",
                  }}
                  title="Chọn nhanh 3 câu đầu để test cực nhanh và siêu tiết kiệm token"
                >
                  ⚡ Chọn 3 câu
                </button>
                <button
                  type="button"
                  onClick={() => selectFirstN(5)}
                  style={{
                    padding: "4px 10px",
                    borderRadius: 6,
                    border: "1px solid #cbd5e1",
                    background: "#fff",
                    fontSize: 12,
                    cursor: "pointer",
                    fontWeight: 600,
                    color: "#334155",
                  }}
                  title="Chọn nhanh 5 câu đầu để test"
                >
                  ⚡ Chọn 5 câu
                </button>
                <button
                  type="button"
                  onClick={() => selectFirstN(10)}
                  style={{
                    padding: "4px 10px",
                    borderRadius: 6,
                    border: "1px solid #cbd5e1",
                    background: "#fff",
                    fontSize: 12,
                    cursor: "pointer",
                    fontWeight: 600,
                    color: "#334155",
                  }}
                  title="Chọn nhanh 10 câu đầu để test"
                >
                  ⚡ Chọn 10 câu
                </button>
                {selectedIds.length > 0 && (
                  <button
                    type="button"
                    onClick={clearSelection}
                    style={{
                      padding: "4px 10px",
                      borderRadius: 6,
                      border: "1px solid #cbd5e1",
                      background: "#fff",
                      fontSize: 12,
                      cursor: "pointer",
                      fontWeight: 600,
                      color: "#64748b",
                    }}
                  >
                    Bỏ chọn ({selectedIds.length})
                  </button>
                )}
              </div>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
              <span style={{ fontSize: 12.5, color: "#475569" }}>
                Đã chọn: <strong style={{ color: "#166b45" }}>{selectedIds.length}</strong> / {filteredBank.length} câu
              </span>

              {selectedIds.length > 0 && (
                <button
                  type="button"
                  onClick={deleteSelectedCases}
                  disabled={busy}
                  style={{
                    padding: "6px 14px",
                    borderRadius: 6,
                    border: "1px solid #fecaca",
                    background: "#fee2e2",
                    color: "#dc2626",
                    fontSize: 12.5,
                    cursor: "pointer",
                    fontWeight: 700,
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 6,
                  }}
                  title="Xóa vĩnh viễn các câu hỏi đang được chọn khỏi bộ kiểm thử"
                >
                  <Trash2 size={14} /> Xóa {selectedIds.length} câu đã chọn
                </button>
              )}

              <button
                type="button"
                className="primary-button"
                disabled={selectedIds.length === 0 || busy}
                onClick={() => runEvaluation(selectedIds)}
                style={{
                  padding: "6px 14px",
                  fontSize: 12.5,
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                  fontWeight: 700,
                  opacity: selectedIds.length === 0 ? 0.5 : 1,
                  cursor: selectedIds.length === 0 ? "not-allowed" : "pointer",
                }}
              >
                <Zap size={14} /> Chạy test {selectedIds.length} câu đã chọn
              </button>

              <button
                type="button"
                onClick={clearAll}
                disabled={busy}
                style={{
                  padding: "6px 12px",
                  borderRadius: 6,
                  border: "1px solid #fecaca",
                  background: "#fff",
                  color: "#dc2626",
                  fontSize: 12,
                  cursor: "pointer",
                  fontWeight: 600,
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 5,
                }}
                title="Xóa toàn bộ câu hỏi trong hệ thống"
              >
                <Trash2 size={13} /> Xóa tất cả ({items.length})
              </button>
            </div>
          </div>

          {/* Test Case Cards List */}
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {filteredBank.map((tc, i) => {
              const isSelected = selectedIds.includes(tc.id);
              return (
                <div
                  key={tc.id}
                  onMouseDown={(e) => handleItemMouseDown(i, tc.id, e)}
                  onMouseEnter={() => handleItemMouseEnter(tc.id)}
                  style={{
                    display: "grid",
                    gridTemplateColumns: "36px 80px 1fr auto",
                    alignItems: "flex-start",
                    gap: 16,
                    padding: "16px",
                    borderRadius: 8,
                    border: isSelected ? "2px solid #166b45" : "1px solid #e2e8f0",
                    background: isSelected ? "#f0fdf4" : "#fff",
                    boxShadow: isSelected ? "0 2px 8px rgba(22, 107, 69, 0.08)" : "none",
                    transition: "border 0.15s ease, background 0.15s ease",
                    cursor: "pointer",
                    userSelect: isDragging.current ? "none" : "auto",
                  }}
                >
                  {/* Checkbox */}
                  <div
                    style={{ paddingTop: 2, display: "flex", justifyContent: "center" }}
                    title={isSelected ? "Bỏ chọn câu này" : "Chọn câu này"}
                  >
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => toggleSelect(tc.id)}
                      onClick={(e) => e.stopPropagation()}
                      style={{
                        width: 19,
                        height: 19,
                        accentColor: "#166b45",
                        cursor: "pointer",
                      }}
                      title="Chọn/bỏ chọn câu hỏi này"
                    />
                  </div>

                  {/* ID & Level Badge */}
                  <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                    <span style={{ fontWeight: 800, fontSize: 13, color: "#166b45" }}>
                      TC-{String(i + 1).padStart(3, "0")}
                    </span>
                    {getLevelBadge(tc.level)}
                  </div>

                  {/* Question & Expected Answer */}
                  <div>
                    <strong style={{ fontSize: 14, color: "#0f172a", display: "block" }}>
                      {tc.question}
                    </strong>
                    <p style={{ margin: "6px 0 4px", fontSize: 12.5, color: "#334155", lineHeight: 1.5 }}>
                      <strong>Đáp án chuẩn:</strong> {tc.expected_answer}
                    </p>
                    <span style={{ fontSize: 11.5, color: "#64748b" }}>
                      📜 Căn cứ: <em>{tc.source_doc || "Chưa gắn nguồn"}</em>
                    </span>
                  </div>

                  {/* Actions & Procedure Badge */}
                  <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 10 }}>
                    <span
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        padding: "4px 10px",
                        borderRadius: 12,
                        fontSize: 11.5,
                        fontWeight: 600,
                        background: isSelected ? "#e2f8e8" : "#f1f5f9",
                        color: "#475569",
                        border: "1px solid #e2e8f0",
                      }}
                    >
                      {getProcedureLabel(tc.procedure_group)}
                    </span>

                    <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                      <button
                        type="button"
                        onClick={(e) => openEditModal(tc, e)}
                        disabled={busy}
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: 4,
                          padding: "4px 8px",
                          borderRadius: 6,
                          border: "1px solid #cbd5e1",
                          background: "#fff",
                          color: "#334155",
                          fontSize: 11.5,
                          fontWeight: 600,
                          cursor: "pointer",
                        }}
                        title="Chuyên gia chỉnh sửa câu hỏi, đáp án chuẩn, căn cứ luật"
                      >
                        <Edit3 size={12} /> Sửa
                      </button>

                      <button
                        type="button"
                        onClick={() => runEvaluation([tc.id])}
                        disabled={busy}
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: 4,
                          padding: "4px 8px",
                          borderRadius: 6,
                          border: "1px solid #b7e8ce",
                          background: "#e8f5ed",
                          color: "#166b45",
                          fontSize: 11.5,
                          fontWeight: 700,
                          cursor: "pointer",
                        }}
                        title="Chạy đánh giá riêng duy nhất câu này để test nhanh nhất"
                      >
                        <Zap size={12} /> Test riêng
                      </button>

                      <button
                        type="button"
                        onClick={(e) => deleteSingleCase(tc.id, e)}
                        disabled={busy}
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          justifyContent: "center",
                          padding: "4px 7px",
                          borderRadius: 6,
                          border: "1px solid #fecaca",
                          background: "#fff",
                          color: "#dc2626",
                          fontSize: 11.5,
                          cursor: "pointer",
                        }}
                        title="Xóa câu hỏi này khỏi bộ kiểm thử"
                      >
                        <Trash2 size={13} />
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* ========================================================================= */}
      {/* MODAL: EXPERT AUDIT & SIDE-BY-SIDE REVIEW (DUYỆT CHUYÊN GIA)              */}
      {/* ========================================================================= */}
      {selectedCase && (
        <div className="modal-backdrop">
          <div
            className="modal-content"
            style={{
              maxWidth: 860,
              width: "100%",
              maxHeight: "92vh",
              overflowY: "auto",
              borderRadius: 12,
            }}
          >
            <div className="modal-header" style={{ background: "#f8faf8" }}>
              <div>
                <h2 style={{ fontSize: 17, fontWeight: 800, color: "#166b45" }}>
                  ⚖️ Thẩm định Chất lượng Pháp lý — {selectedCase.question}
                </h2>
                <span style={{ fontSize: 12, color: "#64748b" }}>
                  Đối chiếu câu trả lời AI với quy định pháp luật và đưa ra phán quyết chuyên môn.
                </span>
              </div>
              <button className="icon-button" onClick={() => setSelectedCase(null)}>
                <X size={18} />
              </button>
            </div>

            <div className="modal-body" style={{ padding: 22, gap: 16 }}>
              {/* Scores bar */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  background: "#f8fafc",
                  border: "1px solid #e2e8f0",
                  padding: "10px 16px",
                  borderRadius: 8,
                }}
              >
                <div style={{ display: "flex", gap: 20 }}>
                  <span style={{ fontSize: 12.5, color: "#475569" }}>
                    Điểm tương đồng từ khóa:{" "}
                    <strong style={{ color: "#166b45" }}>
                      {selectedCase.answer_similarity !== undefined
                        ? (selectedCase.answer_similarity * 100).toFixed(1) + "%"
                        : "—"}
                    </strong>
                  </span>
                  <span style={{ fontSize: 12.5, color: "#475569" }}>
                    Độ bám tài liệu (Grounding):{" "}
                    <strong style={{ color: "#2563eb" }}>
                      {selectedCase.grounding_score !== undefined
                        ? (selectedCase.grounding_score * 100).toFixed(1) + "%"
                        : "—"}
                    </strong>
                  </span>
                </div>
                <div>
                  <span
                    style={{
                      fontSize: 12,
                      fontWeight: 700,
                      padding: "3px 8px",
                      borderRadius: 8,
                      background:
                        selectedCase.manual_status === "pass"
                          ? "#e8f5ed"
                          : selectedCase.manual_status === "fail"
                          ? "#fef2f2"
                          : "#fffbeb",
                      color:
                        selectedCase.manual_status === "pass"
                          ? "#166b45"
                          : selectedCase.manual_status === "fail"
                          ? "#dc2626"
                          : "#b45309",
                    }}
                  >
                    Trạng thái hiện tại:{" "}
                    {selectedCase.manual_status === "pass"
                      ? "ĐÃ ĐẠT"
                      : selectedCase.manual_status === "fail"
                      ? "KHÔNG ĐẠT"
                      : "CHỜ DUYỆT"}
                  </span>
                </div>
              </div>

              {/* Side-by-side comparison */}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr",
                  gap: 16,
                }}
              >
                {/* Left: Ground Truth */}
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: 6,
                    background: "#f0fdf4",
                    border: "1px solid #bbf7d0",
                    padding: 14,
                    borderRadius: 8,
                  }}
                >
                  <span
                    style={{
                      fontSize: 12,
                      fontWeight: 700,
                      color: "#166b45",
                      display: "flex",
                      alignItems: "center",
                      gap: 4,
                    }}
                  >
                    <CheckCircle2 size={14} /> Đáp án chuẩn (Ground Truth)
                  </span>
                  <div
                    style={{
                      fontSize: 13,
                      color: "#0f172a",
                      lineHeight: 1.5,
                      maxHeight: 180,
                      overflowY: "auto",
                    }}
                  >
                    {selectedCase.expected_answer}
                  </div>
                </div>

                {/* Right: AI Actual Answer */}
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: 6,
                    background: "#f8fafc",
                    border: "1px solid #cbd5e1",
                    padding: 14,
                    borderRadius: 8,
                  }}
                >
                  <span
                    style={{
                      fontSize: 12,
                      fontWeight: 700,
                      color: "#2563eb",
                      display: "flex",
                      alignItems: "center",
                      gap: 4,
                    }}
                  >
                    <Sparkles size={14} /> AI trả lời thực tế (RAG Output)
                  </span>
                  <div
                    style={{
                      fontSize: 13,
                      color: "#0f172a",
                      lineHeight: 1.5,
                      maxHeight: 180,
                      overflowY: "auto",
                    }}
                  >
                    {selectedCase.actual_answer || "(Không tạo được câu trả lời)"}
                  </div>
                </div>
              </div>

              {/* Retrieved Contexts / Chunks */}
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                <span
                  style={{
                    fontSize: 12,
                    fontWeight: 700,
                    color: "#475569",
                    display: "flex",
                    alignItems: "center",
                    gap: 4,
                  }}
                >
                  <BookOpen size={14} /> Đoạn trích dẫn luật AI đã dùng (Retrieved Chunks):
                </span>
                <textarea
                  readOnly
                  value={
                    selectedCase.retrieved_contexts?.length
                      ? selectedCase.retrieved_contexts.join("\n\n---\n\n")
                      : "Không trích xuất được chunk nào từ cơ sở dữ liệu."
                  }
                  style={{
                    minHeight: 110,
                    fontSize: 12,
                    color: "#475569",
                    background: "#f8fafc",
                    border: "1px solid #cbd5e1",
                    borderRadius: 6,
                    padding: 10,
                  }}
                />
              </div>

              {/* Expert Review Input Note */}
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                <label style={{ fontSize: 13, fontWeight: 700, color: "#1e293b" }}>
                  ✍️ Nhận xét / Ghi chú của Chuyên gia:
                </label>
                <input
                  value={expertNote}
                  onChange={(e) => setExpertNote(e.target.value)}
                  placeholder="Ví dụ: AI trả lời đủ ý nhưng thiếu viện dẫn Điều 133 Luật Đất đai 2024..."
                  style={{
                    padding: "9px 12px",
                    borderRadius: 6,
                    border: "1px solid #cbd5e1",
                    fontSize: 13,
                  }}
                />
              </div>

              {/* Modal Actions */}
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  borderTop: "1px solid #e2e8f0",
                  paddingTop: 16,
                  marginTop: 6,
                }}
              >
                <button className="secondary-button" onClick={() => setSelectedCase(null)}>
                  Đóng
                </button>

                <div style={{ display: "flex", gap: 10 }}>
                  <button
                    disabled={busy}
                    onClick={() => reviewCase("fail")}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 6,
                      padding: "8px 16px",
                      borderRadius: 6,
                      background: "#fef2f2",
                      color: "#dc2626",
                      border: "1px solid #fecaca",
                      fontWeight: 700,
                      cursor: "pointer",
                    }}
                  >
                    <X size={16} /> Đánh giá: KHÔNG ĐẠT
                  </button>

                  <button
                    disabled={busy}
                    onClick={() => reviewCase("pass")}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 6,
                      padding: "8px 16px",
                      borderRadius: 6,
                      background: "#166b45",
                      color: "#fff",
                      border: "none",
                      fontWeight: 700,
                      cursor: "pointer",
                    }}
                  >
                    <Check size={16} /> Đánh giá: XÁC NHẬN ĐẠT
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* MODAL: ADD TEST CASE (THÊM CÂU HỎI MỚI)                                   */}
      {/* ========================================================================= */}
      {showAdd && (
        <div className="modal-backdrop">
          <form
            className="modal-content"
            style={{ maxWidth: 620, borderRadius: 12 }}
            onSubmit={addTestCase}
          >
            <div className="modal-header">
              <h2 style={{ fontSize: 17, fontWeight: 700 }}>Thêm test case kiểm thử mới</h2>
              <button
                type="button"
                className="icon-button"
                onClick={() => setShowAdd(false)}
              >
                <X size={18} />
              </button>
            </div>
            <div className="modal-body">
              <label>
                Câu hỏi của công dân *
                <input
                  required
                  value={newQuestion}
                  onChange={(e) => setNewQuestion(e.target.value)}
                  placeholder="Ví dụ: Hồ sơ chuyển nhượng quyền sử dụng đất gồm những gì?"
                />
              </label>
              <label>
                Đáp án chuẩn (Ground truth) *
                <textarea
                  required
                  value={newAnswer}
                  onChange={(e) => setNewAnswer(e.target.value)}
                  placeholder="Nêu đầy đủ các ý chính, giấy tờ bắt buộc theo quy định pháp luật..."
                />
              </label>
              <label>
                Căn cứ pháp lý / Điều, Khoản
                <input
                  value={newSource}
                  onChange={(e) => setNewSource(e.target.value)}
                  placeholder="Ví dụ: Luật Đất đai 2024 Điều 133, Nghị định 101/2024/NĐ-CP"
                />
              </label>

              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr",
                  gap: 12,
                }}
              >
                <label>
                  Nhóm thủ tục
                  <select
                    value={newProcedure}
                    onChange={(e) => setNewProcedure(e.target.value)}
                  >
                    <option value="chuyen_nhuong">Chuyển nhượng</option>
                    <option value="tang_cho">Tặng cho</option>
                    <option value="bien_dong">ĐK Biến động</option>
                    <option value="cap_doi">Cấp đổi / Cấp lại</option>
                    <option value="tach_hop_thua">Tách / Hợp thửa</option>
                    <option value="cau_hoi_kho">Câu hỏi khó / Bẫy</option>
                  </select>
                </label>

                <label>
                  Mức độ khó (Level)
                  <select
                    value={newLevel}
                    onChange={(e) => setNewLevel(Number(e.target.value))}
                  >
                    <option value={1}>Level 1: Cơ bản</option>
                    <option value={2}>Level 2: Đời thường</option>
                    <option value={3}>Level 3: Bẫy / Khó</option>
                  </select>
                </label>
              </div>

              <div
                style={{
                  display: "flex",
                  justifyContent: "flex-end",
                  gap: 10,
                  marginTop: 18,
                }}
              >
                <button
                  type="button"
                  className="secondary-button"
                  onClick={() => setShowAdd(false)}
                >
                  Hủy
                </button>
                <button className="primary-button" disabled={busy}>
                  Lưu câu hỏi
                </button>
              </div>
            </div>
          </form>
        </div>
      )}

      {/* ========================================================================= */}
      {/* MODAL: EDIT TEST CASE (CHUYÊN GIA CHỈNH SỬA CÂU HỎI & ĐÁP ÁN)             */}
      {/* ========================================================================= */}
      {editingCase && (
        <div className="modal-backdrop">
          <form
            className="modal-content"
            style={{ maxWidth: 640, borderRadius: 12 }}
            onSubmit={saveEditTestCase}
          >
            <div className="modal-header">
              <h2 style={{ fontSize: 17, fontWeight: 700 }}>Chuyên gia chỉnh sửa câu hỏi & Đáp án chuẩn</h2>
              <button
                type="button"
                className="icon-button"
                onClick={() => setEditingCase(null)}
              >
                <X size={18} />
              </button>
            </div>
            <div className="modal-body">
              <label>
                Câu hỏi của công dân *
                <input
                  required
                  value={editQuestion}
                  onChange={(e) => setEditQuestion(e.target.value)}
                  placeholder="Ví dụ: Hồ sơ chuyển nhượng gồm những gì?"
                />
              </label>
              <label>
                Đáp án chuẩn (Ground truth do chuyên gia thẩm định) *
                <textarea
                  required
                  rows={4}
                  value={editAnswer}
                  onChange={(e) => setEditAnswer(e.target.value)}
                  placeholder="Nêu các căn cứ và nội dung bắt buộc..."
                />
              </label>
              <label>
                Căn cứ pháp lý / Nguồn luật
                <input
                  value={editSource}
                  onChange={(e) => setEditSource(e.target.value)}
                  placeholder="Ví dụ: Nghị định 101/2024/NĐ-CP, Điều 12"
                />
              </label>

              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr",
                  gap: 12,
                }}
              >
                <label>
                  Nhóm thủ tục
                  <select
                    value={editProcedure}
                    onChange={(e) => setEditProcedure(e.target.value)}
                  >
                    <option value="chuyen_nhuong">Chuyển nhượng</option>
                    <option value="tang_cho">Tặng cho</option>
                    <option value="bien_dong">ĐK Biến động</option>
                    <option value="cap_doi">Cấp đổi / Cấp lại</option>
                    <option value="tach_hop_thua">Tách / Hợp thửa</option>
                    <option value="cau_hoi_kho">Câu hỏi khó / Bẫy</option>
                  </select>
                </label>

                <label>
                  Mức độ khó (Level)
                  <select
                    value={editLevel}
                    onChange={(e) => setEditLevel(Number(e.target.value))}
                  >
                    <option value={1}>Level 1: Cơ bản</option>
                    <option value={2}>Level 2: Đời thường</option>
                    <option value={3}>Level 3: Bẫy / Khó</option>
                  </select>
                </label>
              </div>

              <div
                style={{
                  display: "flex",
                  justifyContent: "flex-end",
                  gap: 10,
                  marginTop: 18,
                }}
              >
                <button
                  type="button"
                  className="secondary-button"
                  onClick={() => setEditingCase(null)}
                >
                  Hủy
                </button>
                <button className="primary-button" disabled={busy}>
                  Lưu thay đổi
                </button>
              </div>
            </div>
          </form>
        </div>
      )}

      {/* Sticky Floating Action Bar for Selected Items */}
      {selectedIds.length > 0 && activeTab === "bank" && (
        <div
          style={{
            position: "fixed",
            bottom: 24,
            left: "50%",
            transform: "translateX(-50%)",
            background: "#0f172a",
            color: "#fff",
            padding: "10px 22px",
            borderRadius: 50,
            boxShadow: "0 12px 30px -4px rgba(0, 0, 0, 0.4), 0 4px 12px rgba(0, 0, 0, 0.25)",
            display: "flex",
            alignItems: "center",
            gap: 16,
            zIndex: 999,
            border: "1px solid #334155",
          }}
        >
          <span style={{ fontSize: 13, fontWeight: 600, whiteSpace: "nowrap" }}>
            Đã chọn: <strong style={{ color: "#4ade80", fontSize: 14 }}>{selectedIds.length}</strong> / {filteredBank.length} câu
          </span>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <button
              type="button"
              onClick={() => runEvaluation(selectedIds)}
              disabled={busy}
              style={{
                background: "#166b45",
                color: "#fff",
                border: "none",
                padding: "7px 16px",
                borderRadius: 20,
                fontWeight: 700,
                fontSize: 12.5,
                cursor: "pointer",
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
              }}
            >
              <Zap size={14} /> Chạy test {selectedIds.length} câu
            </button>
            <button
              type="button"
              onClick={deleteSelectedCases}
              disabled={busy}
              style={{
                background: "#dc2626",
                color: "#fff",
                border: "none",
                padding: "7px 16px",
                borderRadius: 20,
                fontWeight: 700,
                fontSize: 12.5,
                cursor: "pointer",
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
              }}
            >
              <Trash2 size={14} /> Xóa {selectedIds.length} câu
            </button>
            <button
              type="button"
              onClick={clearSelection}
              style={{
                background: "transparent",
                color: "#cbd5e1",
                border: "1px solid #475569",
                padding: "7px 14px",
                borderRadius: 20,
                fontSize: 12,
                cursor: "pointer",
                fontWeight: 600,
              }}
            >
              Bỏ chọn
            </button>
          </div>
        </div>
      )}
    </>
  );
}
