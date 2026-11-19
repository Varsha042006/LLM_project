// API Client for ChatGPT Platform
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api";

export interface User {
  id: string;
  email: string;
  display_name: string;
  username?: string;
  plan?: string;
  age_range?: string;
  gpt_builder_profile?: string;
  avatar_url?: string;
  auth_provider: string;
  is_verified: boolean;
}

export interface Chat {
  id: string;
  title: string;
  model_name: string;
  is_archived?: boolean;
  created_at: string;
  updated_at: string;
  message_count?: number;
}

export interface Message {
  id: string;
  chat_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  sources?: string;
  feedback?: "like" | "dislike" | null;
  created_at: string;
}

export interface DocumentItem {
  id: string;
  filename: string;
  file_type: string;
  file_size: number;
  num_chunks: number;
  created_at: string;
}

export interface UserSettings {
  provider: string;
  api_key_set: boolean;
  base_url?: string;
  model_name: string;
  temperature: number;
  top_p: number;
  max_tokens?: number;
  system_prompt: string;
  theme: string;
  memory_enabled?: boolean;
  memory_summary?: string;
  reference_photo_url?: string;
  full_body_photo_url?: string;
  tone_warmth?: string;
}

export interface ActiveSession {
  id: string;
  user_agent?: string;
  ip_address?: string;
  created_at: string;
  last_active: string;
  is_current?: boolean;
}

export interface UsageMetrics {
  plan_name: string;
  plan_price: string;
  member_since: string;
  status: string;
  monthly_prompts_used: number;
  monthly_prompts_limit: number;
  total_chats: number;
  prompts_sent: number;
  ai_responses: number;
  documents_count: number;
  pages_indexed: number;
}

export interface HostedModel {
  id: string;
  name: string;
  provider: string;
  description: string;
}

// Token helper
export const getToken = (): string | null => {
  if (typeof window !== "undefined") {
    return localStorage.getItem("chatgpt_token");
  }
  return null;
};

export const setToken = (token: string) => {
  if (typeof window !== "undefined") {
    localStorage.setItem("chatgpt_token", token);
  }
};

export const removeToken = () => {
  if (typeof window !== "undefined") {
    localStorage.removeItem("chatgpt_token");
  }
};

const getHeaders = (isMultipart: boolean = false) => {
  const headers: Record<string, string> = {};
  if (!isMultipart) {
    headers["Content-Type"] = "application/json";
  }
  const token = getToken();
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return headers;
};

// -----------------------------------------------------------------------------
// Auth Services
// -----------------------------------------------------------------------------
export async function loginGuest(): Promise<{ access_token: string; user: User }> {
  const res = await fetch(`${API_BASE}/auth/guest`, {
    method: "POST",
    headers: getHeaders(),
  });
  if (!res.ok) throw new Error("Failed to sign in as Guest User");
  const data = await res.json();
  setToken(data.access_token);
  return data;
}

export async function loginEmail(email: string, password: string): Promise<{ access_token: string; user: User }> {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Invalid email or password");
  }
  const data = await res.json();
  setToken(data.access_token);
  return data;
}

