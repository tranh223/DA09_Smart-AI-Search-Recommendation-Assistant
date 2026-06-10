"""
Smoke test for user_profile_tool.py
Tests basic functionality of user profile loading and searching.
"""
import sys
import json
from pathlib import Path

# Add parent to path so we can import tools
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.user_profile_tool import (
    get_all_user_profiles,
    get_user_by_id,
    search_user_profile,
    search_users_by_destination,
    get_user_preferences,
)


def test_load_users():
    """Test loading user data from JSON."""
    print("TEST: Load all users")
    users = get_all_user_profiles()
    assert isinstance(users, list), "Expected list of users"
    assert len(users) > 0, "Expected at least one user"
    print(f"✓ Loaded {len(users)} users")
    return users


def test_get_user_by_id(users):
    """Test getting user by ID."""
    print("\nTEST: Get user by ID")
    if not users:
        print("⊘ Skipped: No users in data")
        return
    
    first_user_id = users[0].get("user_id")
    user = get_user_by_id(first_user_id)
    assert user is not None, f"Expected to find user {first_user_id}"
    assert user.get("user_id") == first_user_id, "User ID mismatch"
    print(f"✓ Found user: {user.get('name')} ({first_user_id})")


def test_search_user_profile(users):
    """Test searching user profile."""
    print("\nTEST: Search user profile")
    if not users:
        print("⊘ Skipped: No users in data")
        return
    
    first_user_id = users[0].get("user_id")
    user = search_user_profile(first_user_id)
    assert user is not None, f"Expected to find user {first_user_id}"
    print(f"✓ Found user via search: {user.get('name')}")


def test_get_user_preferences(users):
    """Test getting user preferences."""
    print("\nTEST: Get user preferences")
    if not users:
        print("⊘ Skipped: No users in data")
        return
    
    first_user_id = users[0].get("user_id")
    prefs = get_user_preferences(first_user_id)
    assert prefs is not None, f"Expected preferences for {first_user_id}"
    assert "long_term_profile" in prefs, "Expected long_term_profile in preferences"
    assert "session_context" in prefs, "Expected session_context in preferences"
    print(f"✓ Got preferences for {prefs.get('name')}")
    print(f"  - Long-term destination: {prefs['long_term_profile'].get('long_term_trip_types', {})}")
    print(f"  - Session destination: {prefs['session_context'].get('destination')}")


def test_search_by_destination(users):
    """Test searching users by destination."""
    print("\nTEST: Search users by destination")
    if not users:
        print("⊘ Skipped: No users in data")
        return
    
    # Get a destination from first user
    first_user = users[0]
    destination = first_user.get("session_context", {}).get("destination")
    
    if not destination:
        print(f"⊘ Skipped: First user has no destination")
        return
    
    found_users = search_users_by_destination(destination)
    assert isinstance(found_users, list), "Expected list of users"
    assert len(found_users) > 0, f"Expected to find users in {destination}"
    print(f"✓ Found {len(found_users)} user(s) with destination '{destination}'")
    for user in found_users:
        print(f"  - {user.get('name')} ({user.get('user_id')})")


def test_user_data_structure(users):
    """Test user data structure and fields."""
    print("\nTEST: User data structure")
    if not users:
        print("⊘ Skipped: No users in data")
        return
    
    first_user = users[0]
    required_fields = ["_id", "user_id", "name", "long_term_profile", "session_context"]
    
    for field in required_fields:
        assert field in first_user, f"Missing required field: {field}"
    
    print(f"✓ User data has all required fields")
    print(f"  User: {first_user.get('name')} ({first_user.get('user_id')})")
    print(f"  Long-term budget: {first_user.get('long_term_profile', {}).get('long_term_budget_levels')}")
    print(f"  Session budget: {first_user.get('session_context', {}).get('session_budget_levels')}")


def main():
    """Run all smoke tests."""
    print("=" * 60)
    print("SMOKE TEST: user_profile_tool")
    print("=" * 60)
    
    try:
        users = test_load_users()
        test_get_user_by_id(users)
        test_search_user_profile(users)
        test_get_user_preferences(users)
        test_search_by_destination(users)
        test_user_data_structure(users)
        
        print("\n" + "=" * 60)
        print("✓ ALL TESTS PASSED")
        print("=" * 60)
        return 0
    
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        return 1
    
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
