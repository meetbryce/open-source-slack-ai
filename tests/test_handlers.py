from unittest.mock import AsyncMock, MagicMock, patch
import uuid
import pytest
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from datetime import datetime, timezone
from ossai.slack_context import SlackContext

from ossai.handlers import (
    handler_sandbox_slash_command,
    handler_shortcuts,
    handler_tldr_extended_slash_command,
    handler_topics_slash_command,
    handler_feedback,
    handler_action_summarize_since_date,
    handler_tldr_since_slash_command,
)


@pytest.fixture
def mock_slack_context():
    mock = MagicMock(spec=SlackContext)
    mock.get_bot_id = AsyncMock(return_value="B12345")
    mock.get_channel_history = AsyncMock(return_value=[])
    mock.get_direct_message_channel_id = AsyncMock(return_value="D12345")
    mock.get_is_private_and_channel_name = MagicMock(return_value=(False, "general"))
    mock.get_name_from_id = MagicMock(return_value="John Doe")
    mock.get_parsed_messages = MagicMock(return_value=["John: Hello", "Jane: Hi"])
    mock.get_user_context = AsyncMock(return_value={"name": "John", "title": "Developer"})
    mock.get_workspace_name = MagicMock(return_value="My Workspace")
    mock.client = AsyncMock(spec=WebClient)
    return mock


@pytest.fixture
def client():
    return WebClient()


@pytest.fixture
def payload():
    return {
        "channel": {"id": "channel_id"},
        "user_id": "user_id",
        "message_ts": "message_ts",
        "channel_name": "channel_name",
        "channel_id": "channel_id",
        "text": "text",
    }


@pytest.fixture
def shortcuts_payload():
    return {
        "type": "message_action",
        "token": "tokentokentoken",
        "action_ts": "1724891107.611566",
        "user": {
            "id": "U077J8M90AG",
            "username": "bryce",
            "team_id": "T077UE5VA3B",
            "name": "bryce",
        },
        "channel": {"id": "channel_id", "name": "channel_name"},
        "callback_id": "thread_private",
        "message_ts": "message_ts",
    }


@pytest.fixture
def say(**kwargs):
    async def custom_say(**kwargs):
        blocks = kwargs.get("blocks", [])
        for block in blocks:
            if block["type"] == "section" and len(block["text"]["text"]) > 3000:
                error_response = {
                    "ok": False,
                    "error": "invalid_blocks",
                    "errors": [
                        "failed to match all allowed schemas [json-pointer:/blocks/0/text]",
                        f"must be less than 3001 characters [json-pointer:/blocks/0/text/text]",
                    ],
                }
                raise SlackApiError(
                    "The request to the Slack API failed.", response=error_response
                )
        return {"ok": True, "message": {"ts": "1234567890.123456"}}

    return AsyncMock(side_effect=custom_say)


@pytest.mark.asyncio
async def test_handler_shortcuts(
    mock_slack_context, payload, say
):
    mock_slack_context.client.get_direct_message_channel_id.return_value = "dm_channel_id"
    await handler_shortcuts(mock_slack_context, True, payload, say, user_id="foo123")
    say.assert_called()


@pytest.mark.asyncio
async def test_handler_tldr_extended_slash_command_channel_history_error(
    mock_slack_context, payload, say
):
    mock_slack_context.get_direct_message_channel_id.return_value = "dm_channel_id"
    await handler_tldr_extended_slash_command(
        mock_slack_context, AsyncMock(), payload, say, user_id="foo123"
    )
    say.assert_called()


@pytest.mark.asyncio
@patch("ossai.handlers.analyze_topics_of_history")
async def test_handler_topics_slash_command(
    analyze_topics_of_history_mock,
    mock_slack_context,
    payload,
    say,
):
    mock_slack_context.get_direct_message_channel_id.return_value = "dm_channel_id"
    mock_slack_context.get_channel_history.return_value = ["message1", "message2", "message3"]
    mock_slack_context.get_parsed_messages.return_value = "parsed_messages"
    analyze_topics_of_history_mock.return_value = ("topic_overview", str(uuid.uuid4()))
    await handler_topics_slash_command(
        mock_slack_context, AsyncMock(), payload, say, user_id="foo123"
    )
    say.assert_called()


