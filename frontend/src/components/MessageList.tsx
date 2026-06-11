import { useEffect, useRef } from "react";

import type { ChatMessage } from "../types";
import ClarifyingQuestion from "./ClarifyingQuestion";
import MessageBubble from "./MessageBubble";
import ProductCardList from "./ProductCardList";

export default function MessageList({ messages }: { messages: ChatMessage[] }) {
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="flex-1 space-y-3 overflow-y-auto bg-slate-50 p-4">
      {messages.map((m) => {
        const hasCards = !!m.cards?.length;
        if (m.role === "assistant" && !hasCards) {
          return <ClarifyingQuestion key={m.id} message={m} />;
        }
        return (
          <div key={m.id} className="space-y-1">
            <MessageBubble message={m} />
            {hasCards && <ProductCardList cards={m.cards!} />}
          </div>
        );
      })}
      <div ref={endRef} />
    </div>
  );
}
