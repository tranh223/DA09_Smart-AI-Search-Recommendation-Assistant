"""Pydantic schemas cho API — khớp với frontend/src/types.ts (BE là nguồn chuẩn)."""

from __future__ import annotations

from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    session_id: str
    user_id: str | None = None


class Price(BaseModel):
    amount: float
    currency: str = "VND"
    unit: str | None = None  # "đêm" (hotel)


class CTA(BaseModel):
    label: str
    action: str  # "view_details" | "book"
    deep_link: str


class RecommendationCard(BaseModel):
    entity_id: str
    entity_type: str  # "hotel" | "attraction"
    title: str
    subtitle: str | None = None
    image_url: str | None = None
    images: list[str] = []
    price: Price | None = None
    rating: float | None = None
    review_count: int | None = None
    star: int | None = None
    chips: list[str] = []
    badges: list[str] = []
    reasons: list[str] = []
    highlights: list[str] = []
    cta: list[CTA] = []
    score: float | None = None


class ChatResult(BaseModel):
    clarifying_question: str | None = None
    cards: list[RecommendationCard] = []
