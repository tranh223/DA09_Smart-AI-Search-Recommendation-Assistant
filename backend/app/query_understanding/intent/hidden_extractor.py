import json
import os
import time
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
PROFILE_COMPACT_SCORE_MAP_FIELDS = (
    "traveler_type",
    "long_term_trip_types",
    "long_term_budget_levels",
    "long_term_preference_habits",
    "long_term_hotel_types",
    "long_term_room_views",
    "long_term_amenities",
)
PROFILE_COMPACT_NEGATIVE_FIELDS = (
    "avoid_hotel_types",
    "avoid_amenities",
    "avoid_preference_habits",
    "avoid_nearby_places",
    "avoid_locations",
)
MAX_SEMANTIC_PREFERENCES = 5
MAX_PROFILE_SIGNALS = 3


@dataclass(slots=True)
class HiddenProfileSignal:
    group: str
    value: str
    confidence: float
    evidence: str
    source: str


@dataclass(slots=True)
class HiddenIntentGateResult:
    should_extract: bool = False
    decision: str = "SKIP_NO_HIDDEN_VALUE"
    reason: str = ""
    evidence: str = ""


@dataclass(slots=True)
class HiddenIntentResult:
    semantic_preferences: SemanticPreferenceSet = field(default_factory=SemanticPreferenceSet)
    profile_signals: list[HiddenProfileSignal] = field(default_factory=list)


HIDDEN_INTENT_GATE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["should_extract", "decision", "reason", "evidence"],
    "properties": {
        "should_extract": {"type": "boolean"},
        "decision": {
            "type": "string",
            "enum": [
                "SKIP_SLOT_ONLY",
                "SKIP_FACTUAL_RAG",
                "SKIP_NO_HIDDEN_VALUE",
                "EXTRACT_HIDDEN_INTENT",
            ],
        },
        "reason": {"type": "string"},
        "evidence": {"type": "string"},
    },
}


HIDDEN_INTENT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["semantic_preferences", "profile_signals"],
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
    },
}


HIDDEN_INTENT_GATE_INSTRUCTIONS = """
ROLE
You are a gate for hidden profile intent extraction in an OTA recommendation assistant.

ASSUMPTION
The main guardrail already filtered the request. Treat current_query as OTA-related.
Do not classify greetings, assistant help, or out-of-scope topics here.

TASK
Decide whether the hidden intent extractor should run for current_query.
Think internally, but return only a concise decision, reason, and evidence.

CURRENT QUERY FIRST
- current_query is the primary and required evidence source.
- conversation_history, conversation_summary, session_context, long_term_profile,
  and tagremoved_profile are context only. Use them to resolve references,
  detect duplicates, and avoid conflicts. Do not use them as the sole reason to
  extract.
- Do not pass extraction for a tag/preference that appears only in past turns,
  assistant answers, session_context, or long_term_profile.

RETURN EXTRACT_HIDDEN_INTENT ONLY WHEN
- current_query introduces new useful preference, travel purpose, traveler type,
  hotel style, room view, comfort/safety/privacy/quiet/luxury/vibrant intent, or
  another soft profile signal worth retaining.
- current_query changes the travel objective in a way that may affect profile
  signals, such as business trip, family with children, couple trip, relaxation,
  exploration, privacy, quietness, safety, or unique stay.
- current_query repeats or strengthens an existing profile signal clearly enough
  to be counted as fresh evidence.

RETURN SKIP_SLOT_ONLY WHEN
- current_query only fills structured slots such as destination, dates,
  number_of_guests, budget amount/range/level, or a short answer to a previous
  clarification, without soft preference/profile meaning.

RETURN SKIP_FACTUAL_RAG WHEN
- current_query asks factual information about a hotel, policy, check-in time,
  amenity availability, address, or other RAG-style information, without new
  soft profile preference.

RETURN SKIP_NO_HIDDEN_VALUE WHEN
- explicit extraction is enough and there is no additional hidden profile value.
- the signal already exists in summary/history/session/profile and current_query
  does not add fresh evidence or strengthen it.

STRICT RULES
- Prefer skip over weak inference.
- Do not pass extraction just because old profile has tags.
- Do not pass extraction just because a destination changed unless current_query
  also contains a new preference, persona, trip purpose, or hotel style.
- Do not expose chain-of-thought. Keep reason/evidence short.
""".strip()


