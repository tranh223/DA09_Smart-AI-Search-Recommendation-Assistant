"""Unit smoke tests for structured RAG input and deterministic routing."""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from rag_input import build_retrieval_query, build_structured_plan, parse_rag_request
from tools import rag_tool


CASES = [
    {
        "name": "feature-family-kids-club",
        "intent_type": "HOTEL_FEATURE_QA",
        "query": "InterContinental Danang co phu hop cho gia dinh khong?",
        "features": {
            "hotel_name": "InterContinental Danang",
            "destination": "Da Nang",
            "amenities": ["kids_club"],
            "expectations": ["family_trip"],
        },
        "main_object": "InterContinental Danang",
    },
    {
        "name": "feature-pool-spa",
        "intent_type": "HOTEL_FEATURE_QA",
        "query": "Vinpearl Resort Nha Trang co ho boi va spa khong?",
        "features": {
            "hotel_name": "Vinpearl Resort Nha Trang",
            "destination": "Nha Trang",
            "amenities": ["pool", "spa"],
            "expectations": ["relaxation"],
        },
        "main_object": "Vinpearl Resort Nha Trang",
    },
    {
        "name": "feature-destination-only",
        "intent_type": "HOTEL_FEATURE_QA",
        "query": "Khach san o Da Lat co bai dau xe khong?",
        "features": {
            "destination": "Da Lat",
            "amenities": ["parking"],
        },
        "main_object": "Da Lat",
    },
    {
        "name": "feature-minimal",
        "intent_type": "HOTEL_FEATURE_QA",
        "query": "Khach san nay co phong gym khong?",
        "features": {
            "amenities": ["fitness"],
        },
        "main_object": "hotel",
    },
    {
        "name": "policy-checkin",
        "intent_type": "HOTEL_POLICY_QA",
        "query": "Pullman Hanoi cho check-in tu may gio?",
        "features": {
            "hotel_name": "Pullman Hanoi",
            "destination": "Hanoi",
            "expectations": ["checkin_checkout"],
        },
        "main_object": "Pullman Hanoi",
    },
    {
        "name": "policy-pets",
        "intent_type": "HOTEL_POLICY_QA",
        "query": "Sheraton Hanoi co cho mang thu cung khong?",
        "features": {
            "hotel_name": "Sheraton Hanoi",
            "amenities": ["pets"],
        },
        "main_object": "Sheraton Hanoi",
    },
    {
        "name": "policy-cancellation-destination",
        "intent_type": "HOTEL_POLICY_QA",
        "query": "Chinh sach huy phong tai Phu Quoc nhu the nao?",
        "features": {
            "destination": "Phu Quoc",
            "expectations": ["cancellation_policy"],
        },
        "main_object": "Phu Quoc",
    },
    {
        "name": "comparison-family",
        "intent_type": "HOTEL_COMPARISON_QA",
        "query": "So sanh cac resort phu hop gia dinh tai Nha Trang.",
        "features": {
            "destination": "Nha Trang",
            "amenities": ["kids_club", "pool"],
            "expectations": ["family_trip"],
        },
        "main_object": "Nha Trang",
    },
    {
        "name": "comparison-hotel",
        "intent_type": "HOTEL_COMPARISON_QA",
        "query": "So sanh Sofitel Metropole voi cac khach san cung phan khuc.",
        "features": {
            "hotel_name": "Sofitel Legend Metropole Hanoi",
            "destination": "Hanoi",
            "expectations": ["luxury_trip"],
        },
        "main_object": "Sofitel Legend Metropole Hanoi",
    },
    {
        "name": "comparison-minimal",
        "intent_type": "HOTEL_COMPARISON_QA",
        "query": "So sanh cac lua chon khach san.",
        "features": {},
        "main_object": "hotel",
    },
]


EXPECTED_ROUTES = {
    "HOTEL_FEATURE_QA": {
        "needs_graph": False,
        "rag_sections": ["description", "activities"],
        "hotel_sql_needs": ["detail", "activities"],
    },
    "HOTEL_POLICY_QA": {
        "needs_graph": False,
        "rag_sections": ["policy"],
        "hotel_sql_needs": ["policies"],
    },
    "HOTEL_COMPARISON_QA": {
        "needs_graph": True,
        "rag_sections": ["description", "policy", "activities"],
        "hotel_sql_needs": ["detail", "policies", "activities"],
    },
}


def _payload(case: dict) -> dict:
    return {
        "intent_type": case["intent_type"],
        "source": "RAG_SERVICE",
        "parameters": {
            "query": case["query"],
            "features": case["features"],
        },
    }


def _test_case(case: dict) -> None:
    request = parse_rag_request(_payload(case))
    plan = build_structured_plan(request)
    retrieval_query = build_retrieval_query(request)
    route = EXPECTED_ROUTES[case["intent_type"]]

    assert plan["query_type"] == case["intent_type"], case["name"]
    assert plan["main_object"] == case["main_object"], case["name"]
    assert plan["needs_rag"] is True, case["name"]
    assert plan["needs_hotel_sql"] is True, case["name"]
    assert plan["needs_graph"] is route["needs_graph"], case["name"]
    assert plan["rag_sections"] == route["rag_sections"], case["name"]
    assert plan["hotel_sql_needs"] == route["hotel_sql_needs"], case["name"]
    assert retrieval_query.startswith(case["query"]), case["name"]

    features = request.parameters.features
    for value in [
        features.hotel_name,
        features.destination,
        *features.amenities,
        *features.expectations,
    ]:
        if value:
            assert value in retrieval_query, f"{case['name']}: missing {value}"


def _test_rag_metadata_helpers() -> None:
    rag_tool._META = {
        "0": {
            "hotel_id": 123,
            "hotel_name": "InterContinental Danang Sun Peninsula Resort",
            "section": "description",
        }
    }
    assert rag_tool._resolve_hotel_ids("InterContinental Danang") == {123}
    assert rag_tool._metadata_match(
        {"section": "policy"},
        {"section": ["policy", "activities"]},
    )
    assert not rag_tool._metadata_match(
        {"section": "description"},
        {"section": ["policy"]},
    )


def main() -> int:
    assert len(CASES) == 10
    for case in CASES:
        _test_case(case)
        print(f"PASS: {case['name']}")

    _test_rag_metadata_helpers()
    print("Structured RAG input smoke test passed: 10/10 cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
