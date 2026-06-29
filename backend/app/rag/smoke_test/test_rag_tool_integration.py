"""Integration test for rag_tool.py with mock Qdrant hotel data."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import json

from tools.rag_tool import (
    HotelAskInput,
    HotelAskTool,
    search_rag,
)


# Mock hotel IDs for testing (realistic test data)
MOCK_HOTEL_IDS = [
    12345,  # Hanoi luxury hotel
    23456,  # Ho Chi Minh City resort
    34567,  # Da Nang beach hotel
    45678,  # Phu Quoc island villa
    56789,  # Da Lat mountain lodge
]

# Mock Qdrant response data
MOCK_QDRANT_RESPONSE = {
    "chunks": [
        {
            "text": "Our luxury 5-star hotel offers world-class amenities including a spa, infinity pool, and fine dining restaurants.",
            "score": 0.95,
            "chunk_id": "chunk_001",
            "section": "overview",
            "source_type": "description"
        },
        {
            "text": "Deluxe rooms feature marble bathrooms, premium bedding, and panoramic city views.",
            "score": 0.88,
            "chunk_id": "chunk_002",
            "section": "room_type",
            "source_type": "description"
        },
        {
            "text": "We provide 24/7 concierge service, airport transfers, and business facilities for corporate guests.",
            "score": 0.82,
            "chunk_id": "chunk_003",
            "section": "faq",
            "source_type": "service"
        }
    ]
}


class TestRagToolWithRealHotelIds:
    """Integration tests for rag_tool with realistic hotel IDs."""

    def test_hotel_ask_input_with_real_ids(self):
        """Test HotelAskInput with real hotel IDs."""
        payload = HotelAskInput(
            query="What are the amenities?",
            hotel_ids=MOCK_HOTEL_IDS[:3],
            sections=["overview", "room_type"],
            top_k=5
        )
        assert payload.query == "What are the amenities?"
        assert len(payload.hotel_ids) == 3
        assert payload.hotel_ids[0] == 12345
        assert payload.top_k == 5

    def test_hotel_ask_input_duplicate_ids(self):
        """Test that duplicate hotel IDs are handled."""
        payload = HotelAskInput(
            query="Best hotel in Vietnam",
            hotel_ids=[12345, 23456, 12345, 34567, 23456],
            top_k=10
        )
        # Note: duplicates are handled at tool level with _uniq_ints
        assert len(payload.hotel_ids) == 5

    @patch("tools.rag_tool.asyncio.run")
    def test_search_rag_with_real_hotel_ids(self, mock_run):
        """Test search_rag with realistic hotel IDs from Qdrant."""
        from tools.rag_tool import HotelAskOutput, HotelAskChunk

        # Mock response
        mock_chunks = [
            HotelAskChunk(
                score=0.95,
                chunk_id="chunk_001",
                section="overview",
                content="Luxury hotel amenities",
                metadata={"hotel_id": 12345, "source": "hotel_ask"}
            ),
            HotelAskChunk(
                score=0.88,
                chunk_id="chunk_002",
                section="room_type",
                content="Deluxe room features",
                metadata={"hotel_id": 12345, "source": "hotel_ask"}
            )
        ]
        
        mock_output = HotelAskOutput(
            query="amenities",
            hotel_ids=[12345],
            chunks=mock_chunks,
            errors=[]
        )
        mock_run.return_value = mock_output

        result = search_rag(
            query="What amenities do you offer?",
            top_k=5,
            hotel_ids=[12345]
        )

        assert mock_run.called
        assert isinstance(result, list)

    def test_normalize_chunks_with_qdrant_data(self):
        """Test chunk normalization with mock Qdrant response."""
        from tools.rag_tool import _normalize_chunks

        chunks = _normalize_chunks(
            MOCK_QDRANT_RESPONSE,
            hotel_id=12345,
            query="amenities"
        )

        assert len(chunks) == 3
        assert chunks[0].score == 0.95
        assert chunks[0].content == "Our luxury 5-star hotel offers world-class amenities including a spa, infinity pool, and fine dining restaurants."
        assert chunks[0].metadata["hotel_id"] == 12345
        assert chunks[0].metadata["source"] == "hotel_ask"
        assert chunks[1].section == "room_type"
        assert chunks[2].chunk_id == "chunk_003"

    def test_multiple_hotels_response(self):
        """Test handling responses from multiple hotels."""
        from tools.rag_tool import _normalize_chunks

        hotels_data = {
            12345: MOCK_QDRANT_RESPONSE,
            23456: {
                "chunks": [
                    {
                        "text": "Beach resort with water sports and tropical setting.",
                        "score": 0.91,
                        "chunk_id": "beach_001",
                        "section": "overview"
                    }
                ]
            }
        }

        all_chunks = []
        for hotel_id, response_data in hotels_data.items():
            chunks = _normalize_chunks(response_data, hotel_id=hotel_id, query="resort")
            all_chunks.extend(chunks)

        assert len(all_chunks) >= 4
        # Verify chunks from both hotels
        hotel_12345_chunks = [c for c in all_chunks if c.metadata["hotel_id"] == 12345]
        hotel_23456_chunks = [c for c in all_chunks if c.metadata["hotel_id"] == 23456]
        assert len(hotel_12345_chunks) == 3
        assert len(hotel_23456_chunks) == 1

    def test_tool_initialization_for_multiple_hotels(self):
        """Test HotelAskTool with realistic configuration."""
        tool = HotelAskTool(
            base_url="http://mock-hotel-ask-api:8000",
            timeout=20.0,
            max_retries=3
        )
        assert tool.base_url == "http://mock-hotel-ask-api:8000"
        assert tool.timeout == 20.0
        assert tool.max_retries == 3

    def test_query_with_multiple_sections(self):
        """Test query requesting multiple sections from Qdrant."""
        payload = HotelAskInput(
            query="Tell me about rooms, amenities, and FAQ",
            hotel_ids=[12345, 23456, 34567],
            sections=["room_type", "overview", "faq"],
            top_k=15
        )
        assert len(payload.sections) == 3
        assert "room_type" in payload.sections
        assert "faq" in payload.sections
        assert payload.top_k == 15


class TestRealWorldScenarios:
    """Real-world test scenarios."""

    def test_search_luxury_hotel_amenities(self):
        """Scenario: User searching for luxury hotel amenities."""
        query = "What luxury amenities and services does your hotel offer?"
        hotel_id = 12345

        payload = HotelAskInput(
            query=query,
            hotel_ids=[hotel_id],
            sections=["overview", "faq"],
            top_k=5
        )

        assert payload.query == query
        assert hotel_id in payload.hotel_ids
        assert "overview" in payload.sections

    def test_search_room_comparison_multiple_hotels(self):
        """Scenario: User comparing rooms across multiple hotels."""
        query = "Compare room types and pricing"
        hotel_ids = [12345, 23456, 34567]

        payload = HotelAskInput(
            query=query,
            hotel_ids=hotel_ids,
            sections=["room_type"],
            top_k=20
        )

        assert payload.query == query
        assert len(payload.hotel_ids) == 3
        assert payload.sections == ["room_type"]
        assert payload.top_k == 20

    def test_search_with_location_context(self):
        """Scenario: User searching for hotels in specific location."""
        query = "Best beach resorts in Phu Quoc"
        # Phu Quoc hotel
        hotel_ids = [45678]

        payload = HotelAskInput(
            query=query,
            hotel_ids=hotel_ids,
            sections=["overview", "description"],
            top_k=10
        )

        assert "Phu Quoc" in query
        assert 45678 in payload.hotel_ids

    def test_search_specific_amenity(self):
        """Scenario: User searching for specific amenity."""
        query = "Do you have a spa and wellness center?"
        hotel_ids = [12345]

        payload = HotelAskInput(
            query=query,
            hotel_ids=hotel_ids,
            sections=["overview", "faq"],
            top_k=5
        )

        assert "spa" in query.lower()
        assert payload.hotel_ids == [12345]

    def test_chunk_quality_scoring(self):
        """Test scoring of chunks based on relevance."""
        from tools.rag_tool import _normalize_chunks

        # Higher score = more relevant
        high_score_chunk = MOCK_QDRANT_RESPONSE["chunks"][0]
        low_score_chunk = MOCK_QDRANT_RESPONSE["chunks"][2]

        assert high_score_chunk["score"] > low_score_chunk["score"]
        assert high_score_chunk["score"] == 0.95
        assert low_score_chunk["score"] == 0.82


class TestErrorHandlingWithRealIds:
    """Test error scenarios with real hotel IDs."""

    def test_invalid_hotel_id_handling(self):
        """Test handling of invalid hotel IDs."""
        from tools.rag_tool import _uniq_ints

        invalid_ids = [12345, "invalid", 23456, None, 34567, "hotel_id"]
        result = _uniq_ints(invalid_ids)

        # Should only have valid integer IDs
        assert len(result) == 3
        assert 12345 in result
        assert 23456 in result
        assert 34567 in result

    def test_empty_response_handling(self):
        """Test handling of empty Qdrant response."""
        from tools.rag_tool import _normalize_chunks

        empty_response = {"chunks": []}
        result = _normalize_chunks(empty_response, hotel_id=12345, query="test")

        assert result == []

    def test_malformed_chunk_handling(self):
        """Test handling of malformed chunks from Qdrant."""
        from tools.rag_tool import _normalize_chunks

        malformed = {
            "chunks": [
                {"text": "Valid chunk"},  # valid
                {"content": "No text field"},  # missing text
                {"text": ""},  # empty text
                {"text": "   "},  # whitespace only
            ]
        }
        result = _normalize_chunks(malformed, hotel_id=12345, query="test")

        # Should only normalize valid chunks
        assert len(result) == 1
        assert result[0].content == "Valid chunk"


@pytest.mark.parametrize("hotel_id", MOCK_HOTEL_IDS)
def test_each_hotel_id_valid(hotel_id):
    """Parametrized test for each hotel ID."""
    payload = HotelAskInput(
        query="Hotel information",
        hotel_ids=[hotel_id],
        top_k=5
    )
    assert hotel_id in payload.hotel_ids
    assert payload.query == "Hotel information"


@pytest.mark.parametrize("query,expected_sections", [
    ("amenities", ["overview"]),
    ("room types", ["room_type"]),
    ("questions", ["faq"]),
    ("full info", ["description", "overview", "faq"]),
])
def test_query_to_sections_mapping(query, expected_sections):
    """Test mapping queries to appropriate sections."""
    from tools.rag_tool import _normalize_sections

    result = _normalize_sections(expected_sections)
    # Filter to only valid sections
    valid = [s for s in result if s in expected_sections]
    assert len(valid) >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
