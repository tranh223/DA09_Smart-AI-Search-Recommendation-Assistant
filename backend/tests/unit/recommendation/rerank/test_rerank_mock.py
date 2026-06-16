import json

from app.recommendation.rerank.config import Settings, postgres_debug_info
from app.recommendation.rerank.config import PACKAGE_ROOT
from app.recommendation.rerank.llm_reranker import rerank_with_llm
from app.recommendation.rerank.llm_reranker import validate_llm_output
from app.recommendation.rerank.reranker import rerank


def example_request():
    return json.loads((PACKAGE_ROOT / "data" / "example_request.json").read_text(encoding="utf-8"))


def with_mock_candidates(request):
    payload = json.loads((PACKAGE_ROOT / "data" / "mock_candidate_hotels.json").read_text(encoding="utf-8"))
    request["candidate_items"] = payload["candidate_items"]
    request["options"]["enrich_postgres_candidates"] = False
    return request


def test_full_mock_rerank_succeeds(monkeypatch):
    monkeypatch.setenv("MOCK_MODE", "true")
    request = with_mock_candidates(example_request())
    request["options"]["use_llm_rerank"] = True
    result = rerank(request["user_id"], None, request["candidate_items"], request["query"], request["options"])
    assert result["ranked_items"]
    assert result["ranked_hotels"]
    assert result["ranked_hotels"][0]["item_id"] == result["ranked_items"][0]["item_id"]
    assert result["ranked_hotels"][0]["rank"] == result["ranked_items"][0]["rank"]
    assert [item["item_id"] for item in result["ranked_hotels"]] == [
        item["item_id"] for item in result["ranked_items"]
    ]
    assert result["debug"]["profile_source"] == "mock"
    assert result["debug"]["booking_source"] == "mock"
    assert result["debug"]["llm_source"] == "mock"
    assert result["debug"]["normalized_session"]["destination"] == request["options"]["session_context"]["destination"]


def test_llm_validation_rejects_bad_items():
    valid = validate_llm_output(
        {"ranked_items": [{"item_id": "1", "llm_score": 0.5}, {"item_id": "2", "llm_score": 9}]},
        {"1"},
    )
    assert set(valid) == {"1"}


def test_no_llm_uses_base_score(monkeypatch):
    monkeypatch.setenv("MOCK_MODE", "true")
    request = with_mock_candidates(example_request())
    request["options"]["use_llm_rerank"] = False
    result = rerank(request["user_id"], None, request["candidate_items"], request["query"], request["options"])
    top = result["ranked_items"][0]
    assert top["llm_score"] is None
    assert top["final_score"] == top["base_score"]


def test_diversify_recommendations_reorders_similar_hotels(monkeypatch):
    monkeypatch.setenv("MOCK_MODE", "true")
    request = example_request()
    request["options"]["use_llm_rerank"] = False
    request["options"]["enrich_postgres_candidates"] = False
    request["options"]["diversify_recommendations"] = True
    request["options"]["diversity_strength"] = 0.3
    request["candidate_items"] = [
        {
            "item_id": "1",
            "destination": "Vung Tau",
            "available": True,
            "price_min": 8000000,
            "price_max": 9000000,
            "rating": 4.0,
            "review_sentiment": 0.8,
            "hotel_type": "Resort",
            "tags": ["Gia đình có trẻ nhỏ"],
            "nearby_places": ["Nơi Biểu Diễn Văn Nghệ"],
        },
        {
            "item_id": "2",
            "destination": "Vung Tau",
            "available": True,
            "price_min": 8000000,
            "price_max": 9000000,
            "rating": 4.0,
            "review_sentiment": 0.8,
            "hotel_type": "Resort",
            "tags": ["Gia đình có trẻ nhỏ"],
            "nearby_places": ["Nơi Biểu Diễn Văn Nghệ"],
        },
        {
            "item_id": "3",
            "destination": "Vung Tau",
            "available": True,
            "price_min": 8000000,
            "price_max": 9000000,
            "rating": 4.0,
            "review_sentiment": 0.8,
            "hotel_type": "Boutique",
            "tags": ["Gia đình có trẻ nhỏ"],
            "nearby_places": ["Nơi Biểu Diễn Văn Nghệ"],
        },
    ]

    result = rerank(request["user_id"], None, request["candidate_items"], request["query"], request["options"])
    ranked_ids = [item["item_id"] for item in result["ranked_items"]]
    assert ranked_ids[0] == "1"
    assert ranked_ids[1] == "3"
    assert result["debug"]["diversified"] is True


