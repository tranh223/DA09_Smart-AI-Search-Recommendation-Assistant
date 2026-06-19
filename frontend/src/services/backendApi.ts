// Client gọi backend AI assistant nội bộ (FastAPI).

const BACKEND_BASE_URL = (
  import.meta.env.VITE_BACKEND_BASE_URL ?? 'http://localhost:8000'
).replace(/\/$/, '');

export interface BackendChatRequest {
  user_id: string;
  session_id: string;
  query: string;
  user_profile?: Record<string, unknown>;
  slots?: Record<string, unknown>;
  candidate_limit_per_source?: number;
  rerank_options?: Record<string, unknown>;
}

export interface BackendChatData {
  answer?: string;
  intent?: string;
  recommendations?: Array<Record<string, unknown>>;
  sources?: Array<Record<string, unknown>>;
  next_suggestions?: string[];
  needs_clarification?: boolean;
  clarification_question?: string;
  explanation?: string;
  latency?: Record<string, unknown> | null;
}

export interface BackendApiResponse<T> {
  success: boolean;
  request_id: string;
  data?: T;
  error?: {
    code: string;
    message: string;
  } | null;
  latency_ms?: number | null;
}

export class BackendApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'BackendApiError';
    this.status = status;
  }
}

export async function sendChatMessage(
  payload: BackendChatRequest,
): Promise<BackendChatData> {
  const res = await fetch(`${BACKEND_BASE_URL}/chat`, {
    method: 'POST',
    headers: {
      accept: 'application/json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      user_profile: {},
      slots: {},
      rerank_options: {},
      ...payload,
    }),
  });

  const body = (await res.json().catch(() => null)) as BackendApiResponse<BackendChatData> | null;
  if (!res.ok || !body?.success) {
    const message = body?.error?.message || body?.error?.code || res.statusText || 'Backend request failed';
    throw new BackendApiError(res.status, message);
  }

  return body.data ?? {};
}
