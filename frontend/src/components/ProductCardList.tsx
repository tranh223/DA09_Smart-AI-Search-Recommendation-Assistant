import type { RecommendationCard } from "../types";
import ProductCard from "./ProductCard";

export default function ProductCardList({ cards }: { cards: RecommendationCard[] }) {
  if (!cards.length) return null;
  return (
    <div className="mt-2 flex gap-3 overflow-x-auto pb-2">
      {cards.map((card) => (
        <ProductCard key={card.entity_id} card={card} />
      ))}
    </div>
  );
}
