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
  timeout: 120_000,
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

// ─── Auth API ─────────────────────────────────────────────────────

export const authApi = {
  async login(email: string, password: string, remember = true): Promise<AuthResponse> {
    const { data } = await client.post<AuthResponse>("/auth/login", { email, password });
    this.saveToken(data.access_token, remember);
    return data;
  },
  async register(full_name: string, email: string, password: string): Promise<AuthResponse> {
    const { data } = await client.post<AuthResponse>("/auth/register", { full_name, email, password });
    this.saveToken(data.access_token, true);
    return data;
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
};

// ─── Chat API ─────────────────────────────────────────────────────

export const chatApi = {
  async sendMessage(payload: ChatRequest): Promise<ChatResponse> {
    const { data } = await client.post<ChatResponse>("/chat", payload);
    return data;
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
    procedureType: string
  ): Promise<UploadDocumentResponse> {
    const form = new FormData();
    form.append("file", file);
    form.append("source_name", sourceName);
    form.append("group_type", groupType);
    form.append("procedure_type", procedureType);
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
  async runEvaluation(payload?: EvaluationRunRequest): Promise<{ run_id: string; status: string; message: string }> {
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
};

// ─── Forms API ────────────────────────────────────────────────────

export const formsApi = {
  async getForms(): Promise<any[]> {
    const { data } = await client.get("/forms");
    return data;
  },
  async deleteForm(id: string): Promise<void> {
    await client.delete(`/forms/${id}`);
  },
  async updateForm(id: string, payload: { name: string; procedure_type: string; description?: string }): Promise<any> {
    const { data } = await client.put(`/forms/${id}`, payload);
    return data;
  },
  async analyzeDocx(file: File): Promise<any> {
    const form = new FormData();
    form.append("file", file);
    const { data } = await client.post("/forms/analyze-docx", form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return data;
  },
  async createVisualForm(payload: any): Promise<any> {
    const { data } = await client.post("/forms/create-visual", payload);
    return data;
  },
  async aiPredict(tempId: string, zones: any[]): Promise<{
    predictions: Record<string, { label: string; description: string; confidence: number; section: string }>;
    zones: any[];
    total: number;
  }> {
    const { data } = await client.post("/forms/ai-predict", { temp_id: tempId, zones });
    return data;
  },
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
};
