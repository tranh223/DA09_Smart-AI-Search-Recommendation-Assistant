import json
import os
import unicodedata
from datetime import date

from query_understanding.llm import OpenAIResponsesClient
from query_understanding.models.intent import (
    ConstraintSet,
    EntitySet,
    IntentResult,
    SemanticPreferenceItem,
    SemanticPreferenceSet,
)


TARGET_FIELD_ENUM = [
    "session_amenities",
    "session_hotel_types",
    "session_trip_types",
    "session_preference_habits",
    "nearby_place",
]

CATEGORY_ENUM = [
    "HOTEL_AMENITY",
    "ROOM_AMENITY",
    "HOTEL_TYPE",
    "PLACE_TYPE",
    "ROOM_VIEW",
    "REVIEW_TAG",
    "SUITABLE_FOR",
]

PRIORITY_ENUM = ["hard", "soft"]

TRIP_TYPE_ENUM = [
    "Nhóm du khách",
    "Cặp đôi",
    "Khách du lịch một mình",
    "Gia đình có trẻ nhỏ",
    "Gia đình có thanh thiếu niên",
    "Khách đi công tác",
]

SEMANTIC_ITEMS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["items"],
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["text", "target_field", "category", "priority"],
                "properties": {
                    "text": {"type": "string"},
                    "target_field": {
                        "type": "string",
                        "enum": TARGET_FIELD_ENUM,
                    },
                    "category": {
                        "type": "string",
                        "enum": CATEGORY_ENUM,
                    },
                    "priority": {
                        "type": "string",
                        "enum": PRIORITY_ENUM,
                    },
                },
            },
        }
    },
}

INTENT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["entities", "semantic_preferences", "constraints"],
    "properties": {
        "entities": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "destination": {"type": ["string", "null"]},
                "hotel_name": {"type": ["string", "null"]},
                "budget_min": {"type": ["number", "null"]},
                "budget_max": {"type": ["number", "null"]},
                "budget_scope": {
                    "type": ["string", "null"],
                    "enum": [None, "hotel_price", "trip_total"],
                },
                "trip_type": {
                    "type": ["string", "null"],
                    "enum": [None, *TRIP_TYPE_ENUM],
                },
                "nearby_place": {"type": ["string", "null"]},
                "number_of_guests": {"type": ["integer", "null"]},
                "check_in": {"type": ["string", "null"]},
                "check_out": {"type": ["string", "null"]},
            },
        },
        "semantic_preferences": SEMANTIC_ITEMS_SCHEMA,
        "constraints": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "budget_level": {
                    "type": ["string", "null"],
                    "enum": [None, "low", "medium", "high"],
                },
                "location_hint": {"type": ["string", "null"]},
                "note_amenities": {
                    "type": ["string", "null"],
                    "enum": [None, "max"],
                },
            },
        },
    },
}