def test_empty_after_filter_skips_llm(monkeypatch):
    monkeypatch.setenv("MOCK_MODE", "true")
    request = example_request()
    request["options"]["use_llm_rerank"] = True
    request["candidate_items"] = [
        {
            "item_id": "wrong",
            "destination": "Da Nang",
            "available": True,
            "price_min": 8000000,
            "price_max": 9000000,
        }
    ]
    result = rerank(request["user_id"], None, request["candidate_items"], request["query"], request["options"])
    assert result["ranked_items"] == []
    assert result["debug"]["after_hard_filter"] == 0
    assert result["debug"]["llm_debug"]["reason"] == "no_candidates_after_hard_filter"
    assert result["debug"]["filtered_items"][0]["reason"] == "destination_mismatch"


def test_openrouter_retry_debug_on_failure(monkeypatch):
    settings = Settings(mock_mode=False, openrouter_api_key="token", llm_max_retries=1)

    def fail_response(*args, **kwargs):
        raise RuntimeError("network broke")

    monkeypatch.setattr("app.recommendation.rerank.llm_reranker._openrouter_response", fail_response)
    results, source, fallback, debug = rerank_with_llm(
        settings,
        "query",
        {"user_id": "u1"},
        [{"item_id": "1", "base_score": 0.5, "feature_scores": {}}],
        True,
    )
    assert results == {}
    assert source == "fallback"
    assert fallback is True
    assert debug["reason"] == "RuntimeError: network broke"
    assert len(debug["attempts"]) == 2


def test_postgres_enrichment_keeps_candidate_set(monkeypatch):
    monkeypatch.setenv("MOCK_MODE", "true")
    request = example_request()
    request["options"]["use_llm_rerank"] = False
    request["options"]["enrich_postgres_candidates"] = True
    request["candidate_items"] = [{"item_id": 569205, "keyword_score": 0.9}]

    class FakePostgresStore:
        def __init__(self, settings):
            pass

        def enrich_candidates(self, candidates):
            assert [item["item_id"] for item in candidates] == [569205]
            return [
                {
                    **candidates[0],
                    "name": "Enriched Hotel",
                    "destination": "Vung Tau",
                    "hotel_type": "Ryokan",
                    "price_min": 8000000,
                    "price_max": 12000000,
                    "amenities": ["Tắm suối nước nóng"],
                    "room_views": ["Hướng Hồ"],
                    "available": True,
                    "available_rooms": 3,
                    "rating": 4.7,
                    "review_sentiment": 0.9,
                }
            ], {"requested_ids": ["569205"], "enriched_ids": ["569205"], "missing_ids": []}

    monkeypatch.setattr("app.recommendation.rerank.reranker.PostgresCandidateStore", FakePostgresStore)
    result = rerank(request["user_id"], None, request["candidate_items"], request["query"], request["options"])
    assert [item["item_id"] for item in result["ranked_items"]] == ["569205"]
    assert [item["item_id"] for item in result["ranked_hotels"]] == ["569205"]
    assert result["ranked_items"][0]["name"] == "Enriched Hotel"
    assert result["ranked_hotels"][0]["name"] == "Enriched Hotel"
    assert result["ranked_hotels"][0]["rank"] == 1
    assert result["debug"]["candidate_source"] == "postgres_enriched"
    assert result["debug"]["candidate_enrichment_debug"]["enriched_ids"] == ["569205"]


def test_postgres_debug_info_hides_password():
    info = postgres_debug_info("postgresql://postgres:secret@localhost:5432/hotels_db")
    assert info == {
        "configured": True,
        "scheme": "postgresql",
        "host": "localhost",
        "port": 5432,
        "database": "hotels_db",
        "user": "postgres",
        "password_set": True,
    }
