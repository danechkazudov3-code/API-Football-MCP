"""Tests for sidelined tool."""

import pytest
from tests.conftest import mock_httpx_response

import sys
sys.argv = ["test"]
from server import mcp, register_tools
register_tools()

from tools.sidelined import get_sidelined


@pytest.mark.asyncio
async def test_get_sidelined_by_player(mock_api):
    mock_api.return_value = mock_httpx_response(data=[
        {"type": "Knee Injury", "start": "2023-01-01", "end": "2023-03-15"},
    ])
    result = await get_sidelined(player=276)
    assert result["success"] is True


@pytest.mark.asyncio
async def test_get_sidelined_by_coaches_uses_correct_api_parameter(mock_api):
    mock_api.return_value = mock_httpx_response(data=[])
    result = await get_sidelined(coaches="2-6")
    assert result["success"] is True
    assert mock_api.await_args.kwargs["params"] == {"coaches": "2-6"}


@pytest.mark.asyncio
async def test_get_sidelined_missing_params(mock_api):
    result = await get_sidelined()
    assert result["success"] is False
    assert "At least one" in result["error"]
    mock_api.assert_not_awaited()
