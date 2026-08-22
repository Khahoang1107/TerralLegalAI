import React, { useState, useEffect } from "react";
import { evaluationApi, type TestCase } from "@/lib/api";
import { Plus, TestTube2, Check, Clock3, Trash2, X, Loader2 } from "lucide-react";

export default function TestsView() {
  const [testCases, setTestCases] = useState<TestCase[]>([]);
  const [loading, setLoading] = useState(true);
  const [runningEval, setRunningEval] = useState(false);
  const [evalResult, setEvalResult] = useState<string | null>(null);
  
  // Modal state
  const [showAddModal, setShowAddModal] = useState(false);
  const [newQuestion, setNewQuestion] = useState("");
  const [newAnswer, setNewAnswer] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const fetchTestCases = async () => {
    setLoading(true);
    try {
      const data = await evaluationApi.getTestCases();
      setTestCases(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTestCases();
  }, []);

  const handleRunEvaluation = async () => {
    setRunningEval(true);
    setEvalResult(null);
    try {
      const result = await evaluationApi.runEvaluation();
      setEvalResult(`Đã khởi chạy đánh giá. Mã: ${result.run_id}`);
    } catch (err) {
      setEvalResult("Khởi chạy đánh giá thất bại.");
      console.error(err);
    } finally {
      setRunningEval(false);
    }
  };

  const handleAddTestCase = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newQuestion.trim() || !newAnswer.trim()) return;
    
    setSubmitting(true);
    try {
      await evaluationApi.createTestCase({
        question: newQuestion,
        expected_answer: newAnswer,
      });
      setShowAddModal(false);
      setNewQuestion("");
      setNewAnswer("");
      fetchTestCases();
    } catch (err) {
      console.error(err);
      alert("Lỗi khi thêm bộ test.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!window.confirm("Bạn có chắc chắn muốn xóa test case này?")) return;
    try {
      await evaluationApi.deleteTestCase(id);
      fetchTestCases();
    } catch (err) {
      console.error(err);
      alert("Lỗi khi xóa test case.");
    }
  };

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">Đánh giá định kỳ</span>
          <h1>Bộ kiểm thử</h1>
          <p>Quản lý câu hỏi và câu trả lời chuẩn dùng để đánh giá AI.</p>
        </div>
        <button className="primary-button fit" onClick={() => setShowAddModal(true)}>
          <Plus size={17} /> Thêm test case
        </button>
      </div>

      <section className="panel">
        <div className="test-summary">
          <div><strong>{testCases.length}</strong><span>Tổng test case</span></div>
          <div><strong>0</strong><span>Đạt yêu cầu</span></div>
          <div><strong>0</strong><span>Cần rà soát</span></div>
          <button 
            className="secondary-button" 
            onClick={handleRunEvaluation}
            disabled={runningEval || testCases.length === 0}
          >
            {runningEval ? <Loader2 size={16} className="spinner" /> : <TestTube2 size={16} />} 
            Chạy đánh giá
          </button>
        </div>
        
        {evalResult && (
          <div style={{ padding: "12px", background: "#f0fdfa", color: "#0f766e", borderRadius: "8px", marginBottom: "16px", fontSize: "0.875rem" }}>
            {evalResult}
          </div>
        )}

        {loading ? (
          <div style={{ padding: "40px", textAlign: "center", color: "#64748b" }}>
            <Clock3 style={{ margin: "0 auto 10px", display: "block" }} />
            Đang tải dữ liệu...
          </div>
        ) : testCases.length === 0 ? (
          <div style={{ padding: "40px", textAlign: "center", color: "#64748b" }}>
            <p>Không có test case nào.</p>
          </div>
        ) : (
          <div className="test-list">
            {testCases.map((tc, idx) => (
              <div key={tc.id}>
                <span className="test-id">TC-{String(idx + 1).padStart(3, '0')}</span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <strong style={{ display: "block", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{tc.question}</strong>
                  <p style={{ margin: "4px 0 0", color: "#64748b", fontSize: "0.8125rem", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>Ground truth: {tc.expected_answer}</p>
                </div>
                <button className="icon-button" style={{ color: "#ef4444" }} onClick={() => handleDelete(tc.id)}>
                  <Trash2 size={15} />
                </button>
              </div>
            ))}
          </div>
        )}
      </section>

      {showAddModal && (
        <div className="modal-backdrop">
          <div className="modal-content" style={{ maxWidth: 500 }}>
            <div className="modal-header">
              <h2>Thêm Test Case</h2>
              <button className="icon-button" onClick={() => setShowAddModal(false)}><X size={18} /></button>
            </div>
            <div className="modal-body">
              <form onSubmit={handleAddTestCase}>
                <div className="form-group" style={{ marginBottom: 16 }}>
                  <label style={{ display: "block", marginBottom: 6, fontWeight: 500, fontSize: "0.875rem" }}>Câu hỏi</label>
                  <input 
                    type="text" 
                    value={newQuestion} 
                    onChange={e => setNewQuestion(e.target.value)} 
                    placeholder="VD: Thời hạn giải quyết hồ sơ đất đai là bao lâu?"
                    style={{ width: "100%", padding: "10px", borderRadius: "6px", border: "1px solid #cbd5e1" }}
                    required
                  />
                </div>
                <div className="form-group" style={{ marginBottom: 20 }}>
                  <label style={{ display: "block", marginBottom: 6, fontWeight: 500, fontSize: "0.875rem" }}>Câu trả lời chuẩn (Ground truth)</label>
                  <textarea 
                    value={newAnswer} 
                    onChange={e => setNewAnswer(e.target.value)} 
                    placeholder="VD: Không quá 30 ngày làm việc."
                    style={{ width: "100%", padding: "10px", borderRadius: "6px", border: "1px solid #cbd5e1", minHeight: 80, resize: "vertical" }}
                    required
                  />
                </div>
                <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
                  <button type="button" className="secondary-button" onClick={() => setShowAddModal(false)}>Hủy</button>
                  <button type="submit" className="primary-button" disabled={submitting}>
                    {submitting ? "Đang lưu..." : "Lưu Test Case"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
