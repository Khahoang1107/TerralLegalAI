import axios from "axios";

// ─── Shared types ─────────────────────────────────────────────────

export interface ChatRequest {
  question: string;
  procedure_filter?: string;
  conversation_id?: string;
}

export interface Citation {
  source_name: string;
  article?: string;
  clause?: string;
  text_snippet?: string;
  relevance_score?: number;
}

export interface ChatResponse {
  answer: string;
  citations: Citation[];
  conversation_id?: string;
  message_id?: string;
  confidence?: number;
  intent?: string;
  is_fallback?: boolean;
  latency_ms?: number;
  form_completed?: boolean;
  form_id?: string;
  collected_data?: Record<string, string>;
}

export interface Conversation {
  id: string;
  title: string;
  created_at: string;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  created_at: string;
}

export interface ConversationDetail extends Conversation {
  messages: Message[];
  form_state?: {
    is_complete: boolean;
    active_form_id?: string;
    collected_data?: Record<string, string>;
  };
}

// ─── Document types ────────────────────────────────────────────────

export interface Document {
  id: string;
  source_name: string;
  file_path?: string;
  group_type: string;
  procedure_type: string;
  status: "pending" | "indexing" | "indexed" | "error";
  chunk_count: number;
  created_at: string;
  // Metadata hiệu lực
  document_number?: string;
  validity_status: string;
  promulgation_date?: string;
  effective_date?: string;
  issuing_agency?: string;
  related_documents?: { document_id: string; source_name: string; relation: string; effective_date?: string }[];
}

export interface DocumentStats {
  total_documents: number;
  indexed_documents: number;
  total_chunks_db: number;
  qdrant?: Record<string, unknown>;
}

export interface UploadDocumentResponse {
  document_id: string;
  source_name: string;
  status: string;
  message: string;
}

// ─── Evaluation types ─────────────────────────────────────────────

export interface TestCase {
  id: string;
  question: string;
  expected_answer: string;
  procedure_group?: string;
  intent?: string;
  source_doc?: string;
  field_type?: string;
  level?: number;
  created_at: string;
}

export interface TestCaseCreate {
  question: string;
  expected_answer: string;
  procedure_group?: string;
  intent?: string;
  source_doc?: string;
  field_type?: string;
  level?: number;
}

export interface EvaluationRun {
  id: string;
  run_date: string;
  faithfulness?: number;
  answer_relevancy?: number;
  context_precision?: number;
  context_recall?: number;
  total_questions?: number;
  passed_questions?: number;
  notes?: string;
}

export interface EvaluationRunRequest {
  max_questions?: number;
  procedure_group?: string;
  level?: number;
  notes?: string;
  use_ragas?: boolean;
}

export interface EvaluationCaseResult {
  id: string; question: string; expected_answer: string; actual_answer: string;
  answer_similarity?: number; grounding_score?: number; auto_status: string;
  manual_status: "pending" | "pass" | "fail"; manual_note?: string;
  retrieved_contexts: string[];
}

// ─── Auth types ───────────────────────────────────────────────────

export interface AuthUser {
  id: string;
  full_name: string;
  email: string;
  role: "citizen" | "admin";
}

export interface AuthResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  user: AuthUser;
}

// ─── Axios client setup ───────────────────────────────────────────

const baseUrlEnv = process.env.NEXT_PUBLIC_API_URL;
const baseURL = baseUrlEnv 
  ? (baseUrlEnv.endsWith('/api/v1') ? baseUrlEnv : `${baseUrlEnv.replace(/\/$/, '')}/api/v1`)
  : "http://localhost:8000/api/v1";

const client = axios.create({
  baseURL,
  timeout: 300_000,
});

const TOKEN_KEY = "terralegal_access_token";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY) ?? sessionStorage.getItem(TOKEN_KEY);
}

client.interceptors.request.use((config) => {
  const token = getToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// A token can expire while the portal is already open.  Clear it and notify
// React immediately instead of leaving the old screen visible and allowing a
// later chat request to fail with a confusing mix of 401/500 errors.
client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error?.response?.status === 401 && typeof window !== "undefined") {
      localStorage.removeItem(TOKEN_KEY);
      sessionStorage.removeItem(TOKEN_KEY);
      window.dispatchEvent(new Event("terralegal:unauthorized"));
    }
    return Promise.reject(error);
  },
);