HIDDEN_INTENT_INSTRUCTIONS = """
ROLE
Infer hidden hotel-profile signals for an OTA recommendation assistant.

PRIMARY RULE
- current_query is mandatory evidence for every new output.
- history, conversation_summary, session_context, long_term_profile, and
  tagremoved_profile are context only. Use them to resolve references, dedupe,
  and avoid conflicts.
- Never output a signal based only on old profile, removed tags, assistant
  answers, or past turns.

OUTPUT GROUPS
1. semantic_preferences.items: soft hotel preference phrases in the same shape
   and style as the explicit intent extractor.
2. profile_signals: direct soft profile labels:
   - traveler_type: Explorer, Comfort seeker, Planer, Spontaneous
   - long_term_budget_levels: low, medium, high
   - long_term_preference_habits: luxury, comfort, quiet, privacy, unique, safety, vibrant

WHEN TO OUTPUT
Output only when current_query introduces or clearly strengthens:
- trip purpose or traveler type;
- hotel style/type;
- room view;
- service, cleanliness, quiet, privacy, safety, luxury, comfort, unique, or vibrant intent;
- work/business, family, couple, group, elderly, or children-related needs.

STRICT RULES
- Do not create destination, check_in, check_out, budget_min, or budget_max.
- You may infer budget level from direct wording or long-term price, but never
  create a numeric price range.
- Every signal must include evidence, confidence, and source.
- Evidence must be from current_query or a very close paraphrase.
- Prefer no output over weak inference.
- Output at most 5 semantic_preferences and at most 3 profile_signals.
- Do not repeat a tag already present in profile/session unless current_query
  states or strengthens it.
- If the user explicitly says cheap/low budget, never infer high.
- Follow explicit evidence over heuristics.
- Do not output paid/fee amenities unless current_query explicitly asks for paid/fee service.
- Never output "WiFi tính phí" unless the user says paid/fee/charged internet.

HEURISTICS
- Price <2m VND: low. Price 2-5m: medium. Price >5m: high.
- Explorer: discovery, experience, boutique/homestay/tourist areas.
- Comfort seeker: comfort, amenities, good service, higher-rated hotels.
- Planer: careful planning, quality service, convenient tourist access.
- Spontaneous: quick search, fast check-in/out, simple process.
- luxury/comfort/quiet/privacy/unique/safety/vibrant keep their literal meanings.
- Business/work travel may imply: business-suitable hotel, central/convenient
  location, good service, work-friendly facilities, and stable/free WiFi.
- Family/children/elderly/couple/group may imply the corresponding suitability
  and practical hotel needs.

SEMANTIC STYLE
- Output short Vietnamese phrases close to current_query wording.
- Do not output final catalog tags unless the user said that exact concept.
- target_field must be one of: session_amenities, session_hotel_types,
  session_trip_types, session_preference_habits, nearby_place.
- category must be one of: HOTEL_AMENITY, ROOM_AMENITY, HOTEL_TYPE,
  PLACE_TYPE, ROOM_VIEW, REVIEW_TAG, SUITABLE_FOR.
- Hidden items are soft unless the user states a hard requirement.

MAPPING STYLE
- Trip purpose/persona: session_trip_types + SUITABLE_FOR.
- Generic "view đẹp": text="hướng nhìn từ phòng đẹp",
  target_field=session_preference_habits, category=REVIEW_TAG.
- Explicit view type: category=ROOM_VIEW, target_field=session_preference_habits.
- Service/clean/quiet/privacy/safety: session_preference_habits + REVIEW_TAG.
- Concrete amenities only: session_amenities + HOTEL_AMENITY/ROOM_AMENITY.
- Business location: text="trung tâm thành phố", target_field=nearby_place,
  category=PLACE_TYPE.
- Business WiFi: text="WiFi miễn phí hoặc kết nối internet ổn định phục vụ công việc",
  target_field=session_amenities, category=HOTEL_AMENITY.
- Generic "nhiều tiện nghi" should be omitted unless current_query explicitly says it.
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
        conversation_summary: str | None = None,
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
        normalized_summary = self._normalize_summary(conversation_summary)
        normalized_session_context = LLMIntentExtractor._normalize_session_context(session_context)

        gate_payload = {
            "query": query,
            "conversation_history": normalized_history,
            "conversation_summary": normalized_summary,
            "session_context": normalized_session_context,
        }
        gate_prompt_cache = self.client.build_prompt_cache_settings(
            component_name="qu_hidden_intent_gate",
            model=self.model,
            instructions=HIDDEN_INTENT_GATE_INSTRUCTIONS,
            schema_name="hidden_intent_gate_result",
            schema=HIDDEN_INTENT_GATE_SCHEMA,
            strict=False,
        )
        gate_start = time.perf_counter()
        try:
            gate_raw = self.client.create_structured_output(
                model=self.model,
                instructions=HIDDEN_INTENT_GATE_INSTRUCTIONS,
                input_text=json.dumps(gate_payload, ensure_ascii=False),
                schema_name="hidden_intent_gate_result",
                schema=HIDDEN_INTENT_GATE_SCHEMA,
                safety_identifier=user_id,
                strict=False,
                prompt_cache_key=gate_prompt_cache.get("prompt_cache_key"),
                prompt_cache_retention=gate_prompt_cache.get("prompt_cache_retention"),
                temperature=self.temperature,
            )
            gate_result = self._normalize_gate_result(gate_raw)
            gate_trace = {
                "path": "llm",
                "model": self.model,
                "temperature": self.temperature,
                "input": gate_payload,
                "prompt_cache": gate_prompt_cache,
                "response_meta": dict(self.client.last_response_meta),
                "payload": gate_raw,
                "normalized": asdict(gate_result),
                "latency_ms": self._elapsed_ms(gate_start),
            }
        except Exception as exc:
            self.last_trace = {
                "path": "gate_error",
                "enabled": True,
                "model": self.model,
                "temperature": self.temperature,
                "gate": {
                    "path": "error",
                    "input": gate_payload,
                    "prompt_cache": gate_prompt_cache,
                    "error": f"{type(exc).__name__}: {exc}",
                    "latency_ms": self._elapsed_ms(gate_start),
                },
                "error": f"{type(exc).__name__}: {exc}",
            }
            return HiddenIntentResult()

        if not gate_result.should_extract:
            self.last_trace = {
                "path": "skipped_by_llm_gate",
                "enabled": True,
                "model": self.model,
                "temperature": self.temperature,
                "reason": gate_result.reason,
                "gate_decision": gate_result.decision,
                "gate_evidence": gate_result.evidence,
                "query": query,
                "gate": gate_trace,
                "response_meta": gate_trace.get("response_meta", {}),
            }
            return HiddenIntentResult()

        input_payload = {
            "query": query,
            "conversation_history": normalized_history,
            "conversation_summary": normalized_summary,
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
        extract_start = time.perf_counter()
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
                "gate_decision": gate_result.decision,
                "gate_reason": gate_result.reason,
                "gate_evidence": gate_result.evidence,
                "gate": gate_trace,
                "input": input_payload,
                "prompt_cache": prompt_cache,
                "response_meta": dict(self.client.last_response_meta),
                "payload": payload,
                "normalized": asdict(result),
                "extraction_latency_ms": self._elapsed_ms(extract_start),
            }
            return result
        except Exception as exc:
            self.last_trace = {
                "path": "error",
                "enabled": True,
                "model": self.model,
                "temperature": self.temperature,
                "min_confidence": self.min_confidence,
                "gate_decision": gate_result.decision,
                "gate_reason": gate_result.reason,
                "gate_evidence": gate_result.evidence,
                "gate": gate_trace,
                "input": input_payload,
                "prompt_cache": prompt_cache,
                "error": f"{type(exc).__name__}: {exc}",
                "extraction_latency_ms": self._elapsed_ms(extract_start),
            }
            return HiddenIntentResult()

    @staticmethod
    def _normalize_gate_result(payload: dict[str, object]) -> HiddenIntentGateResult:
        if not isinstance(payload, dict):
            payload = {}
        decision = str(payload.get("decision") or "").strip()
        allowed_decisions = {
            "SKIP_SLOT_ONLY",
            "SKIP_FACTUAL_RAG",
            "SKIP_NO_HIDDEN_VALUE",
            "EXTRACT_HIDDEN_INTENT",
        }
        if decision not in allowed_decisions:
            decision = "SKIP_NO_HIDDEN_VALUE"
        should_extract = bool(payload.get("should_extract")) and decision == "EXTRACT_HIDDEN_INTENT"
        if should_extract:
            decision = "EXTRACT_HIDDEN_INTENT"
        elif decision == "EXTRACT_HIDDEN_INTENT":
            decision = "SKIP_NO_HIDDEN_VALUE"
        return HiddenIntentGateResult(
            should_extract=should_extract,
            decision=decision,
            reason=str(payload.get("reason") or "").strip(),
            evidence=str(payload.get("evidence") or "").strip(),
        )

    def _normalize_result(self, payload: dict[str, object]) -> HiddenIntentResult:
        semantic_payload = payload.get("semantic_preferences")
        if not isinstance(semantic_payload, dict):
            semantic_payload = {}
        semantic_items = LLMIntentExtractor._normalize_semantic_items(
            semantic_payload.get("items", []) if isinstance(semantic_payload.get("items"), list) else []
        )[:MAX_SEMANTIC_PREFERENCES]

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

        return HiddenIntentResult(
            semantic_preferences=SemanticPreferenceSet(items=semantic_items),
            profile_signals=profile_signals[:MAX_PROFILE_SIGNALS],
        )

    @classmethod
    def _compact_profile(cls, profile: dict[str, object] | None) -> dict[str, object]:
        if not isinstance(profile, dict):
            return {}
        top_n = cls._profile_compact_top_n()
        compact: dict[str, object] = {}

        is_enough = profile.get("is_enough")
        if is_enough not in (None, "", {}, []):
            compact["is_enough"] = is_enough

        price_range = profile.get("long_term_price_range")
        if isinstance(price_range, dict):
            compact_price = {
                key: price_range.get(key)
                for key in ("min", "max", "currency")
                if price_range.get(key) not in (None, "", {}, [])
            }
            if compact_price:
                compact["long_term_price_range"] = compact_price

        for field_name in PROFILE_COMPACT_SCORE_MAP_FIELDS:
            top_items = cls._compact_score_map(profile.get(field_name), top_n=top_n)
            if top_items:
                compact[field_name] = top_items

        negative_preferences = profile.get("long_term_negative_preferences")
        if isinstance(negative_preferences, dict):
            compact_negative: dict[str, object] = {}
            for field_name in PROFILE_COMPACT_NEGATIVE_FIELDS:
                top_items = cls._compact_score_map(negative_preferences.get(field_name), top_n=top_n)
                if top_items:
                    compact_negative[field_name] = top_items
            if compact_negative:
                compact["long_term_negative_preferences"] = compact_negative

        return compact

    @staticmethod
    def _profile_compact_top_n() -> int:
        try:
            return max(1, int(os.getenv("HIDDEN_INTENT_PROFILE_TOP_N", "5") or "5"))
        except (TypeError, ValueError):
            return 5

    @classmethod
    def _compact_score_map(cls, value: object, *, top_n: int) -> list[dict[str, object]]:
        if not isinstance(value, dict):
            return []
        items: list[dict[str, object]] = []
        for tag, raw_payload in value.items():
            tag_text = str(tag).strip()
            if not tag_text:
                continue
            if isinstance(raw_payload, dict):
                item: dict[str, object] = {"tag": tag_text}
                count = cls._coerce_count(raw_payload.get("count"))
                if count is not None:
                    item["count"] = count
                last_interaction = raw_payload.get("last_interaction")
                if last_interaction not in (None, "", {}, []):
                    item["last_interaction"] = str(last_interaction)
                for optional_key in ("score", "confidence"):
                    optional_value = raw_payload.get(optional_key)
                    if optional_value not in (None, "", {}, []):
                        item[optional_key] = optional_value
                items.append(item)
            elif raw_payload not in (None, "", {}, []):
                items.append({"tag": tag_text, "value": raw_payload})
        items.sort(
            key=lambda item: (
                cls._coerce_count(item.get("count")) or 0,
                str(item.get("last_interaction") or ""),
                str(item.get("tag") or ""),
            ),
            reverse=True,
        )
        return items[:top_n]

    @staticmethod
    def _coerce_count(value: object) -> int | None:
        try:
            return int(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _coerce_confidence(value: object) -> float:
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _normalize_summary(conversation_summary: str | None) -> str:
        return " ".join(str(conversation_summary or "").strip().split())

    @staticmethod
    def _elapsed_ms(start: float) -> float:
        return round((time.perf_counter() - start) * 1000, 3)
