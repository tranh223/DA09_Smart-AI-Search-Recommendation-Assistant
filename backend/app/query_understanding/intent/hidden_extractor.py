import json
import os
from dataclasses import asdict, dataclass, field

from query_understanding.intent.extractor import (
    SEMANTIC_ITEMS_SCHEMA,
    LLMIntentExtractor,
)
from query_understanding.llm import OpenAIResponsesClient
from query_understanding.models.intent import SemanticPreferenceSet


SOURCE_ENUM = ["query", "history", "profile", "heuristic"]
PROFILE_SIGNAL_GROUPS = {
    "traveler_type": {"Explorer", "Comfort seeker", "Planer", "Spontaneous"},
    "long_term_budget_levels": {"low", "medium", "high"},
    "long_term_preference_habits": {
        "luxury",
        "comfort",
        "quiet",
        "privacy",
        "unique",
        "safety",
        "vibrant",
    },
}
SCALAR_SIGNAL_FIELDS = {"nationality", "age_group", "current_workplace"}


@dataclass(slots=True)
class HiddenProfileSignal:
    group: str
    value: str
    confidence: float
    evidence: str
    source: str


@dataclass(slots=True)
class HiddenScalarSignal:
    field: str
    value: str
    confidence: float
    evidence: str
    source: str


@dataclass(slots=True)
class HiddenIntentResult:
    semantic_preferences: SemanticPreferenceSet = field(default_factory=SemanticPreferenceSet)
    profile_signals: list[HiddenProfileSignal] = field(default_factory=list)
    scalar_signals: list[HiddenScalarSignal] = field(default_factory=list)


HIDDEN_INTENT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["semantic_preferences", "profile_signals", "scalar_signals"],
    "properties": {
        "semantic_preferences": SEMANTIC_ITEMS_SCHEMA,
        "profile_signals": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["group", "value", "confidence", "evidence", "source"],
                "properties": {
                    "group": {
                        "type": "string",
                        "enum": list(PROFILE_SIGNAL_GROUPS.keys()),
                    },
                    "value": {
                        "type": "string",
                    },
                    "confidence": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1,
                    },
                    "evidence": {"type": "string"},
                    "source": {
                        "type": "string",
                        "enum": SOURCE_ENUM,
                    },
                },
            },
        },
        "scalar_signals": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["field", "value", "confidence", "evidence", "source"],
                "properties": {
                    "field": {
                        "type": "string",
                        "enum": list(SCALAR_SIGNAL_FIELDS),
                    },
                    "value": {"type": "string"},
                    "confidence": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1,
                    },
                    "evidence": {"type": "string"},
                    "source": {
                        "type": "string",
                        "enum": SOURCE_ENUM,
                    },
                },
            },
        },
    },
}


