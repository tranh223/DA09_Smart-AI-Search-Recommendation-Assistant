import { useEffect, useRef } from "react";

import type { ChatMessage } from "../types";
import ClarifyingQuestion from "./ClarifyingQuestion";
import MessageBubble from "./MessageBubble";
import ProductCardList from "./ProductCardList";
import ReasoningSteps from "./ReasoningSteps";

export default function MessageList({ messages }: { messages: ChatMessage[] }) {
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="flex-1 space-y-3 overflow-y-auto bg-slate-50 p-4">
      {messages.map((m) => {
        if (m.role === "user") return <MessageBubble key={m.id} message={m} />;

        // Assistant: hiện quá trình suy luận (nếu có) phía trên nội dung trả lời.
        const hasCards = !!m.cards?.length;
        return (
          <div key={m.id} className="space-y-1.5">
            {(m.steps?.length || m.pending) && (
              <ReasoningSteps steps={m.steps ?? []} pending={m.pending} />
            )}
            {hasCards ? (
              <>
                <MessageBubble message={m} />
                <ProductCardList cards={m.cards!} />
              </>
            ) : (
              <ClarifyingQuestion message={m} />
            )}
          </div>
        );
      })}
      <div ref={endRef} />
    </div>
  );
}