INTENT_INSTRUCTIONS = """
ROLE
You are the production intent feature extraction engine for an OTA hotel assistant.

TASK
Given the current user query and the current_date, extract:
1. structured hotel facts
2. semantic preference phrases
3. unresolved constraint notes

CONTEXT
- This component only extracts information.
- Search planning, routing, retrieval, ranking, and recommendation execution are handled elsewhere.
- Intent extraction receives the current user query, the active session_context, and up to 10 recent conversation turns.
- Use session_context as the source of truth for structured facts already collected in this session.
- Use conversation_history only to resolve follow-up references, ellipsis, corrections, and carried-over facts not present in session_context.
- The current user query has highest priority. Do not invent facts from history unless the current query clearly depends on them.
- Assistant answers in history are context only; do not treat assistant suggestions as user preferences unless the user accepted or repeated them.

STRICT OUTPUT POLICY
- Do not output normalized hotel tags, normalized amenities, or normalized hotel types.
- Do not decide search intent, planner task, router branch, retrieval source, or execution plan.
- Only return values directly supported by the current query, except structured trip facts carried over from session_context or conversation_history for a clear follow-up.
- When the current query is a follow-up that adds budget, preferences, traveler type, dates, or constraints, preserve prior structured trip facts from session_context first, then conversation_history, such as destination, check_in, check_out, number_of_guests, and nearby_place unless the current query contradicts them.
- If uncertain, omit the field instead of guessing.
- Use sparse output inside entities and constraints: include only fields that have non-null values.
- Still return the top-level groups `entities`, `constraints`, and `semantic_preferences`.

STRUCTURED FACT RULES
- Extract destination when the city, area, or place is explicit.
- If destination was explicit in session_context or conversation_history and the current query is a follow-up, carry it over.
- Extract hotel_name only when a specific property is referenced.
- Extract nearby_place only when the location anchor is explicit and concrete enough to use directly.
- Extract number_of_guests when explicit.
- Extract check_in and check_out in YYYY-MM-DD format only.
- If check_in/check_out were explicit in session_context or conversation_history and the current query is a follow-up, carry them over.
- Extract budget_min and budget_max as VND numbers when money is clearly mentioned.
- Extract constraints.budget_level as `low`, `medium`, or `high` when the query gives a hotel budget amount or clear budget wording.
- Use `low` for budget-sensitive, cheap, affordable, low-cost, or clearly low hotel price requests. Use `high` for luxury, premium, high-end, expensive requests. Use `medium` for middle-range neutral budgets. Use null only when budget information is absent or insufficient.
- Extract constraints.note_amenities as `max` when the user explicitly asks for broad amenity completeness such as many amenities, full amenities, maximum amenities, or fully equipped hotel amenities.
- If constraints.note_amenities is `max`, do not create a semantic_preferences item for that generic amenity-completeness request. Only create semantic amenity items for concrete amenities such as BBQ, pool, breakfast, spa, wifi, language support, balcony, or kids club.
- Do not set constraints.note_amenities=`max` for concrete amenities such as BBQ, outdoor cooking, pool, breakfast, spa, wifi, language support, balcony, or kids club.
- Keep budget_min, budget_max, budget_scope, trip_type, and number_of_guests only under entities. Do not duplicate those fields under constraints.
- constraints must contain only budget_level, location_hint, and note_amenities.
- Set budget_scope to:
  - hotel_price: hotel price, room price, hotel budget, price per night
  - trip_total: total trip budget, vacation budget, total travel spending
  - null: if scope is unclear
- Extract trip_type only when it is explicit enough to be safely structured.
- When extracting trip_type, output exactly one of these Vietnamese enum values and never output English labels: Nhóm du khách, Cặp đôi, Khách du lịch một mình, Gia đình có trẻ nhỏ, Gia đình có thanh thiếu niên, Khách đi công tác.

SEMANTIC PREFERENCE RULES
- Put descriptive hotel preferences, soft requirements, vibes, room preferences, location styles, and suitability requests into semantic_preferences.items.
- semantic_preferences.items must represent preferences explicitly mentioned in the current user query only.
- If the current query is a follow-up, extract only the new or explicitly repeated preferences from that follow-up.
- Write each semantic phrase as catalog-friendly Vietnamese hotel vocabulary that is specific enough for semantic mapping.
- Never copy vague user wording directly when a stronger hotel-catalog phrase is available.
- Each semantic item must include:
  - text: a Vietnamese semantic phrase rewritten for embedding-based mapping against hotel tag catalog text
  - target_field: exactly one of the allowed target fields
  - category: exactly one taxonomy category
  - priority: hard or soft
- target_field must be selected only from:
  - session_amenities
  - session_hotel_types
  - session_trip_types
  - session_preference_habits
  - nearby_place
- category must be selected only from:
  - HOTEL_AMENITY
  - ROOM_AMENITY
  - HOTEL_TYPE
  - PLACE_TYPE
  - ROOM_VIEW
  - REVIEW_TAG
  - SUITABLE_FOR

TARGET FIELD GUIDANCE
- session_amenities: amenities, facilities, hotel services, guest support capabilities, language support such as `hỗ trợ tiếng Ý`, pool, kids club, breakfast, balcony, spa, wifi
- session_hotel_types: resort, villa, homestay, hostel, hotel, boutique, bungalow
- session_trip_types: suitability such as nhóm du khách, cặp đôi, khách du lịch một mình, gia đình có trẻ nhỏ, gia đình có thanh thiếu niên, khách đi công tác. For this field, output text exactly as one Vietnamese enum value: Nhóm du khách, Cặp đôi, Khách du lịch một mình, Gia đình có trẻ nhỏ, Gia đình có thanh thiếu niên, Khách đi công tác.
- session_preference_habits: review-like qualities, room views, atmosphere, lifestyle, location style, aesthetics, convenience preferences
- nearby_place: place-oriented location anchors. Output a place type noun phrase, not a location-relation sentence. Prefer phrases like `trung tâm thành phố`, `bãi biển`, `phố cổ`, `chợ`, `sân bay`, `khu vực núi`, `bệnh viện và cơ sở y tế`.

CATEGORY GUIDANCE
- HOTEL_AMENITY: hotel-level facilities and services
- ROOM_AMENITY: room-level facilities and in-room features
- HOTEL_TYPE: lodging type
- PLACE_TYPE: location style or place-area preference
- ROOM_VIEW: desired room view type when the view itself is explicit
- REVIEW_TAG: experiential, vibe, quality, generic view-quality, or review-like preference
- SUITABLE_FOR: suitability for a traveler type or group

IMPORTANT DISTINCTIONS
- Keep structured facts separate from semantic items.
- Do not convert semantic items into internal normalized enums.
- If a phrase is too vague to map confidently, omit that semantic item.
- Prefer catalog-friendly Vietnamese hotel wording: include the hotel object, guest context, and concrete attribute when user wording is too short.
- A good semantic phrase should be specific enough to map against tag text formatted as `Tag + Category + Description`.
- Use the examples below as patterns, not as a closed list. Generalize the same style to similar user wording.
- If the user combines service and cleanliness in one phrase, such as `dịch vụ sạch sẽ`, extract both the service-quality semantic item and the cleanliness semantic item. Do not collapse cleanliness into service.
- For generic nice-view requests like `view đẹp`, output `hướng nhìn từ phòng đẹp` with target_field=session_preference_habits and category=REVIEW_TAG. Do not use ROOM_VIEW unless the user names a concrete view type.
- Use ROOM_VIEW only when the requested view is explicit, such as biển, núi, thành phố, sông, hồ, or vườn.
- For generic amenity requests like `nhiều tiện nghi`, set constraints.note_amenities=`max` and do not add a semantic item for that generic request.
- For family-friendly requests like `phù hợp với gia đình`, describe suitability in a way that is semantically close to family-with-children hotel wording.

FORBIDDEN RAW SEMANTIC OUTPUTS
- Do not output text=`nằm ở trung tâm`; output text=`trung tâm thành phố`, target_field=nearby_place, category=PLACE_TYPE.
- Do not output text=`có nhiều tiện ích` or text=`nhiều tiện ích`; set constraints.note_amenities=`max` and omit that semantic item.
- Do not output text=`dịch vụ tốt`; output text=`dịch vụ khách sạn tốt, nhân viên phục vụ chu đáo, hỗ trợ khách hiệu quả`, target_field=session_preference_habits, category=REVIEW_TAG.
- Do not output text=`sạch sẽ`; output text=`độ sạch sẽ của phòng và không gian nghỉ ngơi`, target_field=session_preference_habits, category=REVIEW_TAG.
- Do not output text=`view đẹp`; output text=`hướng nhìn từ phòng đẹp`, target_field=session_preference_habits, category=REVIEW_TAG.

CATALOG-FRIENDLY EXAMPLES
- User wording: `sạch sẽ`, `vệ sinh tốt`, `phòng sạch`
  Semantic item: text=`độ sạch sẽ của phòng và không gian nghỉ ngơi`, target_field=session_preference_habits, category=REVIEW_TAG
- User wording: `dịch vụ tốt`, `phục vụ tốt`, `nhân viên tốt`
  Semantic item: text=`dịch vụ khách sạn tốt, nhân viên phục vụ chu đáo, hỗ trợ khách hiệu quả`, target_field=session_preference_habits, category=REVIEW_TAG
- User wording: `nướng ngoài trời`, `tiệc nướng`, `BBQ`
  Semantic item: text=`tiện nghi BBQ/nấu nướng ngoài trời cho khách`, target_field=session_amenities, category=HOTEL_AMENITY
- User wording: `hỗ trợ tiếng Ý`, `nhân viên nói tiếng Ý`
  Semantic item: text=`hỗ trợ giao tiếp bằng tiếng Ý trong khách sạn`, target_field=session_amenities, category=HOTEL_AMENITY
- User wording: `nhiều tiện ích`, `nhiều tiện nghi`, `tiện nghi đầy đủ`, `tối đa tiện nghi`
  Constraint: note_amenities=`max`; do not output a semantic item for this generic request
- User wording: `view đẹp`
  Semantic item: text=`hướng nhìn từ phòng đẹp`, target_field=session_preference_habits, category=REVIEW_TAG
- User wording: `gần trung tâm`, `gần bệnh viện`
  Semantic item: use a PLACE_TYPE noun phrase such as `trung tâm thành phố` or `bệnh viện và cơ sở y tế`, target_field=nearby_place, category=PLACE_TYPE

END-TO-END EXAMPLE
- User query: `tôi muốn khách sạn nằm ở trung tâm, có nhiều tiện ích, dịch vụ tốt, sạch sẽ và view đẹp`
- Correct constraints.note_amenities: `max`
- Correct semantic_preferences.items:
  - text=`trung tâm thành phố`, target_field=nearby_place, category=PLACE_TYPE
  - text=`dịch vụ khách sạn tốt, nhân viên phục vụ chu đáo, hỗ trợ khách hiệu quả`, target_field=session_preference_habits, category=REVIEW_TAG
  - text=`độ sạch sẽ của phòng và không gian nghỉ ngơi`, target_field=session_preference_habits, category=REVIEW_TAG
  - text=`hướng nhìn từ phòng đẹp`, target_field=session_preference_habits, category=REVIEW_TAG
- Incorrect semantic items for that query: `nằm ở trung tâm`, `có nhiều tiện ích`, `dịch vụ tốt`, `sạch sẽ`, `view đẹp`.

PLACE TYPE REWRITE RULES
- For nearby_place with PLACE_TYPE, write the text as a place type noun phrase only.
- Do not include relation words such as `gần`, `ở gần`, `tọa lạc gần`, `cạnh`, or `kề bên`.
- For hospital/medical-location intent, prefer `bệnh viện và cơ sở y tế` instead of `tọa lạc gần bệnh viện`.
- For downtown/center intent, prefer `trung tâm thành phố` instead of `tọa lạc gần trung tâm thành phố`.

DATE RULES
- Support Vietnamese date expressions such as `23/6 đến 25/6`, `23 tháng 6`, `ngày 23 tháng 6`, and `2 đêm từ 23 tháng 6`.
- Support relative Vietnamese expressions such as `cuối tuần sau`, `tuần sau`, `ngày mai`, and `mốt` using current_date.
- If a partial date omits the year, infer the nearest reasonable future date relative to current_date.
- If ambiguous and not safe to infer, keep check_in/check_out null.

FORMAT
- Do not fill every field in the schema.
- Omit missing scalar fields instead of outputting null.
- Use `{}` for empty entities or constraints.
- semantic_preferences.items may be empty.
- Do not output freeform_notes anywhere; freeform notes are disabled.
""".strip()

