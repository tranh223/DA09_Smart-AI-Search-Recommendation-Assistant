import type { ChatMessage } from "../types";
import MessageBubble from "./MessageBubble";

// Assistant turns without product cards (clarifying questions / plain replies).
// Rendered with a subtle "question" accent.
export default function ClarifyingQuestion({ message }: { message: ChatMessage }) {
  if (!message.text) return <MessageBubble message={message} />;
  return (
    <div className="flex justify-start">
      <div className="flex max-w-[85%] items-start gap-2 rounded-2xl rounded-bl-md border border-blue-100 bg-white px-4 py-2.5 text-sm text-slate-800 shadow-sm sm:max-w-2xl">
        <span className="mt-0.5 text-brand">❓</span>
        <span>{message.text}</span>
      </div>
    </div>
  );
}
