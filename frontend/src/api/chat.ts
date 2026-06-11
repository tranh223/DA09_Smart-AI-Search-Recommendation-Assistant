// SSE client for POST /chat. EventSource only supports GET, so we POST with fetch and
// parse the Server-Sent Events stream manually: token* → result → done.

import type { ChatResult } from "../types";

const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? "/api";

export interface ChatStreamHandlers {
  onToken: (text: string) => void;
  onResult: (result: ChatResult) => void;
  onDone: () => void;
  onError: (err: unknown) => void;
}

export interface ChatRequestBody {
  message: string;
  session_id: string;
  user_id?: string | null;
}

export async function streamChat(body: ChatRequestBody, h: ChatStreamHandlers): Promise<void> {
  try {
    const res = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let idx: number;
      while ((idx = buffer.indexOf("\n\n")) >= 0) {
        const rawEvent = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 2);
        dispatch(rawEvent, h);
      }
    }
    h.onDone();
  } catch (err) {
    h.onError(err);
  }
}

function dispatch(raw: string, h: ChatStreamHandlers): void {
  let event = "message";
  let data = "";
  for (const line of raw.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) data += line.slice(5).trim();
  }
  if (!data) return;

  const payload = JSON.parse(data);
  if (event === "token") h.onToken(payload.text ?? "");
  else if (event === "result") h.onResult(payload as ChatResult);
  // "done" is signaled by the stream ending (onDone in streamChat).
}