class LLMIntentExtractor:
    def __init__(
        self,
        model: str | None = None,
    ) -> None:
        self.client = OpenAIResponsesClient()
        self.model = model or os.getenv("LLM_MODEL", "gpt-4o-mini")
        self.last_trace: dict[str, object] = {}

    def extract(
        self,
        query: str,
        user_id: str | None = None,
        conversation_history: list[dict[str, str]] | None = None,
        session_context: dict[str, object] | None = None,
    ) -> IntentResult:
        current_date = date.today().isoformat()
        normalized_history = self._normalize_history(conversation_history)
        normalized_session_context = self._normalize_session_context(session_context)
        payload = self.client.create_structured_output(
            model=self.model,
            instructions=INTENT_INSTRUCTIONS,
            input_text=self._build_input_text(
                current_date=current_date,
                query=query,
                conversation_history=normalized_history,
                session_context=normalized_session_context,
            ),
            schema_name="intent_result",
            schema=INTENT_SCHEMA,
            safety_identifier=user_id,
            strict=False,
        )

        self.last_trace = {
            "path": "llm",
            "model": self.model,
            "conversation_history": normalized_history,
            "session_context": normalized_session_context,
            "payload": payload,
        }

        entities_payload = payload.get("entities", {})
        constraints_payload = payload.get("constraints", {})
        if not isinstance(entities_payload, dict):
            entities_payload = {}
        if not isinstance(constraints_payload, dict):
            constraints_payload = {}
        semantic_payload = self._extract_semantic_payload(payload, entities_payload, constraints_payload)

        entities = EntitySet(
            destination=entities_payload.get("destination"),
            hotel_name=entities_payload.get("hotel_name"),
            budget_min=entities_payload.get("budget_min"),
            budget_max=entities_payload.get("budget_max"),
            budget_scope=entities_payload.get("budget_scope"),
            trip_type=entities_payload.get("trip_type"),
            nearby_place=entities_payload.get("nearby_place"),
            number_of_guests=entities_payload.get("number_of_guests"),
            check_in=entities_payload.get("check_in"),
            check_out=entities_payload.get("check_out"),
        )
        semantic_items = self._normalize_semantic_items(semantic_payload.get("items", []))
        semantic_items = self._augment_common_semantic_items(query, semantic_items)
        semantic_preferences = SemanticPreferenceSet(items=semantic_items)
        constraints = ConstraintSet(
            budget_level=constraints_payload.get("budget_level"),
            location_hint=constraints_payload.get("location_hint"),
            note_amenities=constraints_payload.get("note_amenities"),
        )
        return IntentResult(
            intent_components=[],
            entities=entities,
            semantic_preferences=semantic_preferences,
            constraints=constraints,
        )

    @staticmethod
    def _extract_semantic_payload(
        payload: dict[str, object],
        entities_payload: dict[str, object],
        constraints_payload: dict[str, object],
    ) -> dict[str, object]:
        semantic_payload = payload.get("semantic_preferences")
        if isinstance(semantic_payload, dict):
            return semantic_payload

        # Non-strict sparse output can occasionally place semantic_preferences
        # inside another top-level object. Recover instead of silently dropping.
        for candidate in (
            entities_payload.get("semantic_preferences"),
            constraints_payload.get("semantic_preferences"),
        ):
            if isinstance(candidate, dict):
                return candidate
            if isinstance(candidate, list):
                return {"items": candidate}

        if isinstance(semantic_payload, list):
            return {"items": semantic_payload}
        return {}

    @staticmethod
    def _unique_list(values: list[str]) -> list[str]:
        return list(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))

    @staticmethod
    def _normalize_semantic_items(values: list[dict[str, str]]) -> list[SemanticPreferenceItem]:
        normalized: list[SemanticPreferenceItem] = []
        seen: set[tuple[str, str, str, str]] = set()
        for item in values:
            text = str(item.get("text", "")).strip()
            target_field = str(item.get("target_field", "")).strip()
            category = str(item.get("category", "")).strip()
            priority = str(item.get("priority", "soft")).strip() or "soft"
            if (
                not text
                or target_field not in TARGET_FIELD_ENUM
                or category not in CATEGORY_ENUM
                or priority not in PRIORITY_ENUM
            ):
                continue
            key = (text, target_field, category, priority)
            if key in seen:
                continue
            seen.add(key)
            normalized.append(
                SemanticPreferenceItem(
                    text=text,
                    target_field=target_field,
                    category=category,
                    priority=priority,
                )
            )
        return normalized

    @staticmethod
    def _augment_common_semantic_items(
        query: str,
        items: list[SemanticPreferenceItem],
    ) -> list[SemanticPreferenceItem]:
        normalized_query = _fold_vietnamese_text(query)
        additions: list[SemanticPreferenceItem] = []
        if any(pattern in normalized_query for pattern in ("sach se", "ve sinh tot", "phong sach")):
            additions.append(
                SemanticPreferenceItem(
                    text="độ sạch sẽ của phòng và không gian nghỉ ngơi",
                    target_field="session_preference_habits",
                    category="REVIEW_TAG",
                    priority="soft",
                )
            )
        if any(
            pattern in normalized_query
            for pattern in (
                "dich vu tot",
                "dich vu sach se",
                "phuc vu tot",
                "nhan vien tot",
                "nhan vien chu dao",
            )
        ):
            additions.append(
                SemanticPreferenceItem(
                    text="dịch vụ khách sạn tốt, nhân viên phục vụ chu đáo, hỗ trợ khách hiệu quả",
                    target_field="session_preference_habits",
                    category="REVIEW_TAG",
                    priority="soft",
                )
            )
        if any(pattern in normalized_query for pattern in ("view dep", "huong nhin dep", "tam nhin dep")):
            additions.append(
                SemanticPreferenceItem(
                    text="hướng nhìn từ phòng đẹp",
                    target_field="session_preference_habits",
                    category="REVIEW_TAG",
                    priority="soft",
                )
            )

        existing = {(item.text, item.target_field, item.category) for item in items}
        for item in additions:
            key = (item.text, item.target_field, item.category)
            if key not in existing:
                items.append(item)
                existing.add(key)
        return items

    @staticmethod
    def _build_input_text(
        *,
        current_date: str,
        query: str,
        conversation_history: list[dict[str, str]],
        session_context: dict[str, object],
    ) -> str:
        payload = {
            "current_date": current_date,
            "session_context": session_context,
            "conversation_history": conversation_history,
            "query": query,
        }
        return json.dumps(payload, ensure_ascii=False)

    @staticmethod
    def _normalize_session_context(session_context: dict[str, object] | None) -> dict[str, object]:
        if not isinstance(session_context, dict):
            return {}
        keys = (
            "destination",
            "check_in",
            "check_out",
            "nearby_place",
            "number_of_guests",
            "has_pet",
            "has_children",
            "session_price_range",
            "note_amenities",
        )
        return {
            key: value
            for key in keys
            if (value := session_context.get(key)) not in (None, "", {}, [])
        }

    @staticmethod
    def _normalize_history(conversation_history: list[dict[str, str]] | None) -> list[dict[str, str]]:
        if not conversation_history:
            return []

        legacy_turns: list[dict[str, str]] = []
        role_messages: list[dict[str, str]] = []
        for item in conversation_history:
            if not isinstance(item, dict):
                continue
            user_query = str(item.get("user_query", "")).strip()
            llm_answer = str(item.get("llm_answer", "")).strip()
            if user_query or llm_answer:
                legacy_turns.append(
                    {
                        "user_query": user_query,
                        "llm_answer": llm_answer,
                    }
                )
                continue

            role = str(item.get("role", "")).strip().lower()
            content = str(item.get("content", "")).strip()
            if role in {"user", "assistant"} and content:
                role_messages.append({"role": role, "content": content})

        if legacy_turns:
            return legacy_turns[-10:]

        turns: list[dict[str, str]] = []
        current_user_query: str | None = None
        for message in role_messages:
            role = message["role"]
            content = message["content"]
            if role == "user":
                if current_user_query is not None:
                    turns.append({"user_query": current_user_query, "llm_answer": ""})
                current_user_query = content
                continue
            if role == "assistant" and current_user_query is not None:
                turns.append({"user_query": current_user_query, "llm_answer": content})
                current_user_query = None

        if current_user_query is not None:
            turns.append({"user_query": current_user_query, "llm_answer": ""})

        return turns[-10:]


def _fold_vietnamese_text(value: str) -> str:
    lowered = str(value or "").lower().replace("đ", "d").replace("Đ", "d")
    return "".join(
        char
        for char in unicodedata.normalize("NFD", lowered)
        if unicodedata.category(char) != "Mn"
    )
