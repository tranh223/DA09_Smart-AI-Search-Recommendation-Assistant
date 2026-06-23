"""Authentication business logic — register, login, get current user."""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
from typing import Any

from app.auth.schemas import AuthData
from app.auth.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.db.mongo.mongo_client import get_collection

logger = logging.getLogger(__name__)

# Collection names from env
ACCOUNT_COLLECTION = os.getenv("MONGODB_ACCOUNT_COLLECTION", "Account")
USER_PROFILE_COLLECTION = os.getenv("MONGODB_USER_PROFILE_COLLECTION", "Users")


# ── Helpers ───────────────────────────────────────────────────────────────────


def _generate_user_id() -> str:
    """Generate the next ``user_XXX`` id by auto-incrementing.

    Scans both Account and Users collections for the highest existing ``user_id``
    matching the pattern ``user_\\d+`` and returns the next integer.
    Falls back to ``user_001`` if the collections are empty.
    """
    account_col = get_collection(ACCOUNT_COLLECTION)
    users_col = get_collection(USER_PROFILE_COLLECTION)

    pipeline = [
        {"$match": {"user_id": {"$regex": r"^user_\d+$"}}},
        {
            "$addFields": {
                "_num": {
                    "$toInt": {
                        "$arrayElemAt": [{"$split": ["$user_id", "_"]}, 1]
                    }
                }
            }
        },
        {"$sort": {"_num": -1}},
        {"$limit": 1},
    ]

    max_num = 0

    acc_results = list(account_col.aggregate(pipeline))
    if acc_results:
        max_num = max(max_num, acc_results[0]["_num"])

    usr_results = list(users_col.aggregate(pipeline))
    if usr_results:
        max_num = max(max_num, usr_results[0]["_num"])

    return f"user_{max_num + 1:03d}"


def _serialize_user_profile(doc: dict[str, Any] | None) -> dict[str, Any]:
    """Convert a MongoDB user profile document to a JSON-safe dict."""
    if doc is None:
        return {}
    result = {k: v for k, v in doc.items() if k != "_id"}
    return result


# ── Public API ────────────────────────────────────────────────────────────────


def register_user(username: str, password: str, name: str) -> AuthData:
    """Register a new account and create a default user profile.

    Steps:
        1. Check if username already exists → raise ValueError
        2. Generate a new ``user_id``
        3. Insert document into ``Account`` collection
        4. Insert default profile into ``Users`` collection
        5. Create JWT token
        6. Return AuthData

    Raises
    ------
    ValueError
        If the username is already taken.
    """
    account_col = get_collection(ACCOUNT_COLLECTION)
    users_col = get_collection(USER_PROFILE_COLLECTION)

    # 1. Check duplicate username
    existing = account_col.find_one({"username": username})
    if existing:
        raise ValueError(f"Username '{username}' đã tồn tại.")

    # 2. Generate user_id
    user_id = _generate_user_id()
    now = datetime.now(timezone.utc)

    # 3. Insert Account
    account_doc = {
        "user_id": user_id,
        "username": username,
        "hashed_password": hash_password(password),
        "role": "user",
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    account_col.insert_one(account_doc)
    logger.info("[auth] Account created: user_id=%s username=%s", user_id, username)

    # 4. Insert default User profile
    user_profile_doc = {
        "user_id": user_id,
        "name": name,
        "long_term_profile": {
            "nationality": None,
            "age_group": None,
            "current_workplace": None,
            "is_enough": False,
            "traveler_type": {},
            "long_term_trip_types": {},
            "long_term_budget_levels": {},
            "long_term_price_range": {"min": None, "max": None, "currency": "VND"},
            "long_term_preference_habits": {},
            "long_term_hotel_types": {},
            "long_term_room_views": {},
            "long_term_amenities": {},
            "recommendation_clicks": {"hotel": []},
            "long_term_negative_preferences": {
                "avoid_hotel_types": {},
                "avoid_amenities": {},
                "avoid_preference_habits": {},
                "avoid_nearby_places": {},
                "avoid_locations": {},
            },
            "gender": None,
        },
    }
    users_col.insert_one(user_profile_doc)
    logger.info("[auth] User profile created: user_id=%s name=%s", user_id, name)

    # 5. Create JWT
    token = create_access_token({"sub": user_id, "role": "user"})

    # 6. Return
    return AuthData(
        access_token=token,
        role="user",
        user=_serialize_user_profile(user_profile_doc),
    )


def login_user(username: str, password: str) -> AuthData:
    """Authenticate a user by username/password and return JWT + profile.

    Raises
    ------
    ValueError
        If the username does not exist, the password is wrong, or the
        account is deactivated.
    """
    account_col = get_collection(ACCOUNT_COLLECTION)
    users_col = get_collection(USER_PROFILE_COLLECTION)

    # 1. Find account
    account = account_col.find_one({"username": username})
    if account is None:
        raise ValueError("Tên đăng nhập hoặc mật khẩu không đúng.")

    # 2. Verify password
    if not verify_password(password, account["hashed_password"]):
        raise ValueError("Tên đăng nhập hoặc mật khẩu không đúng.")

    # 3. Check active
    if not account.get("is_active", True):
        raise ValueError("Tài khoản đã bị vô hiệu hóa.")

    user_id: str = account["user_id"]
    role: str = account.get("role", "user")

    # 4. Load user profile
    user_profile = users_col.find_one({"user_id": user_id})

    # 5. Create JWT
    token = create_access_token({"sub": user_id, "role": role})

    # 6. Return
    return AuthData(
        access_token=token,
        role=role,
        user=_serialize_user_profile(user_profile),
    )


def get_current_user_data(user_id: str) -> dict[str, Any]:
    """Load account + user profile for a verified user_id.

    Returns
    -------
    dict
        ``{"account": {...}, "user_profile": {...}}``

    Raises
    ------
    ValueError
        If the account or profile is not found.
    """
    account_col = get_collection(ACCOUNT_COLLECTION)
    users_col = get_collection(USER_PROFILE_COLLECTION)

    account = account_col.find_one({"user_id": user_id})
    if account is None:
        raise ValueError("Tài khoản không tồn tại.")

    user_profile = users_col.find_one({"user_id": user_id})

    # Sanitize: remove hashed_password and _id from account
    account_safe = {
        k: v
        for k, v in account.items()
        if k not in ("_id", "hashed_password")
    }

    return {
        "account": account_safe,
        "user_profile": _serialize_user_profile(user_profile),
    }
