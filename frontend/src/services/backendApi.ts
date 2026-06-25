// Client gọi backend AI assistant nội bộ (FastAPI).

const BACKEND_BASE_URL = (
  import.meta.env.VITE_BACKEND_BASE_URL ?? 'http://localhost:8000'
).replace(/\/$/, '');

// ── Streaming types ───────────────────────────────────────────────────────────

export type StreamEventType = 'status' | 'delta' | 'metadata' | 'done' | 'error';

export interface StreamEvent {
  type: StreamEventType;
  // status / error
  message?: string;
  // delta
  text?: string;
  // metadata (mirrors BackendChatData fields)
  intent?: string;
  recommendations?: Array<Record<string, unknown>>;
  sources?: Array<Record<string, unknown>>;
  next_suggestions?: string[];
  needs_clarification?: boolean;
  clarification_question?: string;
  explanation?: string;
  latency?: Record<string, unknown> | null;
}

export interface StreamCallbacks {
  /** Gọi khi backend gửi trạng thái xử lý (trước khi answer bắt đầu). */
  onStatus?: (message: string) => void;
  /** Gọi với từng token/chunk Markdown của answer. */
  onDelta?: (text: string) => void;
  /** Gọi một lần sau khi answer hoàn thành — truyền metadata đầy đủ. */
  onMetadata?: (data: BackendChatData) => void;
  /** Gọi khi stream kết thúc bình thường. */
  onDone?: () => void;
  /** Gọi khi có lỗi (network, server, parse). */
  onError?: (error: Error) => void;
}

export interface BackendChatRequest {
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
  token?: string | null,
): Promise<BackendChatData> {
  const headers: Record<string, string> = {
    accept: 'application/json',
    'Content-Type': 'application/json',
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(`${BACKEND_BASE_URL}/chat`, {
    method: 'POST',
    headers,
    body: JSON.stringify({
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

// ── Streaming chat ────────────────────────────────────────────────────────────

/**
 * Gọi POST /chat/stream và xử lý Server-Sent Events.
 *
 * Luồng event từ backend:
 *   status  → onStatus (nhiều lần, trong khi pipeline chạy)
 *   delta   → onDelta  (nhiều lần, từng token Markdown)
 *   metadata → onMetadata (một lần, sau khi answer xong)
 *   done    → onDone   (kết thúc)
 *   error   → onError
 */
export async function sendChatMessageStream(
  payload: BackendChatRequest,
  token: string | null | undefined,
  callbacks: StreamCallbacks,
): Promise<void> {
  const headers: Record<string, string> = {
    accept: 'text/event-stream',
    'Content-Type': 'application/json',
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  let res: Response;
  try {
    res = await fetch(`${BACKEND_BASE_URL}/chat/stream`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ rerank_options: {}, ...payload }),
    });
  } catch (err) {
    callbacks.onError?.(err instanceof Error ? err : new Error(String(err)));
    return;
  }

  if (!res.ok) {
    callbacks.onError?.(new Error(`HTTP ${res.status}: ${res.statusText}`));
    return;
  }

  const reader = res.body?.getReader();
  if (!reader) {
    callbacks.onError?.(new Error('Response body không đọc được'));
    return;
  }

  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // SSE có thể gửi nhiều dòng cùng lúc — xử lý từng dòng
      const lines = buffer.split('\n');
      buffer = lines.pop() ?? '';

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const rawData = line.slice(6).trim();
        if (!rawData) continue;

        let event: StreamEvent;
        try {
          event = JSON.parse(rawData) as StreamEvent;
        } catch {
          continue;
        }

        switch (event.type) {
          case 'status':
            callbacks.onStatus?.(event.message ?? '');
            break;

          case 'delta':
            callbacks.onDelta?.(event.text ?? '');
            break;

          case 'metadata':
            callbacks.onMetadata?.({
              intent: event.intent,
              recommendations: event.recommendations,
              sources: event.sources,
              next_suggestions: event.next_suggestions,
              needs_clarification: event.needs_clarification,
              clarification_question: event.clarification_question,
              explanation: event.explanation,
              latency: event.latency,
            });
            break;

          case 'done':
            callbacks.onDone?.();
            break;

          case 'error':
            callbacks.onError?.(new Error(event.message ?? 'Lỗi từ server'));
            break;
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}
