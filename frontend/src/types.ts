// Mirrors the backend product-card contract (app/api/schemas.py).
// BE is the source of truth — keep these in sync. See docs/response-contract.md.

export interface Price {
  amount: number;
  currency: string;
  unit?: string | null; // "đêm" (hotel) | "vé" (attraction)
}

export interface CTA {
  label: string;
  action: "view_details" | "book";
  deep_link: string;
}

export interface RecommendationCard {
  entity_id: string;
  entity_type: "hotel" | "attraction";
  title: string;
  subtitle?: string | null;
  image_url?: string | null;
  images: string[];
  price?: Price | null;
  rating?: number | null;
  review_count?: number | null;
  star?: number | null;
  chips: string[];
  badges: string[];
  reasons: string[]; // "vì sao phù hợp"
  highlights: string[];
  cta: CTA[];
  score?: number | null;
}

export interface ChatResult {
  clarifying_question?: string | null;
  cards: RecommendationCard[];
}

export type ChatRole = "user" | "assistant";

export interface ChatMessage {
  id: string;
  role: ChatRole;
  text: string;
  cards?: RecommendationCard[];
  pending?: boolean;
}
