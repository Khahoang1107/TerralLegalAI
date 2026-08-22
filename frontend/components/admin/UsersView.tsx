import React, { useState, useEffect } from "react";
import { usersApi } from "@/lib/api";
import { Edit, Trash2, CheckCircle2, XCircle, Clock3, RefreshCw, AlertCircle } from "lucide-react";

export default function UsersView() {
  // Force HMR reload
  const [users, setUsers] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingUser, setEditingUser] = useState<string | null>(null);
  const [savingId, setSavingId] = useState<string | null>(null);

  const fetchUsers = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await usersApi.getUsers();
      setUsers(data);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Không thể tải danh sách người dùng. Vui lòng thử lại.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchUsers(); }, []);

  const handleDelete = async (id: string) => {
    if (!confirm("Bạn có chắc chắn muốn xóa người dùng này?")) return;
    try {
      await usersApi.deleteUser(id);
      setUsers(prev => prev.filter(u => u.id !== id));
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Không thể xóa người dùng.");
    }
  };

  const handleUpdate = async (id: string, payload: { role?: string; is_active?: boolean }) => {
    setSavingId(id);
    try {
      const updated = await usersApi.updateUser(id, payload);
      setUsers(prev => prev.map(u => u.id === id ? updated : u));
      setEditingUser(null);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Không thể cập nhật người dùng.");
    } finally {
      setSavingId(null);
    }
  };

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">Hệ thống</span>
          <h1>Quản lý người dùng</h1>
          <p>Xem và quản lý tài khoản người dùng, phân quyền truy cập hệ thống.</p>
        </div>
        <button onClick={fetchUsers} className="secondary-button" disabled={loading}>
          <RefreshCw size={16} />
          Làm mới
        </button>
      </div>

      {error && (
        <div style={{ padding: "14px 18px", background: "#fef2f2", borderRadius: 8, color: "#dc2626", display: "flex", alignItems: "center", gap: 10, marginBottom: 16, fontSize: "0.875rem" }}>
          <AlertCircle size={16} style={{ flexShrink: 0 }} />
          <span>{error}</span>
          <button onClick={() => setError(null)} style={{ marginLeft: "auto", background: "none", border: "none", cursor: "pointer", color: "#dc2626", fontWeight: 600 }}>x</button>
        </div>
      )}

      <section className="panel">
        <div className="test-summary" style={{ marginBottom: "20px" }}>
          <div><strong>{users.length}</strong><span>Tổng số người dùng</span></div>
          <div><strong>{users.filter(u => u.role === "admin").length}</strong><span>Quản trị viên</span></div>
          <div><strong>{users.filter(u => u.is_active).length}</strong><span>Đang hoạt động</span></div>
        </div>

        {loading ? (
          <div style={{ padding: "40px", textAlign: "center", color: "#64748b" }}>
            <Clock3 style={{ margin: "0 auto 10px", display: "block" }} />
            Đang tải dữ liệu...
          </div>
        ) : users.length === 0 && !error ? (
          <div style={{ padding: "40px", textAlign: "center", color: "#64748b" }}>
            <p>Không có người dùng nào.</p>
            <button className="secondary-button" onClick={fetchUsers} style={{ marginTop: 12 }}><RefreshCw size={15} /> Thử lại</button>
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.875rem", textAlign: "left" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid #e2e8f0", color: "#64748b" }}>
                  <th style={{ padding: "12px 16px", fontWeight: 600 }}>Họ và tên</th>
                  <th style={{ padding: "12px 16px", fontWeight: 600 }}>Email</th>
                  <th style={{ padding: "12px 16px", fontWeight: 600 }}>Vai trò</th>
                  <th style={{ padding: "12px 16px", fontWeight: 600 }}>Trạng thái</th>
                  <th style={{ padding: "12px 16px", fontWeight: 600 }}>Ngày tạo</th>
                  <th style={{ padding: "12px 16px", fontWeight: 600, textAlign: "right" }}>Hành động</th>
                </tr>
              </thead>
              <tbody>
                {users.map(user => (
                  <tr key={user.id} style={{ borderBottom: "1px solid #f1f5f9", opacity: savingId === user.id ? 0.5 : 1 }}>
                    <td style={{ padding: "12px 16px", fontWeight: 500, color: "#1e293b" }}>{user.full_name}</td>
                    <td style={{ padding: "12px 16px", color: "#475569" }}>{user.email}</td>
                    <td style={{ padding: "12px 16px" }}>
                      {editingUser === user.id ? (
                        <select defaultValue={user.role} onChange={(e) => handleUpdate(user.id, { role: e.target.value })} style={{ padding: "4px 8px", borderRadius: "4px", border: "1px solid #cbd5e1" }} disabled={savingId === user.id}>
                          <option value="citizen">Công dân</option>
                          <option value="admin">Quản trị viên</option>
                        </select>
                      ) : (
                        <span style={{ display: "inline-block", padding: "2px 8px", borderRadius: "12px", fontSize: "0.75rem", fontWeight: 600, backgroundColor: user.role === "admin" ? "#e0e7ff" : "#f1f5f9", color: user.role === "admin" ? "#4338ca" : "#475569" }}>
                          {user.role === "admin" ? "Quản trị viên" : "Công dân"}
                        </span>
                      )}
                    </td>
                    <td style={{ padding: "12px 16px" }}>
                      {editingUser === user.id ? (
                        <select defaultValue={user.is_active ? "true" : "false"} onChange={(e) => handleUpdate(user.id, { is_active: e.target.value === "true" })} style={{ padding: "4px 8px", borderRadius: "4px", border: "1px solid #cbd5e1" }} disabled={savingId === user.id}>
                          <option value="true">Hoạt động</option>
                          <option value="false">Bị khóa</option>
                        </select>
                      ) : (
                        <span style={{ display: "flex", alignItems: "center", gap: "6px", color: user.is_active ? "#10b981" : "#ef4444" }}>
                          {user.is_active ? <CheckCircle2 size={16} /> : <XCircle size={16} />}
                          {user.is_active ? "Hoạt động" : "Bị khóa"}
                        </span>
                      )}
                    </td>
                    <td style={{ padding: "12px 16px", color: "#64748b" }}>{user.created_at ? new Date(user.created_at).toLocaleDateString("vi-VN") : "-"}</td>
                    <td style={{ padding: "12px 16px", textAlign: "right" }}>
                      {editingUser === user.id ? (
                        <button onClick={() => setEditingUser(null)} style={{ padding: "6px 12px", background: "#f1f5f9", border: "none", borderRadius: "4px", cursor: "pointer", fontSize: "0.75rem", fontWeight: 600, color: "#475569" }}>Hủy</button>
                      ) : (
                        <div style={{ display: "flex", justifyContent: "flex-end", gap: "8px" }}>
                          <button onClick={() => setEditingUser(user.id)} style={{ background: "none", border: "none", cursor: "pointer", color: "#3b82f6", padding: 4 }} title="Chỉnh sửa"><Edit size={16} /></button>
                          <button onClick={() => handleDelete(user.id)} style={{ background: "none", border: "none", cursor: "pointer", color: "#ef4444", padding: 4 }} title="Xóa"><Trash2 size={16} /></button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