export async function registerEmail(email: string, password: string, display_name?: string): Promise<{ access_token: string; user: User }> {
  const res = await fetch(`${API_BASE}/auth/register`, {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify({ email, password, display_name }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Registration failed");
  }
  const data = await res.json();
  setToken(data.access_token);
  return data;
}

export async function loginGoogle(name?: string, email?: string, avatar_url?: string, token?: string): Promise<{ access_token: string; user: User }> {
  const res = await fetch(`${API_BASE}/auth/google`, {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify({ name, email, avatar_url, token }),
  });
  if (!res.ok) throw new Error("Google login failed");
  const data = await res.json();
  setToken(data.access_token);
  return data;
}

export async function getMe(): Promise<User | null> {
  const token = getToken();
  if (!token) return null;
  try {
    const res = await fetch(`${API_BASE}/auth/me`, {
      headers: getHeaders(),
    });
    if (!res.ok) {
      removeToken();
      return null;
    }
    return await res.json();
  } catch {
    return null;
  }
}

// -----------------------------------------------------------------------------
// Chat Services
// -----------------------------------------------------------------------------
export async function listChats(search?: string): Promise<Chat[]> {
  const url = search ? `${API_BASE}/chats?search=${encodeURIComponent(search)}` : `${API_BASE}/chats`;
  const res = await fetch(url, { headers: getHeaders() });
  if (!res.ok) return [];
  return await res.json();
}

export async function createChat(title: string = "New Chat", model_name?: string): Promise<Chat> {
  const res = await fetch(`${API_BASE}/chats`, {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify({ title, model_name }),
  });
  if (!res.ok) throw new Error("Failed to create chat");
  return await res.json();
}

export async function getChatDetail(chatId: string): Promise<Chat & { messages: Message[] }> {
  const res = await fetch(`${API_BASE}/chats/${chatId}`, { headers: getHeaders() });
  if (!res.ok) throw new Error("Failed to load chat details");
  return await res.json();
}

export async function renameChat(chatId: string, title: string): Promise<Chat> {
  const res = await fetch(`${API_BASE}/chats/${chatId}`, {
    method: "PATCH",
    headers: getHeaders(),
    body: JSON.stringify({ title }),
  });
  if (!res.ok) throw new Error("Failed to rename chat");
  return await res.json();
}

export async function deleteChat(chatId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/chats/${chatId}`, {
    method: "DELETE",
    headers: getHeaders(),
  });
  if (!res.ok) throw new Error("Failed to delete chat");
}

export async function sendFeedback(messageId: string, feedback: "like" | "dislike" | null): Promise<void> {
  await fetch(`${API_BASE}/chat/feedback`, {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify({ message_id: messageId, feedback }),
  });
}

export interface ImageUploadResult {
  url: string;
  filename: string;
  width: number;
  height: number;
  format: string;
  size: number;
}

export async function uploadImage(file: File): Promise<ImageUploadResult> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_BASE}/upload/image`, {
    method: "POST",
    headers: getHeaders(true),
    body: formData,
  });

  if (!res.ok) {
    const errText = await res.text();
    throw new Error(`Failed to upload image: ${errText}`);
  }

  return await res.json();
}

export interface ImageEditParams {
  image_url: string;
  instruction: string;
  mask_data?: string; // base64 data URI
  chat_id?: string;
  operation?: string;
}

export interface ImageEditResult {
  status: string;
  image_url: string;
  original_url?: string;
  operation: string;
  instruction: string;
  version: number;
  filename: string;
  dimensions?: { width: number; height: number };
  pixel_preservation?: string;
}

export interface ImageVersionItem {
  version: number;
  image_url: string;
  filename: string;
  operation: string;
  instruction: string;
  parent_url?: string;
  timestamp: string;
}

export async function editImage(params: ImageEditParams): Promise<ImageEditResult> {
  const res = await fetch(`${API_BASE}/image/edit`, {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify(params),
  });

  if (!res.ok) {
    const errText = await res.text();
    throw new Error(`Failed to edit image: ${errText}`);
  }

  return await res.json();
}

export async function getImageLineage(chatId: string): Promise<ImageVersionItem[]> {
  const res = await fetch(`${API_BASE}/image/lineage/${chatId}`, {
    headers: getHeaders(),
  });
  if (!res.ok) return [];
  const data = await res.json();
  return data.versions || [];
}

// -----------------------------------------------------------------------------
// Real-Time SSE Token Stream
// -----------------------------------------------------------------------------
export async function streamChatResponse(
  params: {
    chat_id?: string;
    message: string;
    image_url?: string;
    document_name?: string;
    model_name?: string;
    use_rag?: boolean;
    temperature?: number;
    top_p?: number;
    system_prompt?: string;
  },
  onToken: (token: string) => void,
  onMeta?: (meta: { chat_id: string; sources: any[] }) => void,
  signal?: AbortSignal
): Promise<void> {
  const res = await fetch(`${API_BASE}/chat/stream`, {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify(params),
    signal,
  });

  if (!res.ok) {
    const errText = await res.text();
    throw new Error(`Streaming failed (${res.status}): ${errText}`);
  }

  const reader = res.body?.getReader();
  if (!reader) throw new Error("No response body readable stream.");

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n\n");
    buffer = lines.pop() || "";

    for (const block of lines) {
      const line = block.trim();
      if (!line.startsWith("data: ")) continue;
      const dataStr = line.replace("data: ", "").trim();
      if (!dataStr) continue;

      try {
        const payload = JSON.parse(dataStr);
        if (payload.type === "meta" && onMeta) {
          onMeta(payload);
        } else if (payload.type === "token") {
          onToken(payload.content);
        } else if (payload.type === "done") {
          return;
        }
      } catch (err) {
        // Fallback for raw text token
        onToken(dataStr);
      }
    }
  }
}

// -----------------------------------------------------------------------------
// Document RAG Services
// -----------------------------------------------------------------------------
export async function listDocuments(): Promise<DocumentItem[]> {
  const res = await fetch(`${API_BASE}/documents`, { headers: getHeaders() });
  if (!res.ok) return [];
  return await res.json();
}

export async function uploadDocument(file: File): Promise<DocumentItem> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_BASE}/documents/upload`, {
    method: "POST",
    headers: getHeaders(true),
    body: formData,
  });

  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Upload failed");
  }
  return await res.json();
}

export async function deleteDocument(docId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/documents/${docId}`, {
    method: "DELETE",
    headers: getHeaders(),
  });
  if (!res.ok) throw new Error("Failed to delete document");
}

