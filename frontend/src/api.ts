export type ApiStatus = "idle" | "loading" | "success" | "error";

const API_BASE = import.meta.env.VITE_TRADE_API_BASE ?? "/api";

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  const payload = await response.json().catch(() => ({}));

  if (!response.ok) {
    const message = payload?.detail ?? payload?.error ?? `HTTP ${response.status}`;
    throw new Error(typeof message === "string" ? message : JSON.stringify(message));
  }

  return payload as T;
}

export type TradeChatResult = {
  request_id?: string;
  final_answer?: string;
  evidence?: string[];
  sources?: Array<Record<string, unknown>>;
  next_steps?: string[];
  error?: string | null;
};

export type UploadDocumentResult = {
  uploaded: boolean;
  file_name: string;
  path: string;
  collection_name?: string;
  index_stats?: Record<string, number>;
};

export function runTradeChat(input: {
  user_input: string;
  tenant_id: string;
  user_id: string;
  department_ids?: string[];
  groups?: string[];
  clearance_level?: string;
  max_cost_units: number;
}) {
  return postJson<TradeChatResult>("/chat", {
    ...input,
    department_ids: input.department_ids ?? ["business"],
    groups: input.groups ?? [],
    clearance_level: input.clearance_level ?? "internal",
    roles: ["operator", "analyst"]
  });
}

export async function uploadTradeDocument(file: File) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("tenant_id", "company_internal");
  formData.append("user_id", "business_user");
  formData.append("visibility", "department");
  formData.append("sensitivity_level", "internal");

  const response = await fetch(`${API_BASE}/documents/upload`, {
    method: "POST",
    body: formData
  });
  const payload = await response.json().catch(() => ({}));

  if (!response.ok) {
    const message = payload?.detail ?? payload?.error ?? `HTTP ${response.status}`;
    throw new Error(typeof message === "string" ? message : JSON.stringify(message));
  }

  return payload as UploadDocumentResult;
}
