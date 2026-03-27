import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from ossai import slack_context
from ossai.decorators.catch_error_dm_user import (
    catch_errors_dm_user,
    _handle_slack_api_error,
    _send_error_message,
    SlackPayload,
)
from ossai.slack_context import SlackContext


@pytest.mark.asyncio
async def test_catch_errors_dm_user_happy_path():
    # Setup
    slack_context = AsyncMock(spec=SlackContext)
    slack_context.client = AsyncMock(spec=WebClient)
    mock_func = AsyncMock()
    mock_func.return_value = "Success"
    decorated_func = catch_errors_dm_user(mock_func)

    # Create a mock payload with channel_id and a mock ack function
    mock_payload = {"channel_id": "C123", "user_id": "U123"}
    mock_ack = AsyncMock()

    # Execute
    result = await decorated_func(
        slack_context, mock_ack, mock_payload, user_id="U123", arg1="test", arg2=123
    )

    # Verify
    assert result == "Success"
    mock_func.assert_called_once_with(
        slack_context, mock_ack, mock_payload, user_id="U123", arg1="test", arg2=123
    )
    assert mock_payload["channel_id"] == "C123"
    slack_context.client.chat_postEphemeral.assert_not_called()


@pytest.mark.asyncio
@patch("ossai.decorators.catch_error_dm_user.logger")
async def test_catch_errors_dm_user_error_handling(mock_logger):
    # Setup
    slack_context = AsyncMock(spec=SlackContext)
    slack_context.client = AsyncMock(spec=WebClient)
    mock_func = AsyncMock()
    mock_func.side_effect = SlackApiError(
        message="Pineapple on pizza error", response={"error": "API error"}
    )
    decorated_func = catch_errors_dm_user(mock_func)

    slack_context.client.chat_postEphemeral = AsyncMock()

    # Create a mock payload with channel_id and a mock ack function
    mock_payload = {"channel_id": "C123", "user_id": "U123"}
    mock_ack = AsyncMock()

    # Execute
    await decorated_func(
        slack_context, mock_ack, mock_payload, user_id="U123", arg1="test", arg2=123
    )

    # Verify
    slack_context.client.chat_postEphemeral.assert_called_once()
    call_args = slack_context.client.chat_postEphemeral.call_args
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


@pytest.mark.asyncio
@pytest.mark.parametrize("error_code", ["not_in_channel", "channel_not_found"])
async def test_handle_slack_api_error_channel_error_branch(error_code):
    """not_in_channel and channel_not_found route through _handle_channel_error and mention the bot by name."""
    mock_context = AsyncMock(spec=SlackContext)
    mock_context.client = AsyncMock(spec=WebClient)
    mock_context.get_direct_message_channel_id = AsyncMock(return_value="DM123")
    mock_context.get_bot_id = AsyncMock(return_value="B123")
    mock_context.client.bots_info = MagicMock(return_value={"bot": {"name": "MyBot"}})
    mock_context.client.chat_postEphemeral = AsyncMock()

    payload = SlackPayload(user_id="U123", channel_id="C123")
    error = SlackApiError("error", {"error": error_code, "headers": {}})

    await _handle_slack_api_error(mock_context, payload, {"user_id": "U123", "channel_id": "C123"}, error)

    mock_context.client.chat_postEphemeral.assert_called_once()
    call_kwargs = mock_context.client.chat_postEphemeral.call_args.kwargs
    assert call_kwargs["channel"] == "DM123"
    assert call_kwargs["user"] == "U123"
    assert "@MyBot" in call_kwargs["text"]


@pytest.mark.asyncio
async def test_handle_slack_api_error_generic_error_branch():
    """Generic Slack errors post to the original channel (not DM) with the error code in the message."""
    mock_context = AsyncMock(spec=SlackContext)
    mock_context.client = AsyncMock(spec=WebClient)
    mock_context.client.chat_postEphemeral = AsyncMock()

    payload = SlackPayload(user_id="U123", channel_id="C123")
    error = SlackApiError("ratelimited", {"error": "ratelimited", "headers": {}})

    await _handle_slack_api_error(mock_context, payload, {"user_id": "U123", "channel_id": "C123"}, error)

    mock_context.client.chat_postEphemeral.assert_called_once()
    call_kwargs = mock_context.client.chat_postEphemeral.call_args.kwargs
    assert call_kwargs["channel"] == "C123"
    assert "ratelimited" in call_kwargs["text"]
    mock_context.get_direct_message_channel_id.assert_not_called()


@pytest.mark.asyncio
@patch("ossai.decorators.catch_error_dm_user.logger")
async def test_send_error_message_exception_is_swallowed(mock_logger):
    """When chat_postEphemeral itself raises, _send_error_message logs and does not re-raise."""
    mock_client = AsyncMock(spec=WebClient)
    mock_client.chat_postEphemeral.side_effect = Exception("network failure")

    # Should not raise
    await _send_error_message(mock_client, "C123", "U123", "TestError", "error message")

    assert mock_logger.error.called
    error_log = mock_logger.error.call_args.args[0]
    assert "All hope is lost" in error_log