HIDDEN_INTENT_INSTRUCTIONS = """
ROLE
You infer hidden hotel-profile intent for an OTA recommendation assistant.

TASK
Use the current query, recent conversation history, session_context,
long_term_profile, and tagremoved_profile to infer soft profile signals.
This component complements explicit extraction. It must not replace explicit facts.

OUTPUT GROUPS
1. semantic_preferences.items: hotel preference phrases with the same shape as
   the main intent extractor. These may go through semantic mapping and graph
   expansion.
2. profile_signals: direct inferred profile tags:
   - traveler_type: Explorer, Comfort seeker, Planer, Spontaneous
   - long_term_budget_levels: low, medium, high
   - long_term_preference_habits: luxury, comfort, quiet, privacy, unique,
     safety, vibrant
3. scalar_signals: nationality, age_group, current_workplace only when explicit
   evidence exists in query/history/profile.

STRICT SAFETY RULES
- Do not create destination, check_in, check_out, budget_min, or budget_max.
- You may infer budget level from long-term price range or direct wording, but
  never create a numeric price range.
- Do not infer far beyond evidence. Every signal needs evidence, confidence,
  and source: query, history, profile, or heuristic.
- Prefer no signal over a weak signal.
- If the user explicitly says cheap/low budget, never infer high.
- If explicit profile/history contradicts a heuristic, follow explicit evidence.
- Assistant history is context only. Treat it as user preference only when the
  user accepted or repeated it.

HEURISTIC CATALOG
- Foreign nationality: often has stronger budget; prefer hotels from 2 stars
  upward, exploration, and hotels near tourist/entertainment areas.
- Vietnamese user under 25: often lower budget and likes experiences; prefer
  homestay, hostel, budget hotels.
- Age 25-35: often more flexible budget; prefer hotels from 2 stars upward.
- Age above 35: often more stable budget; prefer 3-star upward, convenience,
  full services, and tourist-area convenience.
- Long-term price below 2 million VND: budget level low; budget hotels,
  homestay, hostel.
- Long-term price 2-5 million VND: budget level medium; hotels from 2 stars
  upward.
- Long-term price above 5 million VND: budget level high; hotels from 3 stars
  upward.
- Explorer: likes discovery/experience; boutique, homestay, tourist areas.
- Comfort seeker: likes comfort and amenities; 3-star upward, good services.
- Planer: searches early and carefully; quality service, amenities, good
  tourist access.
- Spontaneous: needs quick search; fast check-in/check-out and simple process.
- luxury: branded, premium, high-end hotels.
- comfort: good service, high ratings, many amenities.
- quiet: soundproofing, less central noise, nice view.
- privacy: soundproofing and couple-friendly hotels.
- unique: distinctive style; tree, bamboo, wooden, cabin, ocean, villa,
  mountain retreat.
- safety: clean and safe hotels.
- vibrant: bar, lively area, near city center.
- Solo: solo-friendly hotels.
- Tourist: exploration and tourist attractions nearby.
- Business: 3-star upward, good service, strong wifi, central location,
  well-rated staff, shuttle if supported.
- Family: family-friendly hotels and larger family rooms.
- Elderly: elevator and accessibility.
- Children: kids-friendly amenities.
- Couple: privacy, couple-friendly, soundproofing.
- Group: group-friendly, tourist-area convenience, easy transport.

SEMANTIC PREFERENCE RULES
- Only output catalog-friendly Vietnamese hotel preference phrases.
- target_field must be one of: session_amenities, session_hotel_types,
  session_trip_types, session_preference_habits, nearby_place.
- category must be one of: HOTEL_AMENITY, ROOM_AMENITY, HOTEL_TYPE,
  PLACE_TYPE, ROOM_VIEW, REVIEW_TAG, SUITABLE_FOR.
- priority must be hard or soft.
- Hidden semantic preferences should be soft unless the user clearly stated a
  hard requirement.
""".strip()


