import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from slack_sdk.errors import SlackApiError
from ossai.decorators import safe_slack_api_call


@pytest.mark.asyncio
async def test_safe_slack_api_call_happy_path():
    # Setup
    client = MagicMock()
    mock_func = AsyncMock()
    mock_func.return_value = "Success"
    decorated_func = safe_slack_api_call(mock_func)

    # Create a mock payload with channel_id and a mock ack function
    mock_payload = {"channel_id": "C123"}
    mock_ack = AsyncMock()

    # Execute
    result = await decorated_func(
        client, mock_ack, mock_payload, user_id="U123", arg1="test", arg2=123
    )

    # Verify
    assert result == "Success"
    mock_func.assert_called_once_with(
        client, mock_ack, mock_payload, user_id="U123", arg1="test", arg2=123
    )
    assert mock_payload["channel_id"] == "C123"
    client.chat_postEphemeral.assert_not_called()


@pytest.mark.asyncio
@patch("ossai.decorators.logger")
async def test_safe_slack_api_call_error_handling(mock_logger):
    # Setup
    client = MagicMock()
    mock_func = AsyncMock()
    mock_func.side_effect = SlackApiError(
        message="Pineapple on pizza error", response={"error": "API error"}
    )
    decorated_func = safe_slack_api_call(mock_func)

    # Create a mock payload with channel_id and a mock ack function
    mock_payload = {"channel_id": "C123"}
    mock_ack = AsyncMock()

    # Execute
    await decorated_func(
        client, mock_ack, mock_payload, user_id="U123", arg1="test", arg2=123
    )

    # Verify
    client.chat_postEphemeral.assert_called_once()
    call_args = client.chat_postEphemeral.call_args
    assert call_args.kwargs["channel"] == "C123"
    assert call_args.kwargs["user"] == "U123"
    assert (
        "Sorry, an unexpected error occurred. `API error`" in call_args.kwargs["text"]
    )
    assert "Pineapple on pizza error" in call_args.kwargs["text"]

    mock_logger.error.assert_called()
    log_message = mock_logger.error.call_args.args[0]
    assert "[Slack API error]" in log_message
    assert "Pineapple on pizza error" in log_message
    assert "Message sent to user" in mock_logger.error.call_args_list[1].args[0]