export async function clearAllDocuments(): Promise<void> {
  await fetch(`${API_BASE}/documents`, {
    method: "DELETE",
    headers: getHeaders(),
  });
}

// -----------------------------------------------------------------------------
// Settings & Models Services
// -----------------------------------------------------------------------------
export async function getSettings(): Promise<UserSettings> {
  const res = await fetch(`${API_BASE}/settings`, { headers: getHeaders() });
  if (!res.ok) throw new Error("Failed to load settings");
  return await res.json();
}

export async function updateSettings(settings: Partial<UserSettings>): Promise<UserSettings> {
  const res = await fetch(`${API_BASE}/settings`, {
    method: "PATCH",
    headers: getHeaders(),
    body: JSON.stringify(settings),
  });
  if (!res.ok) throw new Error("Failed to update settings");
  return await res.json();
}

export async function getAvailableModels(): Promise<HostedModel[]> {
  const res = await fetch(`${API_BASE}/models`);
  if (!res.ok) return [];
  return await res.json();
}

// -----------------------------------------------------------------------------
// Neural LLM X-Ray Services
// -----------------------------------------------------------------------------
export interface XRayToken {
  index: number;
  token_id: number;
  raw_token: string;
  decoded_token: string;
  display_token: string;
  char_length: number;
}

export interface XRayEmbeddingStat {
  token_index: number;
  token_text?: string;
  norm: number;
  mean: number;
  std: number;
  slice: number[];
}

export interface XRayPrediction {
  rank: number;
  token_id: number;
  token_str: string;
  display_str: string;
  logit: number;
  probability: number;
  percentage: number;
}

export interface XRayRolloutStep {
  step: number;
  chosen_token_id: number;
  chosen_token_str: string;
  chosen_display_str: string;
  accumulated_text: string;
}

export interface XRayData {
  model_metadata: {
    model_type: string;
    num_layers: number;
    hidden_dim: number;
    num_heads: number;
    vocab_size: number;
    intermediate_dim: number;
    num_parameters_formatted: string;
    device: string;
  };
  tokens: XRayToken[];
  embeddings: {
    dim: number;
    stats: XRayEmbeddingStat[];
    heatmap_sample?: number[][];
    pca_coords?: { index: number; token: string; token_id: number; x: number; y: number }[];
  };
  selected: {
    layer_idx: number;
    head_idx: number;
    token_idx: number;
  };
  attention_matrix: number[][];
  layer_avg_attention_matrix?: number[][];
  hidden_states_pca: { layer: number; x: number; y: number }[];
  hidden_states_trajectories?: Record<string, { layer: number; x: number; y: number }[]>;
  predictions: XRayPrediction[];
  generated_response?: string;
  rollout_steps?: XRayRolloutStep[];
}

export async function inspectXRay(params: {
  text: string;
  layer_idx?: number;
  head_idx?: number;
  token_idx?: number;
  max_new_tokens?: number;
}): Promise<XRayData> {
  const res = await fetch(`${API_BASE}/xray/inspect`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "X-Ray inspection failed");
  }
  return await res.json();
}

// -----------------------------------------------------------------------------
// Document Generation & Export
// -----------------------------------------------------------------------------
export async function downloadDocument(
  content: string,
  title: string = "Document",
  format: "pdf" | "docx" | "md" | "txt" = "pdf"
): Promise<void> {
  const res = await fetch(`${API_BASE}/export/document`, {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify({ title, content, format }),
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Document export failed: ${err}`);
  }

  const blob = await res.blob();
  const disposition = res.headers.get("Content-Disposition");
  let filename = `${title.replace(/\s+/g, "_")}.${format}`;
  if (disposition) {
    const match = disposition.match(/filename="?([^"]+)"?/);
    if (match && match[1]) {
      filename = match[1];
    }
  }

  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}

export async function downloadChat(
  chatId: string,
  format: "pdf" | "docx" | "md" | "txt" = "pdf"
): Promise<void> {
  const res = await fetch(`${API_BASE}/export/chat/${chatId}?format=${format}`, {
    headers: getHeaders(),
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Chat export failed: ${err}`);
  }

  const blob = await res.blob();
  const disposition = res.headers.get("Content-Disposition");
  let filename = `Chat_Export.${format}`;
  if (disposition) {
    const match = disposition.match(/filename="?([^"]+)"?/);
    if (match && match[1]) {
      filename = match[1];
    }
  }

  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}

