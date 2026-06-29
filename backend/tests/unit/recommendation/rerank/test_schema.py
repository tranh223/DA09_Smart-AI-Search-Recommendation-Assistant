from app.recommendation.rerank.normalizer import normalize_candidate
from app.recommendation.rerank.schemas import RankedItem


def test_candidate_id_string_and_lists():
    candidate = normalize_candidate({"item_id": 123, "item_type": "hotel", "amenities": "WiFi", "available": True})
    assert candidate["item_id"] == "123"
    assert candidate["amenities"] == ["WiFi"]


def test_candidate_accepts_hotel_id_alias():
    candidate = normalize_candidate({"hotel_id": 123, "amenities": ["WiFi"], "available": True})
    assert candidate["item_id"] == "123"


def test_candidate_accepts_search_score_alias():
    candidate = normalize_candidate({"item_id": 123, "search_score": 0.82, "available": True})
    assert candidate["item_id"] == "123"
    assert candidate["keyword_score"] == 0.82


def test_candidate_accepts_postgres_hotel_shape():
    candidate = normalize_candidate(
        {
            "id": 47218637,
            "name": "Nhà Sun (The Sun House)",
            "city": "Vung Tau",
            "accommodation_type": "Nhà dân",
            "review_score": 8.8,
            "amenities": ["WiFi miễn phí"],
            "suitable_for": ["Cặp đôi", "family_friendly"],
            "min_price": 500000,
            "max_price": 1500000,
            "room_views": ["Hướng Biển"],
            "nearby_place_names": ["Bãi Biển"],
            "room_count": 3,
        }
    )
    assert candidate["item_id"] == "47218637"
    assert candidate["destination"] == "Vung Tau"
    assert candidate["hotel_type"] == "Nhà dân"
    assert candidate["price_min"] == 500000
    assert candidate["price_max"] == 1500000
    assert candidate["rating"] == 4.4
    assert candidate["review_sentiment"] == 0.88
    assert candidate["available"] is True
    assert candidate["available_rooms"] == 3
    assert candidate["room_views"] == ["Hướng Biển"]
    assert candidate["nearby_places"] == ["Bãi Biển"]


def test_candidate_accepts_postgres_store_enriched_row():
    candidate = normalize_candidate(
        {
            "id": 1,
            "name": "Beach Hotel",
            "city": "Vung Tau",
            "accommodation_type": "Khách sạn",
            "review_score": 9.0,
            "amenities": ["WiFi miễn phí"],
            "room_amenities": ["Máy pha trà cà phê", "WiFi miễn phí"],
            "suitable_for": ["Gia đình có người già"],
            "policyNotes": ["Không hút thuốc"],
            "nearby_places": ["Bãi Biển"],
            "activity_titles": ["Tour biển"],
            "min_price": 1000000,
            "max_price": 2000000,
            "room_count": 5,
        }
    )
    assert candidate["item_id"] == "1"
    assert candidate["amenities"] == ["WiFi miễn phí"]
    assert candidate["tags"] == ["Gia đình có người già", "Không hút thuốc", "Tour biển"]
    assert candidate["available_rooms"] == 5


def test_ranked_item_clamps_scores():
    item = RankedItem(
        item_id="1",
        rank=1,
        final_score=2,
        base_score=-1,
        feature_scores={},
        negative_penalty=9,
    )
    assert item.final_score == 1.0
    assert item.base_score == 0.0
    assert item.negative_penalty == 1.0
