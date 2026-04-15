"""Tests for the AI hazard classifier module."""

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from classifier import (
    CONFIDENCE_THRESHOLD,
    _keyword_fallback,
    _parse_llm_response,
    _strip_markdown_fences,
    classify_post,
)

# Dummy request for httpx.Response (required by raise_for_status)
_DUMMY_REQUEST = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")


# ── Keyword fallback tests ────────────────────────────────────────────
class TestKeywordFallback:
    def test_flood_detected(self) -> None:
        result = _keyword_fallback("Waist-deep water flooding the underpass")
        assert result["is_hazard"] is True
        assert result["category"] == "Flood"
        assert result["severity"] == "HIGH"

    def test_accident_detected(self) -> None:
        result = _keyword_fallback("Major crash near the junction, two cars collided")
        assert result["is_hazard"] is True
        assert result["category"] == "Accident"

    def test_benign_text(self) -> None:
        result = _keyword_fallback("Beautiful morning, roads are clear and sunny")
        assert result["is_hazard"] is False
        assert result["category"] == "None"

    def test_returns_correct_schema(self) -> None:
        result = _keyword_fallback("Gas leak near the school")
        assert set(result.keys()) == {"is_hazard", "category", "severity", "confidence"}
        assert isinstance(result["confidence"], float)


# ── Markdown stripping tests ──────────────────────────────────────────
class TestMarkdownStripping:
    def test_strips_json_fences(self) -> None:
        raw = '```json\n{"is_hazard": true}\n```'
        assert _strip_markdown_fences(raw) == '{"is_hazard": true}'

    def test_strips_plain_fences(self) -> None:
        raw = '```\n{"key": "val"}\n```'
        assert _strip_markdown_fences(raw) == '{"key": "val"}'

    def test_no_fences_unchanged(self) -> None:
        raw = '{"key": "val"}'
        assert _strip_markdown_fences(raw) == raw


# ── LLM response parsing tests ───────────────────────────────────────
class TestParseResponse:
    def test_valid_json(self) -> None:
        raw = '{"is_hazard": true, "category": "Flood", "severity": "HIGH", "confidence": 0.9}'
        result = _parse_llm_response(raw)
        assert result is not None
        assert result["category"] == "Flood"

    def test_invalid_json_returns_none(self) -> None:
        assert _parse_llm_response("not json at all") is None

    def test_with_markdown_fences(self) -> None:
        raw = '```json\n{"is_hazard": false, "category": "None", "severity": "LOW", "confidence": 0.95}\n```'
        result = _parse_llm_response(raw)
        assert result is not None
        assert result["is_hazard"] is False


# ── classify_post integration tests ──────────────────────────────────
class TestClassifyPost:
    @pytest.mark.asyncio
    async def test_hazard_with_groq_mock(self) -> None:
        """Mock a successful Groq API call returning a hazard."""
        groq_response = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "is_hazard": True,
                                "category": "Flood",
                                "severity": "HIGH",
                                "confidence": 0.91,
                            }
                        )
                    }
                }
            ]
        }
        mock_response = httpx.Response(200, json=groq_response, request=_DUMMY_REQUEST)

        with patch.dict("os.environ", {"GROQ_API_KEY": "test-key"}):
            with patch("classifier.httpx.AsyncClient") as MockClient:
                instance = AsyncMock()
                instance.post.return_value = mock_response
                instance.__aenter__ = AsyncMock(return_value=instance)
                instance.__aexit__ = AsyncMock(return_value=False)
                MockClient.return_value = instance

                result = await classify_post("Massive flooding at the junction")

        assert result is not None
        assert result["is_hazard"] is True
        assert result["category"] == "Flood"

    @pytest.mark.asyncio
    async def test_benign_with_groq_mock(self) -> None:
        """Mock a Groq call that classifies as non-hazard."""
        groq_response = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "is_hazard": False,
                                "category": "None",
                                "severity": "LOW",
                                "confidence": 0.92,
                            }
                        )
                    }
                }
            ]
        }
        mock_response = httpx.Response(200, json=groq_response, request=_DUMMY_REQUEST)

        with patch.dict("os.environ", {"GROQ_API_KEY": "test-key"}):
            with patch("classifier.httpx.AsyncClient") as MockClient:
                instance = AsyncMock()
                instance.post.return_value = mock_response
                instance.__aenter__ = AsyncMock(return_value=instance)
                instance.__aexit__ = AsyncMock(return_value=False)
                MockClient.return_value = instance

                result = await classify_post("Roads are clear today")

        assert result is not None
        assert result["is_hazard"] is False

    @pytest.mark.asyncio
    async def test_groq_failure_uses_fallback(self) -> None:
        """When Groq fails, keyword fallback should still work."""
        with patch.dict("os.environ", {"GROQ_API_KEY": "test-key"}):
            with patch("classifier.httpx.AsyncClient") as MockClient:
                instance = AsyncMock()
                instance.post.side_effect = httpx.ConnectError("connection refused")
                instance.__aenter__ = AsyncMock(return_value=instance)
                instance.__aexit__ = AsyncMock(return_value=False)
                MockClient.return_value = instance

                result = await classify_post("Massive flooding in the area")

        assert result is not None
        assert result["category"] == "Flood"

    @pytest.mark.asyncio
    async def test_low_confidence_rejected(self) -> None:
        """Results with confidence below threshold should return None."""
        groq_response = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "is_hazard": True,
                                "category": "Traffic",
                                "severity": "LOW",
                                "confidence": 0.3,
                            }
                        )
                    }
                }
            ]
        }
        mock_response = httpx.Response(200, json=groq_response, request=_DUMMY_REQUEST)

        with patch.dict("os.environ", {"GROQ_API_KEY": "test-key"}):
            with patch("classifier.httpx.AsyncClient") as MockClient:
                instance = AsyncMock()
                instance.post.return_value = mock_response
                instance.__aenter__ = AsyncMock(return_value=instance)
                instance.__aexit__ = AsyncMock(return_value=False)
                MockClient.return_value = instance

                result = await classify_post("Slight traffic nearby")

        assert result is None

    @pytest.mark.asyncio
    async def test_no_api_key_uses_fallback(self) -> None:
        """When GROQ_API_KEY is empty, classifier uses keyword fallback."""
        with patch.dict("os.environ", {"GROQ_API_KEY": ""}, clear=False):
            result = await classify_post("Tree fell on the road blocking traffic")
        assert result is not None
        assert result["category"] == "Obstruction"