@pytest.mark.asyncio
@patch("ossai.handlers.Summarizer")
async def test_handler_shortcuts(
    summarizer_mock,
    mock_slack_context,
    shortcuts_payload,
    say,
):
    # Arrange
    run_id = str(uuid.uuid4())
    mock_slack_context.get_direct_message_channel_id.return_value = "dm_channel_id"
    mock_slack_context.client.conversations_replies.return_value = {
        "ok": True,
        "messages": [{"text": "test message"}],
    }
    mock_slack_context.get_workspace_name.return_value = "workspace_name"
    mock_slack_context.get_user_context.return_value = {"user": "info"}

    # Mock Summarizer instance
    summarizer_instance_mock = summarizer_mock.return_value
    summarizer_instance_mock.summarize_slack_messages.return_value = (["summary"], run_id)

    expected_blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Summary of <https://workspace_name.slack.com/archives/channel_id/pmessage_ts|message>:*\n>test message\n",
            },
        },
        {"type": "section", "text": {"type": "mrkdwn", "text": "summary"}},
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":-1: Not Helpful"},
                    "action_id": "not_helpful_button",
                    "value": run_id,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":+1: Helpful"},
                    "action_id": "helpful_button",
                    "value": run_id,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":tada: Very Helpful"},
                    "action_id": "very_helpful_button",
                    "value": run_id,
                },
            ],
        },
    ]

    # Act
    await handler_shortcuts(mock_slack_context, True, shortcuts_payload, say, user_id="foo123")

    # Assert
    say.assert_called_with(
        channel="dm_channel_id", text="summary", blocks=expected_blocks
    )
    summarizer_mock.assert_called_once()
    summarizer_instance_mock.summarize_slack_messages.assert_called_once_with(
        [{"text": "test message"}],
        "channel_id",
        feature_name="summarize_thread",
        user={"user": "info"},
    )
    mock_slack_context.get_user_context.assert_called_once_with("foo123")


@pytest.mark.asyncio
async def test_handler_tldr_extended_slash_command_public(
    mock_slack_context, say
):
    mock_slack_context.get_direct_message_channel_id.return_value = "dm_channel_id"
    payload = {
        "text": "public",
        "channel_name": "channel_name",
        "channel_id": "channel_id",
        "user_id": "user_id",
    }
    await handler_tldr_extended_slash_command(
        mock_slack_context, AsyncMock(), payload, say, user_id="foo123"
    )
    say.assert_called()


@patch("ossai.handlers.Client")
@patch("os.environ.get")
def test_handler_feedback_not_helpful_button(env_get_mock, client_mock):
    # Arrange
    env_get_mock.return_value = "test_project_id"
    client_instance = client_mock.return_value
    body = {"actions": [{"value": "1234", "action_id": "not_helpful_button"}]}

    # Act
    handler_feedback(body)

    # Assert
    client_instance.create_feedback.assert_called_once_with(
        "1234",
        project_id="test_project_id",
        key="user_feedback",
        score=-1.0,
        comment="Feedback from action: not_helpful_button",
    )


@patch("ossai.handlers.Client")
@patch("os.environ.get")
def test_handler_feedback_helpful_button(env_get_mock, client_mock):
    # Arrange
    env_get_mock.return_value = "test_project_id"
    client_instance = client_mock.return_value
    body = {"actions": [{"value": "1234", "action_id": "helpful_button"}]}

    # Act
    handler_feedback(body)

    # Assert
    client_instance.create_feedback.assert_called_once_with(
        "1234",
        project_id="test_project_id",
        key="user_feedback",
        score=1.0,
        comment="Feedback from action: helpful_button",
    )


@patch("ossai.handlers.Client")
@patch("os.environ.get")
def test_handler_feedback_very_helpful_button(env_get_mock, client_mock):
    # Arrange
    env_get_mock.return_value = "test_project_id"
    client_instance = client_mock.return_value
    body = {"actions": [{"value": "1234", "action_id": "very_helpful_button"}]}

    # Act
    handler_feedback(body)

    # Assert
    client_instance.create_feedback.assert_called_once_with(
        "1234",
        project_id="test_project_id",
        key="user_feedback",
        score=2.0,
        comment="Feedback from action: very_helpful_button",
    )


@pytest.mark.asyncio
async def test_handler_shortcuts_channel_not_found_error(
    mock_slack_context,
):
    # Setup
    mock_slack_context.client.bots_info.return_value = {"bot": {"name": "TestBot"}}
    say = AsyncMock()
    mock_slack_context.get_direct_message_channel_id.return_value = "DM123"
    mock_slack_context.get_bot_id.return_value = "B123"
    mock_slack_context.client.conversations_replies.side_effect = SlackApiError(
        message="channel_not_found", response={"error": "channel_not_found"}
    )

    # Execute
    await handler_shortcuts(
        mock_slack_context,
        False,
        {
            "channel": {"id": "C123"},
            "user": {"id": "U123"},
            "message_ts": "1234567890.123456",
        },
        say=say,
        user_id="U123",
    )

    # Verify
    mock_slack_context.get_direct_message_channel_id.assert_called_with("U123")
    mock_slack_context.client.chat_postEphemeral.assert_called_once_with(
        channel="DM123",
        user="U123",
        text="Sorry, couldn't find the channel. Have you added `@TestBot` to the channel?",
    )