// -----------------------------------------------------------------------------
// Extended Settings, Profile, Sessions & Usage APIs
// -----------------------------------------------------------------------------
export async function updateUserProfile(data: {
  display_name?: string;
  username?: string;
  email?: string;
  gpt_builder_profile?: string;
  age_range?: string;
}): Promise<User> {
  const res = await fetch(`${API_BASE}/auth/profile`, {
    method: "PATCH",
    headers: getHeaders(),
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || "Failed to update profile");
  }
  return res.json();
}

export async function changePassword(current_password?: string, new_password?: string): Promise<any> {
  const res = await fetch(`${API_BASE}/auth/change-password`, {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify({ current_password, new_password }),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || "Failed to change password");
  }
  return res.json();
}

export async function deleteAccount(): Promise<any> {
  const res = await fetch(`${API_BASE}/auth/account`, {
    method: "DELETE",
    headers: getHeaders(),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || "Failed to delete account");
  }
  removeToken();
  return res.json();
}

export async function getSessions(): Promise<ActiveSession[]> {
  const res = await fetch(`${API_BASE}/auth/sessions`, {
    headers: getHeaders(),
  });
  if (!res.ok) return [];
  return res.json();
}

export async function terminateSession(sessionId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/auth/sessions/${sessionId}`, {
    method: "DELETE",
    headers: getHeaders(),
  });
  return res.json();
}

export async function getUsageMetrics(): Promise<UsageMetrics> {
  const res = await fetch(`${API_BASE}/settings/usage`, {
    headers: getHeaders(),
  });
  if (!res.ok) {
    return {
      plan_name: "VYNEXA AI Free",
      plan_price: "₹0 / month",
      member_since: "Member since November 2026",
      status: "Active",
      monthly_prompts_used: 7,
      monthly_prompts_limit: 1000,
      total_chats: 6,
      prompts_sent: 7,
      ai_responses: 7,
      documents_count: 1,
      pages_indexed: 7,
    };
  }
  return res.json();
}

export async function getArchivedChats(): Promise<Chat[]> {
  const res = await fetch(`${API_BASE}/chats/archived`, {
    headers: getHeaders(),
  });
  if (!res.ok) return [];
  return res.json();
}

export async function archiveChat(chatId: string): Promise<Chat> {
  const res = await fetch(`${API_BASE}/chats/${chatId}/archive`, {
    method: "POST",
    headers: getHeaders(),
  });
  if (!res.ok) throw new Error("Failed to archive chat");
  return res.json();
}

export async function unarchiveChat(chatId: string): Promise<Chat> {
  const res = await fetch(`${API_BASE}/chats/${chatId}/unarchive`, {
    method: "POST",
    headers: getHeaders(),
  });
  if (!res.ok) throw new Error("Failed to unarchive chat");
  return res.json();
}

export async function uploadReferencePhoto(file: File, photoType: "portrait" | "full_body"): Promise<{ url: string }> {
  const token = getToken();
  const formData = new FormData();
  formData.append("photo_type", photoType);
  formData.append("file", file);

  const res = await fetch(`${API_BASE}/settings/upload-photo`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: formData,
  });
  if (!res.ok) throw new Error("Failed to upload photo");
  return res.json();
}

export async function clearLearnedMemory(): Promise<any> {
  const res = await fetch(`${API_BASE}/settings/memory`, {
    method: "DELETE",
    headers: getHeaders(),
  });
  return res.json();
}

export interface MemoryCategory {
  id: string;
  title: string;
  icon: string;
  badge: string;
  content: string;
}

export interface MemoryDetailResponse {
  enabled: boolean;
  summary: string;
  categories: MemoryCategory[];
  total_chats_analyzed: number;
  last_updated?: string;
}

export async function getStructuredMemory(): Promise<MemoryDetailResponse> {
  const res = await fetch(`${API_BASE}/settings/memory`, {
    headers: getHeaders(),
  });
  if (!res.ok) throw new Error("Failed to load structured memory");
  return res.json();
}

export async function updateStructuredMemory(data: {
  category_id?: string;
  content?: string;
  summary?: string;
}): Promise<MemoryDetailResponse> {
  const res = await fetch(`${API_BASE}/settings/memory`, {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Failed to update memory");
  return res.json();
}

export async function synthesizeMemoryFromChats(): Promise<MemoryDetailResponse> {
  const res = await fetch(`${API_BASE}/settings/memory/synthesize`, {
    method: "POST",
    headers: getHeaders(),
  });
  if (!res.ok) throw new Error("Failed to synthesize memory from chat history");
  return res.json();
}

export async function deleteMemoryCategory(categoryId: string): Promise<MemoryDetailResponse> {
  const res = await fetch(`${API_BASE}/settings/memory/${categoryId}`, {
    method: "DELETE",
    headers: getHeaders(),
  });
  if (!res.ok) throw new Error("Failed to delete memory category");
  return res.json();
}





