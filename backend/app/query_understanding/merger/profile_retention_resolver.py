from __future__ import annotations

import os
from typing import Any

from query_understanding.llm import OpenAIResponsesClient
from query_understanding.models.planner import (
    CountInteractionValue,
    LongTermProfile,
)


GROUP_NAMES = [
    "traveler_type",
    "long_term_trip_types",
    "long_term_budget_levels",
    "long_term_preference_habits",
    "long_term_hotel_types",
    "long_term_room_views",
    "long_term_amenities",
    "avoid_hotel_types",
    "avoid_amenities",
    "avoid_preference_habits",
    "avoid_nearby_places",
    "avoid_locations",
]

GROUP_DECISION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["profile", "tagremoved"],
    "properties": {
        "profile": {"type": "array", "items": {"type": "string"}},
        "tagremoved": {"type": "array", "items": {"type": "string"}},
    },
}

RETENTION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": GROUP_NAMES,
    "properties": {group_name: GROUP_DECISION_SCHEMA for group_name in GROUP_NAMES},
}

RETENTION_INSTRUCTIONS = """
You are the long-term profile retention resolver for an OTA hotel assistant.

Your job is to decide which existing profile features should stay in the main long-term profile
and which should be moved to tagremoved.

Input JSON contains:
- current_query
- session_signals: features reinforced by the current session
- old_profile: features currently stored in the main long-term profile
- tagremoved: features currently stored in the tagremoved pool

Decision rules:
- If a feature is reinforced by the current session, keep it in profile.
- Features in old_profile that are no longer aligned with the current session may move to tagremoved.
- Features in tagremoved may return to profile if the current session clearly reinforces them.
- Never invent new feature names.
- Every feature must belong to exactly one bucket: profile or tagremoved.
- Prefer stable retention: if uncertain, keep a feature in its current bucket.
- Only decide for the feature names provided in input. Do not add any extra keys.
""".strip()


class ProfileRetentionResolver:
    def __init__(
        self,
        client: OpenAIResponsesClient | None = None,
        model: str | None = None,
    ) -> None:
        self.client = client or OpenAIResponsesClient()
        self.model = model or os.getenv("LLM_MODEL", "gpt-4o-mini")
        self.last_trace: dict[str, Any] = {}

    def resolve(
        self,
        *,
        query: str,
        old_profile: LongTermProfile,
        tagremoved_profile: LongTermProfile,
        session_signals: dict[str, dict[str, CountInteractionValue]],
    ) -> dict[str, dict[str, list[str]]]:
        payload = self._build_input_payload(
            query=query,
            old_profile=old_profile,
            tagremoved_profile=tagremoved_profile,
            session_signals=session_signals,
        )
        if not any(payload["old_profile"].values()) and not any(payload["tagremoved"].values()):
            result = self._default_decisions(payload)
            self.last_trace = {
                "path": "skipped",
                "reason": "no_existing_features",
                "payload": payload,
                "result": result,
            }
            return result

        prompt_cache = self.client.build_prompt_cache_settings(
            component_name="profile_retention_resolver",
            model=self.model,
            instructions=RETENTION_INSTRUCTIONS,
            schema_name="profile_retention",
            schema=RETENTION_SCHEMA,
            strict=True,
        )
        response = self.client.create_structured_output(
            model=self.model,
            instructions=RETENTION_INSTRUCTIONS,
            input_text=_json_dumps(payload),
            schema_name="profile_retention",
            schema=RETENTION_SCHEMA,
            strict=True,
            prompt_cache_key=prompt_cache.get("prompt_cache_key"),
            prompt_cache_retention=prompt_cache.get("prompt_cache_retention"),
        )
        decisions = self._normalize_decisions(response, payload)
        self.last_trace = {
            "path": "llm",
            "model": self.model,
            "payload": payload,
            "response": response,
            "prompt_cache": prompt_cache,
            "response_meta": dict(self.client.last_response_meta),
            "decisions": decisions,
        }
        return decisions

    def _build_input_payload(
        self,
        *,
        query: str,
        old_profile: LongTermProfile,
        tagremoved_profile: LongTermProfile,
        session_signals: dict[str, dict[str, CountInteractionValue]],
    ) -> dict[str, Any]:
        return {
            "current_query": query,
            "session_signals": {
                group_name: _serialize_score_map(session_signals.get(group_name, {}))
                for group_name in GROUP_NAMES
            },
            "old_profile": {
                group_name: _serialize_score_map(_extract_group_map(old_profile, group_name))
                for group_name in GROUP_NAMES
            },
            "tagremoved": {
                group_name: _serialize_score_map(_extract_group_map(tagremoved_profile, group_name))
                for group_name in GROUP_NAMES
            },
        }

    def _normalize_decisions(
        self,
        response: dict[str, Any],
        payload: dict[str, Any],
    ) -> dict[str, dict[str, list[str]]]:
        normalized: dict[str, dict[str, list[str]]] = {}
        for group_name in GROUP_NAMES:
            old_keys = set(payload["old_profile"].get(group_name, {}).keys())
            removed_keys = set(payload["tagremoved"].get(group_name, {}).keys())
            session_keys = set(payload["session_signals"].get(group_name, {}).keys())
            allowed_keys = old_keys | removed_keys | session_keys

            default_profile = sorted(old_keys | session_keys)
            default_tagremoved = sorted(removed_keys - session_keys)

            raw_group = response.get(group_name)
            if not isinstance(raw_group, dict):
                normalized[group_name] = {
                    "profile": default_profile,
                    "tagremoved": default_tagremoved,
                }
                continue

            raw_profile = raw_group.get("profile") if isinstance(raw_group.get("profile"), list) else []
            raw_tagremoved = raw_group.get("tagremoved") if isinstance(raw_group.get("tagremoved"), list) else []

            profile_keys = {str(item).strip() for item in raw_profile if str(item).strip() in allowed_keys}
            tagremoved_keys = {str(item).strip() for item in raw_tagremoved if str(item).strip() in allowed_keys}

            profile_keys |= session_keys
            profile_keys |= {key for key in old_keys if key not in profile_keys and key not in tagremoved_keys}
            tagremoved_keys |= {key for key in removed_keys if key not in profile_keys and key not in tagremoved_keys}
            tagremoved_keys -= session_keys

            normalized[group_name] = {
                "profile": sorted(profile_keys),
                "tagremoved": sorted(tagremoved_keys),
            }
        return normalized

    @staticmethod
    def _default_decisions(payload: dict[str, Any]) -> dict[str, dict[str, list[str]]]:
        decisions: dict[str, dict[str, list[str]]] = {}
        for group_name in GROUP_NAMES:
            old_keys = set(payload["old_profile"].get(group_name, {}).keys())
            removed_keys = set(payload["tagremoved"].get(group_name, {}).keys())
            session_keys = set(payload["session_signals"].get(group_name, {}).keys())
            decisions[group_name] = {
                "profile": sorted(old_keys | session_keys),
                "tagremoved": sorted(removed_keys - session_keys),
            }
        return decisions


def _extract_group_map(profile: LongTermProfile, group_name: str) -> dict[str, CountInteractionValue]:
    if group_name.startswith("avoid_"):
        return getattr(profile.long_term_negative_preferences, group_name)
    return getattr(profile, group_name)


def _serialize_score_map(values: dict[str, CountInteractionValue]) -> dict[str, dict[str, Any]]:
    return {
        key: {
            "count": value.count,
            "last_interaction": value.last_interaction,
        }
        for key, value in values.items()
    }


def _json_dumps(payload: dict[str, Any]) -> str:
    return __import__("json").dumps(payload, ensure_ascii=False)