@pytest.mark.asyncio
@patch("ossai.handlers.Summarizer")
@patch("ossai.handlers.get_text_and_blocks_for_say")
async def test_handler_tldr_extended_slash_command_non_public(
    get_text_and_blocks_for_say_mock,
    summarizer_mock,
    mock_slack_context,
):
    # Setup
    say = AsyncMock()
    mock_slack_context.get_direct_message_channel_id.return_value = "DM123"
    mock_slack_context.get_channel_history.return_value = ["message1", "message2"]
    mock_slack_context.get_user_context.return_value = {"user": "info"}
    
    summarizer_instance_mock = summarizer_mock.return_value
    summarizer_instance_mock.summarize_slack_messages.return_value = ("summary", "run_id")
    
    get_text_and_blocks_for_say_mock.return_value = ("text", "blocks")

    # Execute
    await handler_tldr_extended_slash_command(
        mock_slack_context,
        AsyncMock(),
        {
            "channel_name": "general",
            "channel_id": "C123",
            "user_id": "U123",
        },
        say,
        "U123",
    )

    # Verify
    assert say.call_count == 2
    say.assert_called_with(channel="DM123", text="text", blocks="blocks")
    mock_slack_context.get_direct_message_channel_id.assert_called_once_with("U123")
    summarizer_mock.assert_called_once()
    summarizer_instance_mock.summarize_slack_messages.assert_called_once_with(
        ["message2", "message1"],
        "C123",
        feature_name="summarize_channel_messages",
        user={"user": "info"},
    )



@pytest.mark.asyncio
@patch("ossai.handlers.datetime")
@patch("ossai.handlers.Summarizer")
@patch("ossai.handlers.get_text_and_blocks_for_say")
@patch("aiohttp.ClientSession.post", new_callable=AsyncMock)
async def test_handler_action_summarize_since_date(
    mock_post,
    get_text_and_blocks_for_say_mock,
    summarizer_mock,
    datetime_mock,
    mock_slack_context,
):
    # Setup
    ack = AsyncMock()
    body = {
        "channel": {"name": "general", "id": "C123"},
        "user": {"id": "U123"},
        "actions": [
            {
                "action_id": "summarize_since_preset",
                "selected_option": {"value": "1676955600"},
            }
        ],
        "response_url": "http://example.com/response",
    }
    mock_slack_context.get_direct_message_channel_id.return_value = "DM123"
    mock_slack_context.get_channel_history.return_value = ["message1", "message2"]
    mock_slack_context.get_user_context.return_value = {"user": "info"}
    
    summarizer_instance_mock = summarizer_mock.return_value
    summarizer_instance_mock.summarize_slack_messages.return_value = ("summary", "run_id")
    
    get_text_and_blocks_for_say_mock.return_value = ("text", "blocks")

    # Mock datetime to return a fixed date
    mocked_date = datetime(2023, 2, 21, tzinfo=timezone.utc)
    datetime_mock.fromtimestamp.return_value = mocked_date

    # Execute
    await handler_action_summarize_since_date(mock_slack_context, ack, body)

    # Verify
    ack.assert_called_once()
    mock_slack_context.get_direct_message_channel_id.assert_called_once_with("U123")
    datetime_mock.fromtimestamp.assert_called_once_with(1676955600)
    mock_slack_context.get_channel_history.assert_called_once_with(
        "C123", since=mocked_date.date()
    )
    mock_slack_context.get_user_context.assert_called_once_with("U123")
    summarizer_mock.assert_called_once()
    summarizer_instance_mock.summarize_slack_messages.assert_called_once_with(
        ["message2", "message1"],
        "C123",
        feature_name="summarize_since_preset",
        user={"user": "info"},
    )
    get_text_and_blocks_for_say_mock.assert_called_once_with(
        title="*Summary of #general* since Tuesday Feb 21, 2023 (2 messages)\n",
        run_id="run_id",
        messages="summary",
        custom_prompt=None,
    )
    mock_slack_context.client.chat_postMessage.assert_called_with(
        channel="DM123", text="text", blocks="blocks"
    )
    mock_post.assert_called_once_with(
        "http://example.com/response", json={"delete_original": "true"}
    )

@pytest.mark.asyncio
@patch("ossai.handlers.get_since_timeframe_presets")
async def test_handler_tldr_since_slash_command_happy_path(
    get_since_timeframe_presets_mock,
    mock_slack_context,
):
    # Setup
    say = AsyncMock()
    payload = {"user_id": "U123", "channel_id": "C123", "channel_name": "general"}
    get_since_timeframe_presets_mock.return_value = {"foo": "bar"}
    mock_slack_context.get_direct_message_channel_id.return_value = "DM123"
    ack = AsyncMock()

    # Execute
    await handler_tldr_since_slash_command(mock_slack_context, ack, payload, say)

    # Verify
    ack.assert_called_once()
    mock_slack_context.client.chat_postEphemeral.assert_called_once_with(
        channel="C123",
        user="U123",
        text="Choose your summary timeframe.",
        blocks=[
            {
                "type": "actions",
                "elements": [
                    {"foo": "bar"},
                    {
                        "type": "datepicker",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Select a date",
                            "emoji": True,
                        },
                        "action_id": "summarize_since",
                    },
                ],
            }
        ],
    )
    say.assert_called_once_with(
        channel="DM123",
        text="In #general, choose a date or timeframe to get your summary",
    )