// ─── Auth API ─────────────────────────────────────────────────────

export const authApi = {
  async login(identifier: string, password: string, remember = true): Promise<AuthResponse> {
    const { data } = await client.post<AuthResponse>("/auth/login", { email: identifier, password });
    this.saveToken(data.access_token, remember);
    return data;
  },
  async register(full_name: string, email: string, password: string): Promise<AuthResponse> {
    const { data } = await client.post<AuthResponse>("/auth/register", { full_name, email, password });
    this.saveToken(data.access_token, true);
    return data;
  },
  async changePassword(currentPassword: string, newPassword: string): Promise<void> {
    await client.post("/auth/change-password", {
      current_password: currentPassword,
      new_password: newPassword,
    });
  },
  async me(): Promise<AuthUser | null> {
    if (!getToken()) return null;
    try {
      const { data } = await client.get<AuthUser>("/auth/me");
      return data;
    } catch {
      this.logout();
      return null;
    }
  },
  saveToken(token: string, remember: boolean) {
    localStorage.removeItem(TOKEN_KEY);
    sessionStorage.removeItem(TOKEN_KEY);
    (remember ? localStorage : sessionStorage).setItem(TOKEN_KEY, token);
  },
  logout() {
    localStorage.removeItem(TOKEN_KEY);
    sessionStorage.removeItem(TOKEN_KEY);
  },
  async getOverview(): Promise<any> {
    const { data } = await client.get("/reports/overview");
    return data;
  }
};

// ─── Chat API ─────────────────────────────────────────────────────

