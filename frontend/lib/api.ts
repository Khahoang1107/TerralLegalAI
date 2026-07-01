import axios from "axios";

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

const client = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1",
  timeout: 60_000,
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

export const chatApi = {
  async sendMessage(payload: ChatRequest): Promise<ChatResponse> {
    const response = await client.post<ChatResponse>("/chat", payload);
    return response.data;
  },
};

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
  }
};
