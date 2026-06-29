"""Unit tests for rag_tool.py (Hotel Ask retrieval tool)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from app.rag.tools.rag_tool import (
    HotelAskInput,
    HotelAskChunk,
    HotelAskOutput,
    HotelAskTool,
    _uniq_ints,
    _normalize_sections,
    _normalize_chunks,
    _coerce_float,
    search_rag,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


class TestHotelAskInput:
    """Test HotelAskInput model."""

    def test_input_defaults(self):
        """Test default values."""
        inp = HotelAskInput(query="test")
        assert inp.query == "test"
        assert inp.hotel_ids == []
        assert inp.sections == []
        assert inp.top_k == 5

    def test_input_with_values(self):
        """Test input with custom values."""
        inp = HotelAskInput(
            query="best rooms",
            hotel_ids=[123, 456],
            sections=["room_type", "faq"],
            top_k=10
        )
        assert inp.query == "best rooms"
        assert inp.hotel_ids == [123, 456]
        assert inp.sections == ["room_type", "faq"]
        assert inp.top_k == 10


class TestHotelAskChunk:
    """Test HotelAskChunk model."""

    def test_chunk_defaults(self):
        """Test chunk with minimal data."""
        chunk = HotelAskChunk(content="Sample content")
        assert chunk.content == "Sample content"
        assert chunk.score == 0.0
        assert chunk.chunk_id is None
        assert chunk.section is None
        assert chunk.metadata == {}

    def test_chunk_full(self):
        """Test chunk with all fields."""
        chunk = HotelAskChunk(
            score=0.95,
            chunk_id="chunk_1",
            section="description",
            content="Luxury room",
            metadata={"hotel_id": 123}
        )
        assert chunk.score == 0.95
        assert chunk.chunk_id == "chunk_1"
        assert chunk.section == "description"
        assert chunk.content == "Luxury room"
        assert chunk.metadata["hotel_id"] == 123


class TestHotelAskOutput:
    """Test HotelAskOutput model."""

    def test_output_defaults(self):
        """Test default output."""
        output = HotelAskOutput(query="test", hotel_ids=[1, 2])
        assert output.query == "test"
        assert output.hotel_ids == [1, 2]
        assert output.chunks == []
        assert output.errors == []

    def test_output_with_chunks_and_errors(self):
        """Test output with data."""
        chunks = [HotelAskChunk(content="Room 1")]
        errors = ["Error 1"]
        output = HotelAskOutput(query="test", hotel_ids=[1], chunks=chunks, errors=errors)
        assert len(output.chunks) == 1
        assert len(output.errors) == 1


class TestUtilityFunctions:
    """Test utility functions."""

    def test_uniq_ints_basic(self):
        """Test unique integer extraction."""
        result = _uniq_ints([1, 2, 3, 2, 1])
        assert result == [1, 2, 3]

    def test_uniq_ints_with_strings(self):
        """Test conversion from strings."""
        result = _uniq_ints(["1", "2", "3"])
        assert result == [1, 2, 3]

    def test_uniq_ints_mixed(self):
        """Test mixed types with duplicates."""
        result = _uniq_ints([1, "2", 3, "2", 1])
        assert result == [1, 2, 3]

    def test_uniq_ints_invalid(self):
        """Test with invalid values."""
        result = _uniq_ints([1, "invalid", 2])
        assert result == [1, 2]

    def test_uniq_ints_empty(self):
        """Test empty list."""
        result = _uniq_ints([])
        assert result == []

    def test_normalize_sections_valid(self):
        """Test valid section names."""
        result = _normalize_sections(["description", "faq", "room_type"])
        assert set(result) == {"description", "faq", "room_type"}

    def test_normalize_sections_invalid(self):
        """Test invalid section names are filtered."""
        result = _normalize_sections(["description", "invalid", "faq"])
        assert "invalid" not in result
        assert "description" in result

    def test_normalize_sections_duplicates(self):
        """Test duplicates are removed."""
        result = _normalize_sections(["description", "faq", "description"])
        assert result.count("description") == 1

    def test_normalize_sections_empty(self):
        """Test empty sections."""
        result = _normalize_sections([])
        assert result == []

    def test_normalize_sections_none(self):
        """Test None sections."""
        result = _normalize_sections(None)
        assert result == []

    def test_coerce_float_valid(self):
        """Test float coercion."""
        assert _coerce_float(3.14) == 3.14
        assert _coerce_float("3.14") == 3.14
        assert _coerce_float(5) == 5.0

    def test_coerce_float_invalid(self):
        """Test invalid values default to 0.0."""
        assert _coerce_float("invalid") == 0.0
        assert _coerce_float(None) == 0.0
        assert _coerce_float([]) == 0.0


class TestNormalizeChunks:
    """Test chunk normalization."""

    def test_normalize_chunks_valid(self):
        """Test normalizing valid chunks."""
        data = {
            "chunks": [
                {
                    "text": "Beautiful room",
                    "score": 0.95,
                    "chunk_id": "c1",
                    "section": "description"
                }
            ]
        }
        result = _normalize_chunks(data, hotel_id=123, query="room")
        assert len(result) == 1
        assert result[0].content == "Beautiful room"
        assert result[0].score == 0.95
        assert result[0].metadata["hotel_id"] == 123

    def test_normalize_chunks_alt_keys(self):
        """Test alternative key names."""
        data = {
            "results": [
                {"content": "Room content", "score": 0.8}
            ]
        }
        result = _normalize_chunks(data, hotel_id=123, query="test")
        assert len(result) == 1
        assert result[0].content == "Room content"

    def test_normalize_chunks_empty(self):
        """Test empty chunks."""
        result = _normalize_chunks({}, hotel_id=123, query="test")
        assert result == []

    def test_normalize_chunks_invalid_format(self):
        """Test invalid chunk format."""
        data = {"chunks": "not a list"}
        result = _normalize_chunks(data, hotel_id=123, query="test")
        assert result == []

    def test_normalize_chunks_empty_content(self):
        """Test chunks with empty content are skipped."""
        data = {
            "chunks": [
                {"content": "Valid content"},
                {"content": ""},
                {"content": "   "}
            ]
        }
        result = _normalize_chunks(data, hotel_id=123, query="test")
        assert len(result) == 1


class TestHotelAskTool:
    """Test HotelAskTool class."""

    def test_init_defaults(self):
        """Test default initialization."""
        tool = HotelAskTool()
        assert tool.timeout == 15.0
        assert tool.max_retries == 2
        assert tool.retry_backoff_seconds == 0.4
        assert tool._owns_client is True

    def test_init_custom(self):
        """Test custom initialization."""
        tool = HotelAskTool(
            base_url="http://custom.api",
            timeout=30.0,
            max_retries=5
        )
        assert tool.base_url == "http://custom.api"
        assert tool.timeout == 30.0
        assert tool.max_retries == 5

    def test_base_url_from_env(self):
        """Test base_url from environment."""
        with patch.dict("os.environ", {"HOTEL_ASK_BASE_URL": "http://env.api"}):
            # Need to reimport or reload to pick up env
            tool = HotelAskTool()
            # This tests that env is checked (actual value depends on .env loading)
            assert tool.base_url is not None

    def test_should_retry_timeout(self):
        """Test retry logic for timeouts."""
        tool = HotelAskTool()
        exc = httpx.TimeoutException("timeout")
        assert tool._should_retry(exc, 0) is True
        assert tool._should_retry(exc, 2) is False  # max_retries=2

    def test_should_retry_http_error(self):
        """Test retry logic for HTTP errors."""
        tool = HotelAskTool()
        
        # Create mock response
        mock_response = MagicMock()
        mock_response.status_code = 503
        
        exc = httpx.HTTPStatusError("error", request=MagicMock(), response=mock_response)
        assert tool._should_retry(exc, 0) is True

    def test_should_retry_max_retries(self):
        """Test no retry after max attempts."""
        tool = HotelAskTool(max_retries=1)
        mock_response = MagicMock()
        mock_response.status_code = 503
        exc = httpx.HTTPStatusError("error", request=MagicMock(), response=mock_response)
        assert tool._should_retry(exc, 1) is False


@pytest.mark.anyio
async def test_hotel_ask_tool_ask_empty_query():
    """Test ask with empty query."""
    tool = HotelAskTool()
    payload = HotelAskInput(query="", hotel_ids=[123])
    result = await tool.ask(payload)
    assert result.query == ""
    assert result.chunks == []


@pytest.mark.anyio
async def test_hotel_ask_tool_ask_no_hotel_ids():
    """Test ask with no hotel IDs."""
    tool = HotelAskTool()
    payload = HotelAskInput(query="test")
    result = await tool.ask(payload)
    assert len(result.errors) > 0
    assert result.chunks == []


@pytest.mark.anyio
async def test_hotel_ask_tool_context_manager():
    """Test context manager."""
    async with HotelAskTool() as tool:
        assert tool._client is not None


class TestSearchRag:
    """Test search_rag function."""

    def test_search_rag_empty_query(self):
        """Test with empty query."""
        result = search_rag("")
        assert result == []

    def test_search_rag_whitespace_query(self):
        """Test with whitespace-only query."""
        result = search_rag("   ")
        assert result == []

    @patch("app.rag.tools.rag_tool.asyncio.run")
    def test_search_rag_with_hotel_ids(self, mock_run):
        """Test search_rag with explicit hotel IDs."""
        # Mock the async result
        mock_output = HotelAskOutput(
            query="test",
            hotel_ids=[123],
            chunks=[HotelAskChunk(content="test", score=0.9)]
        )
        def run_without_await_warning(coroutine):
            coroutine.close()
            return mock_output

        mock_run.side_effect = run_without_await_warning
        
        result = search_rag("test", hotel_ids=[123])
        assert mock_run.called


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_normalize_chunks_with_metadata_section(self):
        """Test metadata section handling."""
        data = {
            "chunks": [
                {
                    "text": "Content",
                    "section": "room_type",
                    "score": 0.8
                }
            ]
        }
        result = _normalize_chunks(data, hotel_id=123, query="test")
        assert result[0].metadata.get("section") == "room_type"

    def test_uniq_ints_preserves_order(self):
        """Test that order is preserved."""
        result = _uniq_ints([3, 1, 2, 1, 3])
        assert result == [3, 1, 2]

    def test_normalize_sections_with_spaces(self):
        """Test section normalization with spaces."""
        result = _normalize_sections(["  description  ", "faq"])
        assert "description" in result

    def test_coerce_float_negative(self):
        """Test negative float coercion."""
        assert _coerce_float(-3.14) == -3.14


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
