import { useCallback, useRef, useState } from "react";

import { streamChat } from "../api/chat";
import type { ChatMessage } from "../types";

function uid(): string {
  return Math.random().toString(36).slice(2);
}

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const sessionId = useRef(uid());

  const update = (id: string, patch: Partial<ChatMessage>) =>
    setMessages((m) => m.map((x) => (x.id === id ? { ...x, ...patch } : x)));

  const send = useCallback(async (text: string) => {
    if (!text.trim() || loading) return;
    const botId = uid();
    setMessages((m) => [
      ...m,
      { id: uid(), role: "user", text },
      { id: botId, role: "assistant", text: "", steps: [], pending: true },
    ]);
    setLoading(true);

    let acc = "";
    await streamChat(
      {
        message: text,
        session_id: sessionId.current,
        user_id: localStorage.getItem("user_id"),
      },
      {
        onStep: (s) =>
          setMessages((m) =>
            m.map((x) => (x.id === botId ? { ...x, steps: [...(x.steps ?? []), s] } : x)),
          ),
        onToken: (t) => {
          acc += t;
          update(botId, { text: acc });
        },
        onResult: (r) => {
          update(botId, {
            cards: r.cards,
            text: acc.trim() || r.clarifying_question || "",
          });
        },
        onDone: () => {
          update(botId, { pending: false });
          setLoading(false);
        },
        onError: () => {
          update(botId, { pending: false, text: "Xin lỗi, có lỗi kết nối tới server." });
          setLoading(false);
        },
      },
    );
  }, [loading]);

  return { messages, loading, send };
}