class HiddenIntentInsightExtractor:
    def __init__(
        self,
        model: str | None = None,
        temperature: float | None = None,
        min_confidence: float | None = None,
        enabled: bool | None = None,
    ) -> None:
        self.enabled = (
            enabled
            if enabled is not None
            else os.getenv("HIDDEN_INTENT_ENABLED", "true").strip().lower()
            in {"1", "true", "yes", "on"}
        )
        self.model = model or os.getenv("HIDDEN_INTENT_MODEL", "gpt-5.4-mini")
        self.temperature = (
            temperature
            if temperature is not None
            else float(os.getenv("HIDDEN_INTENT_TEMPERATURE", "0.1") or "0.1")
        )
        self.min_confidence = (
            min_confidence
            if min_confidence is not None
            else float(os.getenv("HIDDEN_INTENT_MIN_CONFIDENCE", "0.65") or "0.65")
        )
        self.client = OpenAIResponsesClient()
        self.last_trace: dict[str, object] = {}

    def extract(
        self,
        query: str,
        *,
        user_id: str | None = None,
        conversation_history: list[dict[str, str]] | None = None,
        session_context: dict[str, object] | None = None,
        long_term_profile: dict[str, object] | None = None,
        tagremoved_profile: dict[str, object] | None = None,
    ) -> HiddenIntentResult:
        if not self.enabled:
            self.last_trace = {
                "path": "disabled",
                "enabled": False,
                "model": self.model,
            }
            return HiddenIntentResult()

        normalized_history = LLMIntentExtractor._normalize_history(conversation_history)
        normalized_session_context = LLMIntentExtractor._normalize_session_context(session_context)
        input_payload = {
            "query": query,
            "conversation_history": normalized_history,
            "session_context": normalized_session_context,
            "long_term_profile": self._compact_profile(long_term_profile),
            "tagremoved_profile": self._compact_profile(tagremoved_profile),
            "min_confidence": self.min_confidence,
        }
        prompt_cache = self.client.build_prompt_cache_settings(
            component_name="qu_hidden_intent",
            model=self.model,
            instructions=HIDDEN_INTENT_INSTRUCTIONS,
            schema_name="hidden_intent_result",
            schema=HIDDEN_INTENT_SCHEMA,
            strict=False,
        )
        try:
            payload = self.client.create_structured_output(
                model=self.model,
                instructions=HIDDEN_INTENT_INSTRUCTIONS,
                input_text=json.dumps(input_payload, ensure_ascii=False),
                schema_name="hidden_intent_result",
                schema=HIDDEN_INTENT_SCHEMA,
                safety_identifier=user_id,
                strict=False,
                prompt_cache_key=prompt_cache.get("prompt_cache_key"),
                prompt_cache_retention=prompt_cache.get("prompt_cache_retention"),
                temperature=self.temperature,
            )
            result = self._normalize_result(payload)
            self.last_trace = {
                "path": "llm",
                "enabled": True,
                "model": self.model,
                "temperature": self.temperature,
                "min_confidence": self.min_confidence,
                "input": input_payload,
                "prompt_cache": prompt_cache,
                "response_meta": dict(self.client.last_response_meta),
                "payload": payload,
                "normalized": asdict(result),
            }
            return result
        except Exception as exc:
            self.last_trace = {
                "path": "error",
                "enabled": True,
                "model": self.model,
                "temperature": self.temperature,
                "min_confidence": self.min_confidence,
                "input": input_payload,
                "prompt_cache": prompt_cache,
                "error": f"{type(exc).__name__}: {exc}",
            }
            return HiddenIntentResult()

    def _normalize_result(self, payload: dict[str, object]) -> HiddenIntentResult:
        semantic_payload = payload.get("semantic_preferences")
        if not isinstance(semantic_payload, dict):
            semantic_payload = {}
        semantic_items = LLMIntentExtractor._normalize_semantic_items(
            semantic_payload.get("items", []) if isinstance(semantic_payload.get("items"), list) else []
        )

        profile_signals: list[HiddenProfileSignal] = []
        for raw in payload.get("profile_signals", []):
            if not isinstance(raw, dict):
                continue
            group = str(raw.get("group", "")).strip()
            value = str(raw.get("value", "")).strip()
            confidence = self._coerce_confidence(raw.get("confidence"))
            evidence = str(raw.get("evidence", "")).strip()
            source = str(raw.get("source", "")).strip()
            if group not in PROFILE_SIGNAL_GROUPS or value not in PROFILE_SIGNAL_GROUPS[group]:
                continue
            if source not in SOURCE_ENUM or confidence < self.min_confidence or not evidence:
                continue
            profile_signals.append(
                HiddenProfileSignal(
                    group=group,
                    value=value,
                    confidence=confidence,
                    evidence=evidence,
                    source=source,
                )
            )

        scalar_signals: list[HiddenScalarSignal] = []
        for raw in payload.get("scalar_signals", []):
            if not isinstance(raw, dict):
                continue
            field_name = str(raw.get("field", "")).strip()
            value = str(raw.get("value", "")).strip()
            confidence = self._coerce_confidence(raw.get("confidence"))
            evidence = str(raw.get("evidence", "")).strip()
            source = str(raw.get("source", "")).strip()
            if field_name not in SCALAR_SIGNAL_FIELDS or source not in SOURCE_ENUM:
                continue
            if confidence < self.min_confidence or not value or not evidence:
                continue
            scalar_signals.append(
                HiddenScalarSignal(
                    field=field_name,
                    value=value,
                    confidence=confidence,
                    evidence=evidence,
                    source=source,
                )
            )

        return HiddenIntentResult(
            semantic_preferences=SemanticPreferenceSet(items=semantic_items),
            profile_signals=profile_signals,
            scalar_signals=scalar_signals,
        )

    @staticmethod
    def _compact_profile(profile: dict[str, object] | None) -> dict[str, object]:
        if not isinstance(profile, dict):
            return {}
        return {
            key: value
            for key, value in profile.items()
            if value not in (None, "", {}, [])
        }

    @staticmethod
    def _coerce_confidence(value: object) -> float:
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return 0.0