@pytest.mark.asyncio
async def test_handlers_bot_not_in_channel(
    mock_slack_context
) -> None:
    USER_ID = "U123"
    CHANNEL_ID = "C123"
    DM_CHANNEL_ID = "DM123"

    mock_slack_context.client.bots_info.return_value = {"bot": {"name": "TestBot"}}
    say = AsyncMock()
    ack = AsyncMock()
    mock_slack_context.get_direct_message_channel_id.return_value = DM_CHANNEL_ID
    mock_slack_context.get_bot_id.return_value = "B123"

    handlers_to_test = [
        (
            handler_shortcuts,
            (
                mock_slack_context,
                False,
                {
                    "channel": {"id": CHANNEL_ID},
                    "user": {"id": USER_ID},
                    "message_ts": "1234567890.123456",
                },
                say,
                USER_ID,
            ),
        ),
        (
            handler_tldr_since_slash_command,
            (
                mock_slack_context,
                ack,
                {
                    "user_id": USER_ID,
                    "channel_id": CHANNEL_ID,
                    "channel_name": "general",
                },
                say,
            ),
        ),
        (
            handler_sandbox_slash_command,
            (
                mock_slack_context,
                ack,
                {
                    "user_id": USER_ID,
                    "channel_id": CHANNEL_ID,
                    "channel_name": "general",
                },
                say,
                USER_ID,
            ),
        ),
        (
            handler_action_summarize_since_date,
            (
                mock_slack_context,
                ack,
                {
                    "channel": {"name": "general", "id": CHANNEL_ID},
                    "user": {"id": USER_ID},
                    "actions": [
                        {
                            "action_id": "summarize_since_preset",
                            "selected_option": {"value": "1676955600"},
                        }
                    ],
                    "response_url": "http://example.com/response",
                },
            ),
        ),
        (
            handler_topics_slash_command,
            (
                mock_slack_context,
                ack,
                {
                    "user_id": USER_ID,
                    "channel_id": CHANNEL_ID,
                    "channel_name": "general",
                },
                say,
                USER_ID,
            ),
        ),
        (
            handler_tldr_extended_slash_command,
            (
                mock_slack_context,
                ack,
                {
                    "user_id": USER_ID,
                    "channel_id": CHANNEL_ID,
                    "channel_name": "general",
                    "text": "",
                },
                say,
                USER_ID,
            ),
        ),
    ]

    for handler, args in handlers_to_test:
        mock_slack_context.client.reset_mock()
        say.reset_mock()
        ack.reset_mock()

        mock_slack_context.client.conversations_replies.side_effect = SlackApiError(
            message="channel_not_found", response={"error": "channel_not_found"}
        )
        mock_slack_context.client.chat_postEphemeral.side_effect = SlackApiError(
            message="channel_not_found", response={"error": "channel_not_found"}
        )
        mock_slack_context.client.conversations_history.side_effect = SlackApiError(
            message="channel_not_found", response={"error": "channel_not_found"}
        )
        mock_slack_context.client.chat_postMessage.side_effect = SlackApiError(
            message="channel_not_found", response={"error": "channel_not_found"}
        )
        say.side_effect = SlackApiError(
            message="channel_not_found", response={"error": "channel_not_found"}
        )

        await handler(*args)

        error_message = "Sorry, couldn't find the channel. Have you added `@TestBot` to the channel?"

        mock_slack_context.client.chat_postEphemeral.assert_called_with(
            channel=DM_CHANNEL_ID, user=USER_ID, text=error_message
        )

        mock_slack_context.client.conversations_replies.side_effect = None
        mock_slack_context.client.chat_postEphemeral.side_effect = None
        mock_slack_context.client.conversations_history.side_effect = None
        say.side_effect = None


@pytest.mark.asyncio
async def test_handler_sandbox_slash_command_happy_path(mock_slack_context):
    ack = AsyncMock()
    say = AsyncMock()
    payload = {"user_id": "U123", "channel_id": "C123", "channel_name": "general"}

    await handler_sandbox_slash_command(mock_slack_context, ack, payload, say, user_id="foo123")
    say.assert_called_once()
    assert any(
        "This is a test of the /sandbox command." in str(block)
        for block in say.call_args[1]["blocks"]
    )
