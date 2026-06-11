import { useChat } from "../hooks/useChat";
import ChatInput from "./ChatInput";
import MessageList from "./MessageList";

const SUGGESTIONS = [
  "Khách sạn ở Đà Nẵng có view biển",
  "Khách sạn 5 sao ở Nha Trang cho cặp đôi",
  "Khách sạn ở Hội An có hồ bơi",
];

export default function ChatWindow() {
  const { messages, loading, send } = useChat();

  return (
    <div className="flex h-full flex-col">
      {messages.length === 0 ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-5 p-6 text-center">
          <div className="grid h-16 w-16 place-items-center rounded-2xl bg-gradient-to-br from-blue-500 to-blue-600 text-3xl text-white shadow-lg">
            🧭
          </div>
          <p className="max-w-sm text-slate-600">
            Xin chào! Mình là trợ lý du lịch. Cho mình biết bạn muốn đi đâu — mình sẽ gợi ý
            khách sạn &amp; điểm tham quan phù hợp kèm lý do.
          </p>
          <div className="flex flex-wrap justify-center gap-2">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                onClick={() => send(s)}
                className="rounded-full border border-slate-200 bg-white px-3.5 py-2 text-sm text-slate-700 shadow-sm transition hover:border-brand hover:text-brand"
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      ) : (
        <MessageList messages={messages} />
      )}
      <ChatInput onSend={send} disabled={loading} />
    </div>
  );
}
