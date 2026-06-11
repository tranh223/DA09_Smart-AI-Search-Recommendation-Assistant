import type { RecommendationCard } from "../types";

function formatVnd(n: number): string {
  return n.toLocaleString("vi-VN");
}

function formatCount(n?: number | null): string {
  if (!n) return "";
  return n >= 1000 ? `${(n / 1000).toFixed(1)}k` : `${n}`;
}

export default function ProductCard({ card }: { card: RecommendationCard }) {
  return (
    <div className="w-72 shrink-0 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm transition hover:shadow-md">
      <div className="relative h-36 w-full bg-slate-100">
        {card.image_url && (
          <img src={card.image_url} alt={card.title} className="h-full w-full object-cover" loading="lazy" />
        )}
        <div className="absolute left-2 top-2 flex flex-wrap gap-1">
          {card.badges.map((b) => (
            <span key={b} className="rounded-full bg-brand px-2 py-0.5 text-[11px] font-medium text-white shadow">
              {b}
            </span>
          ))}
        </div>
        {card.star ? (
          <span className="absolute right-2 top-2 rounded-md bg-black/60 px-1.5 py-0.5 text-[11px] text-white">
            {"★".repeat(card.star)}
          </span>
        ) : null}
      </div>

      <div className="space-y-2 p-3">
        <div>
          <h3 className="line-clamp-1 font-semibold text-slate-800">{card.title}</h3>
          {card.subtitle && <p className="text-xs text-slate-500">{card.subtitle}</p>}
        </div>

        <div className="flex items-center justify-between">
          {card.rating ? (
            <span className="text-sm text-amber-600">
              ⭐ {card.rating}
              <span className="text-slate-400"> ({formatCount(card.review_count)})</span>
            </span>
          ) : <span />}
          {card.price && (
            <span className="text-sm font-semibold text-slate-800">
              {formatVnd(card.price.amount)} {card.price.currency}
              {card.price.unit ? <span className="font-normal text-slate-500">/{card.price.unit}</span> : null}
            </span>
          )}
        </div>

        {card.chips.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {card.chips.map((c) => (
              <span key={c} className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] text-slate-600">
                {c}
              </span>
            ))}
          </div>
        )}

        {card.reasons.length > 0 && (
          <div className="rounded-lg bg-blue-50 p-2">
            <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-brand-dark">
              Vì sao phù hợp
            </p>
            <ul className="space-y-0.5">
              {card.reasons.map((r, i) => (
                <li key={i} className="flex gap-1 text-xs text-slate-700">
                  <span className="text-brand">✓</span>
                  <span>{r}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="flex gap-2 pt-1">
          {card.cta.map((cta) => (
            <a
              key={cta.action}
              href={cta.deep_link}
              onClick={(e) => e.preventDefault()}
              className={
                cta.action === "book"
                  ? "flex-1 rounded-lg bg-gradient-to-r from-blue-500 to-blue-600 px-3 py-1.5 text-center text-sm font-medium text-white shadow-sm transition hover:opacity-90"
                  : "flex-1 rounded-lg border border-slate-200 px-3 py-1.5 text-center text-sm text-slate-700 transition hover:bg-slate-50"
              }
            >
              {cta.label}
            </a>
          ))}
        </div>
      </div>
    </div>
  );
}
