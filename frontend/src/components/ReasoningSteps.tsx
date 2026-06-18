import { useEffect, useState } from "react";

import type { ReasoningStep } from "../types";

// Hiển thị "quá trình suy luận" do backend stream qua SSE (event `step`).
// Đang xử lý: mở sẵn, hiện từng bước hoàn tất kèm spinner cho bước kế tiếp.
// Xong: tự thu gọn thành "Đã suy luận qua N bước", bấm để xem lại.
export default function ReasoningSteps({
  steps,
  pending,
}: {
  steps: ReasoningStep[];
  pending?: boolean;
}) {
  const [open, setOpen] = useState(true);
  useEffect(() => {
    if (!pending) setOpen(false);
  }, [pending]);

  if (!steps.length && !pending) return null;

  const totalMs = steps.filter((s) => s.depth === 0).reduce((sum, s) => sum + s.ms, 0);
  const totalLabel = totalMs >= 1000 ? `${(totalMs / 1000).toFixed(1)}s` : `${totalMs}ms`;

  return (
    <div className="flex justify-start">
      <div className="w-full max-w-[85%] overflow-hidden rounded-2xl rounded-bl-md border border-slate-200 bg-slate-50/80 text-sm shadow-sm sm:max-w-2xl">
        <button
          onClick={() => setOpen((v) => !v)}
          className="flex w-full items-center gap-2 px-3.5 py-2 text-left text-slate-600 transition hover:bg-slate-100"
        >
          {pending ? (
            <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-slate-300 border-t-brand" />
          ) : (
            <span className="text-brand">✓</span>
          )}
          <span className="flex-1 font-medium">
            {pending ? "Đang suy luận…" : `Đã suy luận qua ${steps.length} bước`}
          </span>
          {!pending && <span className="text-xs text-slate-400">{totalLabel}</span>}
          <span className="text-xs text-slate-400">{open ? "▾" : "▸"}</span>
        </button>

        {open && (
          <ol className="space-y-1.5 border-t border-slate-200 px-3.5 py-2.5">
            {steps.map((s, i) => (
              <li
                key={i}
                className="flex items-center gap-2 text-slate-600"
                style={{ paddingLeft: s.depth * 14 }}
              >
                <span className="text-brand">✓</span>
                <span className="flex-1">{s.name}</span>
                <span className="text-xs text-slate-400">{s.ms}ms</span>
              </li>
            ))}
            {pending && (
              <li className="flex items-center gap-2 text-slate-400">
                <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-slate-300" />
                <span className="italic">đang xử lý…</span>
              </li>
            )}
          </ol>
        )}
      </div>
    </div>
  );
}
