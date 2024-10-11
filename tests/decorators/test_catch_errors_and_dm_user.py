import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from ossai import slack_context
from ossai.decorators.catch_error_dm_user import catch_errors_dm_user
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
