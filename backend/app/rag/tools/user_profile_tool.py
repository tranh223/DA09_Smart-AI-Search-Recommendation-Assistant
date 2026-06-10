"""
User Profile Tool
Reads user profile data from MongoDB using connection settings from .env.
"""
import os
import re
from typing import Any, Dict, List, Optional

from bson import ObjectId
from dotenv import load_dotenv
from pymongo.collection import Collection

from tools.mongo_tool import get_client

load_dotenv()

DEFAULT_DB_NAME = "VinSmartFuture"
DEFAULT_COLLECTION_NAME = "Users"
DEFAULT_QUERY_LIMIT = 3000

_collection_cache: Optional[Collection] = None
_user_data_cache: Optional[List[Dict[str, Any]]] = None


def _get_env_value(name: str, default: str) -> str:
    """Read an env value while tolerating quoted values with extra spaces."""
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip().strip('"\'')
    return value or default


def get_user_profile_source() -> Dict[str, str]:
    """Return the MongoDB source used by this tool."""
    return {
        "database": _get_env_value("MONGO_DB_NAME", DEFAULT_DB_NAME),
        "collection": _get_env_value("MONGO_USERS_COLLECTION", DEFAULT_COLLECTION_NAME),
    }


def _get_query_limit() -> int:
    raw_limit = _get_env_value("MONGO_USERS_LIMIT", str(DEFAULT_QUERY_LIMIT))
    try:
        return int(raw_limit)
    except ValueError:
        return DEFAULT_QUERY_LIMIT


def _get_collection() -> Collection:
    """Get the MongoDB Users collection configured by .env."""
    global _collection_cache
    if _collection_cache is not None:
        return _collection_cache

    source = get_user_profile_source()
    client = get_client()
    _collection_cache = client[source["database"]][source["collection"]]
    return _collection_cache


def _normalize_mongo_value(value: Any) -> Any:
    """Convert Mongo-only values into JSON-friendly Python values."""
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, list):
        return [_normalize_mongo_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _normalize_mongo_value(item) for key, item in value.items()}
    return value


def _normalize_document(document: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if document is None:
        return None
    return _normalize_mongo_value(dict(document))


def _regex_filter(value: str) -> Dict[str, Any]:
    return {"$regex": re.escape(value), "$options": "i"}


def _load_user_data() -> List[Dict[str, Any]]:
    """Load user data from MongoDB and cache it for repeated list/filter calls."""
    global _user_data_cache
    if _user_data_cache is not None:
        return _user_data_cache

    limit = max(_get_query_limit(), 0)
    cursor = _get_collection().find({})
    if limit:
        cursor = cursor.limit(limit)
    _user_data_cache = [_normalize_mongo_value(dict(user)) for user in cursor]
    return _user_data_cache


def refresh_user_profile_cache() -> None:
    """Clear cached MongoDB user profile data."""
    global _user_data_cache
    _user_data_cache = None


def search_user_profile(user_id: str, query: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Search user profile by user_id or query text.

    Args:
        user_id: User ID to search for (e.g., "user_001")
        query: Optional search query (searches in name, user_id, destination, etc.)

    Returns:
        User profile dict, or None if not found
    """
    if user_id:
        user = _normalize_document(_get_collection().find_one({"user_id": user_id}))
        if user:
            return user

    if query:
        text_filter = _regex_filter(query)
        return _normalize_document(
            _get_collection().find_one(
                {
                    "$or": [
                        {"name": text_filter},
                        {"user_id": text_filter},
                        {"session_context.destination": text_filter},
                        {"session_context.current_location": text_filter},
                        {"session_context.nearby_place": text_filter},
                    ]
                }
            )
        )

    return None


def get_all_user_profiles() -> List[Dict[str, Any]]:
    """Get all user profiles from MongoDB."""
    return _load_user_data()


def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    """Get user profile by user_id."""
    if not user_id:
        return None
    return _normalize_document(_get_collection().find_one({"user_id": user_id}))


def search_users_by_destination(destination: str) -> List[Dict[str, Any]]:
    """Search users by destination."""
    if not destination:
        return []

    docs = _get_collection().find(
        {"session_context.destination": _regex_filter(destination)}
    ).limit(_get_query_limit())
    results = [_normalize_mongo_value(dict(user)) for user in docs]
    if results:
        return results

    # Preserve the previous "either string contains the other" behavior.
    dest_lower = destination.lower()
    results = []
    for user in _load_user_data():
        session_dest = user.get("session_context", {}).get("destination")
        if session_dest is None:
            continue
        session_dest_lower = str(session_dest).lower()
        if dest_lower in session_dest_lower or session_dest_lower in dest_lower:
            results.append(user)
    return results


def get_user_preferences(user_id: str) -> Optional[Dict[str, Any]]:
    """Get user preferences (both long-term and session)."""
    user = get_user_by_id(user_id)
    if not user:
        return None

    return {
        "user_id": user_id,
        "name": user.get("name"),
        "long_term_profile": user.get("long_term_profile"),
        "session_context": user.get("session_context"),
    }


def _contains_text(value: Any, needle: str) -> bool:
    if value is None:
        return False
    return needle in str(value).lower()


def _profile_value_matches(value: Any, needle: str) -> bool:
    """Match strings, lists, and weighted-key dictionaries used by profiles."""
    if value is None:
        return False
    if isinstance(value, dict):
        return any(_contains_text(key, needle) for key in value.keys())
    if isinstance(value, list):
        return any(_contains_text(item, needle) for item in value)
    return _contains_text(value, needle)


def filter_users_by_budget_level(budget_level: str) -> List[Dict[str, Any]]:
    """Filter users by budget level (e.g., 'low', 'medium', 'high')."""
    budget_lower = budget_level.lower()
    return [
        user
        for user in _load_user_data()
        if _profile_value_matches(
            user.get("long_term_profile", {}).get("long_term_budget_levels"),
            budget_lower,
        )
        or _profile_value_matches(
            user.get("long_term_profile", {}).get("budget_levels"),
            budget_lower,
        )
    ]


def filter_users_by_traveler_type(traveler_type: str) -> List[Dict[str, Any]]:
    """Filter users by traveler type (e.g., 'solo', 'planner', 'explorer')."""
    travel_lower = traveler_type.lower()
    return [
        user
        for user in _load_user_data()
        if _profile_value_matches(
            user.get("long_term_profile", {}).get("traveler_type"),
            travel_lower,
        )
        or _profile_value_matches(
            user.get("long_term_profile", {}).get("long_term_trip_types"),
            travel_lower,
        )
    ]


def filter_users_by_amenities(amenity: str) -> List[Dict[str, Any]]:
    """Filter users by preferred amenities."""
    amenity_lower = amenity.lower()
    return [
        user
        for user in _load_user_data()
        if _profile_value_matches(
            user.get("long_term_profile", {}).get("long_term_amenities"),
            amenity_lower,
        )
        or _profile_value_matches(
            user.get("long_term_profile", {}).get("amenities"),
            amenity_lower,
        )
    ]