export const chatApi = {
  async sendMessage(payload: ChatRequest): Promise<ChatResponse> {
    const { data } = await client.post<ChatResponse>("/chat", payload);
    return data;
  },
  async sendMessageStream(
    payload: ChatRequest,
    onDelta: (text: string) => void,
  ): Promise<ChatResponse> {
    const token = getToken();
    const response = await fetch(`${baseURL}/chat/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(payload),
    });

    if (response.status === 401 && typeof window !== "undefined") {
      localStorage.removeItem(TOKEN_KEY);
      sessionStorage.removeItem(TOKEN_KEY);
      window.dispatchEvent(new Event("terralegal:unauthorized"));
    }
    if (!response.ok || !response.body) {
      throw new Error(`Chat stream failed (${response.status})`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let finalResponse: ChatResponse | undefined;

    const consumeLine = (line: string) => {
      if (!line.trim()) return;
      const event = JSON.parse(line) as {
        type: "delta" | "done" | "error";
        data: string | ChatResponse | { detail?: string };
      };
      if (event.type === "delta") onDelta(event.data as string);
      if (event.type === "done") finalResponse = event.data as ChatResponse;
      if (event.type === "error") {
        throw new Error((event.data as { detail?: string }).detail || "Chat stream failed");
      }
    };

    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";
      lines.forEach(consumeLine);
      if (done) break;
    }
    consumeLine(buffer);

    if (!finalResponse) throw new Error("Chat stream ended without a final response");
    return finalResponse;
  },
  async sendFeedback(messageId: string, value: 1 | -1): Promise<void> {
    await client.post(`/messages/${messageId}/feedback`, { value });
  },
  async exportForm(form_id: string, payload: Record<string, string>): Promise<void> {
    const response = await client.post(`/forms/export/${form_id}?format=docx`, { data: payload }, {
      responseType: 'blob'
    });
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `BieuMau_${form_id}.docx`);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  },
  async getOverview(): Promise<any> {
    const { data } = await client.get("/reports/overview");
    return data;
  }
};

// ─── Conversation API ─────────────────────────────────────────────

export const conversationApi = {
  async getConversations(): Promise<Conversation[]> {
    const { data } = await client.get<Conversation[]>("/conversations");
    return data;
  },
  async getConversation(id: string): Promise<ConversationDetail> {
    const { data } = await client.get<ConversationDetail>(`/conversations/${id}`);
    return data;
  },
  async updateConversation(id: string, title: string): Promise<Conversation> {
    const { data } = await client.put<Conversation>(`/conversations/${id}`, { title });
    return data;
  },
  async deleteConversation(id: string): Promise<void> {
    await client.delete(`/conversations/${id}`);
  },
  async getOverview(): Promise<any> {
    const { data } = await client.get("/reports/overview");
    return data;
  }
};

// ─── Documents API ────────────────────────────────────────────────

export const documentsApi = {
  async getDocuments(params?: { group_type?: string; procedure_type?: string; status?: string }): Promise<Document[]> {
    const { data } = await client.get<Document[]>("/documents", { params });
    return data;
  },
  async getDocument(id: string): Promise<Document> {
    const { data } = await client.get<Document>(`/documents/${id}`);
    return data;
  },
  async getStats(): Promise<DocumentStats> {
    const { data } = await client.get<DocumentStats>("/documents/stats");
    return data;
  },
  async uploadDocument(
    file: File,
    sourceName: string,
    groupType: string,
    procedureType: string,
    opts?: {
      documentAction?: string;
      documentNumber?: string;
      promulgationDate?: string;
      effectiveDate?: string;
      issuingAgency?: string;
      parentDocumentId?: string;
    }
  ): Promise<UploadDocumentResponse> {
    const form = new FormData();
    form.append("file", file);
    form.append("source_name", sourceName);
    form.append("group_type", groupType);
    form.append("procedure_type", procedureType);
    if (opts?.documentAction) form.append("document_action", opts.documentAction);
    if (opts?.documentNumber) form.append("document_number", opts.documentNumber);
    if (opts?.promulgationDate) form.append("promulgation_date", opts.promulgationDate);
    if (opts?.effectiveDate) form.append("effective_date", opts.effectiveDate);
    if (opts?.issuingAgency) form.append("issuing_agency", opts.issuingAgency);
    if (opts?.parentDocumentId) form.append("parent_document_id", opts.parentDocumentId);
    const { data } = await client.post<UploadDocumentResponse>("/documents/upload", form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return data;
  },
  async deleteDocument(id: string): Promise<void> {
    await client.delete(`/documents/${id}`);
  },
  async reindexDocument(id: string): Promise<{ document_id: string; status: string; message: string }> {
    const { data } = await client.put(`/documents/${id}/reindex`);
    return data;
  },
  async getChunks(id: string): Promise<{ id: string; text: string; article?: string; clause?: string; field_type?: string }[]> {
    const { data } = await client.get(`/documents/${id}/chunks`); return data;
  },
  async getOverview(): Promise<any> {
    const { data } = await client.get("/reports/overview");
    return data;
  }
};

// ─── Evaluation API ───────────────────────────────────────────────

export const evaluationApi = {
  async getTestCases(params?: { procedure_group?: string; level?: number }): Promise<TestCase[]> {
    const { data } = await client.get<TestCase[]>("/evaluation/test-cases", { params });
    return data;
  },
  async createTestCase(payload: TestCaseCreate): Promise<TestCase> {
    const { data } = await client.post<TestCase>("/evaluation/test-cases", payload);
    return data;
  },
  async deleteTestCase(id: string): Promise<void> {
    await client.delete(`/evaluation/test-cases/${id}`);
  },
  async updateTestCase(id: string, payload: TestCaseCreate): Promise<TestCase> {
    const { data } = await client.put<TestCase>(`/evaluation/test-cases/${id}`, payload); return data;
  },
  async importTestCases(file: File): Promise<{ created: number; errors: { line: number; error: string }[] }> {
    const form = new FormData(); form.append("file", file);
    const { data } = await client.post("/evaluation/test-cases/import", form); return data;
  },
  async runEvaluation(payload?: EvaluationRunRequest): Promise<{ run_id: string; status: string; message: string; total_questions?: number }> {
    const { data } = await client.post("/evaluation/run", payload ?? {});
    return data;
  },
  async getResults(): Promise<EvaluationRun[]> {
    const { data } = await client.get<EvaluationRun[]>("/evaluation/results");
    return data;
  },
  async getResult(id: string): Promise<EvaluationRun> {
    const { data } = await client.get<EvaluationRun>(`/evaluation/results/${id}`);
    return data;
  },
  async getResultCases(runId: string): Promise<{ items: EvaluationCaseResult[]; total: number }> {
    const { data } = await client.get(`/evaluation/results/${runId}/cases`); return data;
  },
  async reviewResultCase(id: string, status: "pass" | "fail" | "pending", note = ""): Promise<void> {
    await client.put(`/evaluation/results/cases/${id}/review`, { status, note });
  },
  async getOverview(): Promise<any> {
    const { data } = await client.get("/reports/overview");
    return data;
  }
};

// ─── Forms API ────────────────────────────────────────────────────

export const formsApi = {
  async getForms(): Promise<any[]> {
    const { data } = await client.get("/forms");
    return data;
  },
  async getForm(id: string): Promise<any> {
    const { data } = await client.get(`/forms/${id}`);
    return data;
  },
  async deleteForm(id: string): Promise<void> {
    await client.delete(`/forms/${id}`);
  },
  async updateForm(id: string, payload: { name: string; procedure_type: string; description?: string; fields?: any[] }): Promise<any> {
    const { data } = await client.put(`/forms/${id}`, payload);
    return data;
  },
  async updateTemplate(id: string, file: File): Promise<any> {
    const formData = new FormData();
    formData.append("file", file);
    const { data } = await client.put(`/forms/${id}/template`, formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return data;
  },

  async previewPdf(formId: string, data: Record<string, any>, mode?: string): Promise<Blob> {
    const url = mode ? `/forms/preview-pdf/${formId}?mode=${mode}` : `/forms/preview-pdf/${formId}`;
    const response = await client.post(url, data, {
      responseType: 'blob'
    });
    return response.data;
  },
  async previewImages(formId: string, data: Record<string, any> = {}, mode?: string): Promise<string[]> {
    const url = mode ? `/forms/preview-pdf/${formId}?format=images&mode=${mode}` : `/forms/preview-pdf/${formId}?format=images`;
    const response = await client.post(url, data);
    return response.data.page_images || [];
  },
  async generateFormDocument(id: string, data: any, format: "docx" | "pdf" = "docx"): Promise<Blob> {
    if (format === "pdf") {
      return this.previewPdf(id, data);
    }
    const response = await client.post(`/forms/${id}/generate`, { data }, { responseType: 'blob' });
    return response.data;
  },
  async analyzeDocx(file: File): Promise<any> {
    const form = new FormData();
    form.append("file", file);
    const { data } = await client.post("/forms/analyze-docx", form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return data;
  },
  async uploadForm(jsonFile: File, docxFile: File): Promise<any> {
    const form = new FormData();
    form.append("json_file", jsonFile);
    form.append("docx_file", docxFile);
    const { data } = await client.post("/forms/upload", form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return data;
  },
  async createVisualForm(payload: any): Promise<any> {
    const { data } = await client.post("/forms/create-visual", payload);
    return data;
  },
  async createFormFromDocxJson(docxFile: File, jsonFile: File): Promise<any> {
    const form = new FormData();
    form.append("docx_file", docxFile);
    form.append("json_file", jsonFile);
    const { data } = await client.post("/forms/upload", form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return data;
  },
  async aiPredict(tempId: string, zones: any[], userLabels?: Record<string, string>): Promise<{
    predictions: Record<string, { label: string; description: string; confidence: number; section: string }>;
    zones: any[];
    total: number;
  }> {
    const { data } = await client.post("/forms/ai-predict", { temp_id: tempId, zones, user_labels: userLabels });
    return data;
  },
  async getOverview(): Promise<any> {
    const { data } = await client.get("/reports/overview");
    return data;
  }
};

// ─── Reports API ──────────────────────────────────────────────────

export const reportsApi = {
  async getStats(): Promise<{
    feedback_stats: { total: number; up_pct: number; down_pct: number };
    topic_stats: { name: string; percentage: number }[];
    fallback_logs: { question: string; time: string; reason: string }[];
  }> {
    const { data } = await client.get("/reports/stats");
    return data;
  },
  async getOverview(): Promise<any> {
    const { data } = await client.get("/reports/overview");
    return data;
  }
};


export const usersApi = {
  async getUsers(): Promise<any[]> {
    const { data } = await client.get('/users');
    return data;
  },
  async updateUser(id: string, payload: { role?: string; is_active?: boolean }): Promise<any> {
    const { data } = await client.put('/users/' + id, payload);
    return data;
  },
  async deleteUser(id: string): Promise<any> {
    const { data } = await client.delete('/users/' + id);
    return data;
  }
};
