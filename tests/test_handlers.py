from unittest.mock import AsyncMock, patch

import pytest
from slack_sdk import WebClient

from hackathon_2023.handlers import (
    handler_shortcuts,
    handler_tldr_slash_command,
    handler_topics_slash_command,
)


@pytest.fixture
def client():
    return WebClient()


@pytest.fixture
def payload():
    return {
        "channel": {"id": "channel_id"},
        "message_ts": "message_ts",
        "channel_name": "channel_name",
        "channel_id": "channel_id",
        "text": "text",
    }


@pytest.fixture
def say():
    return AsyncMock()


@pytest.mark.asyncio
@patch("hackathon_2023.handlers.get_direct_message_channel_id")
async def test_handler_shortcuts(
    get_direct_message_channel_id_mock, client, payload, say
):
    get_direct_message_channel_id_mock.return_value = "dm_channel_id"
    await handler_shortcuts(client, True, payload, say)
    say.assert_called()


@pytest.mark.asyncio
@patch("hackathon_2023.handlers.get_direct_message_channel_id")
async def test_handler_tldr_slash_command_channel_history_error(
    get_direct_message_channel_id_mock, client, payload, say
):
    get_direct_message_channel_id_mock.return_value = "dm_channel_id"
    await handler_tldr_slash_command(client, AsyncMock(), payload, say)
    say.assert_called()


@pytest.mark.asyncio
@patch("hackathon_2023.handlers.get_direct_message_channel_id")
@patch("hackathon_2023.handlers.get_channel_history")
@patch("hackathon_2023.handlers.get_parsed_messages")
@patch("hackathon_2023.handlers.analyze_topics_of_history")
async def test_handler_topics_slash_command(
    analyze_topics_of_history_mock,
    get_parsed_messages_mock,
    get_channel_history_mock,
    get_direct_message_channel_id_mock,
    client,
    payload,
    say,
):
    get_direct_message_channel_id_mock.return_value = "dm_channel_id"
    get_channel_history_mock.return_value = ["message1", "message2", "message3"]
    get_parsed_messages_mock.return_value = "parsed_messages"
    analyze_topics_of_history_mock.return_value = "topic_overview"
    await handler_topics_slash_command(client, AsyncMock(), payload, say)
    say.assert_called()


@pytest.mark.asyncio
@patch("hackathon_2023.handlers.get_workspace_name")
@patch("hackathon_2023.handlers.summarize_slack_messages")
@patch("slack_sdk.WebClient.conversations_replies")
@patch("hackathon_2023.handlers.get_direct_message_channel_id")
async def test_handler_shortcuts(
    get_direct_message_channel_id_mock,
    conversations_replies_mock,
    summarize_slack_messages_mock,
    get_workspace_name_mock,
    client,
    payload,
    say,
):
    # Arrange
    get_direct_message_channel_id_mock.return_value = "dm_channel_id"
    conversations_replies_mock.return_value = {
        "ok": True,
        "messages": [{"text": "test message"}],
    }
    get_workspace_name_mock.return_value = "workspace_name"
    summarize_slack_messages_mock.return_value = ["summary"]

    # Act
    await handler_shortcuts(client, True, payload, say)

    # Assert
    say.assert_called_with(channel="dm_channel_id", text="\n".join(["summary"]))


@pytest.mark.asyncio
@patch("hackathon_2023.handlers.get_direct_message_channel_id")
async def test_handler_tldr_slash_command_public(
    get_direct_message_channel_id_mock, client, say
):
    get_direct_message_channel_id_mock.return_value = "dm_channel_id"
    payload = {
        "text": "public",
        "channel_name": "channel_name",
        "channel_id": "channel_id",
    }
    await handler_tldr_slash_command(client, AsyncMock(), payload, say)
    say.assert_called()
