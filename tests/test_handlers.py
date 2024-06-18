from unittest.mock import AsyncMock, patch
import uuid
import pytest
from slack_sdk import WebClient

from ossai.handlers import (
    handler_shortcuts,
    handler_tldr_slash_command,
    handler_topics_slash_command,
    handler_feedback,
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
@patch("ossai.handlers.get_direct_message_channel_id")
async def test_handler_shortcuts(
    get_direct_message_channel_id_mock, client, payload, say
):
    get_direct_message_channel_id_mock.return_value = "dm_channel_id"
    await handler_shortcuts(client, True, payload, say, user_id="foo123")
    say.assert_called()


@pytest.mark.asyncio
@patch("ossai.handlers.get_direct_message_channel_id")
async def test_handler_tldr_slash_command_channel_history_error(
    get_direct_message_channel_id_mock, client, payload, say
):
    get_direct_message_channel_id_mock.return_value = "dm_channel_id"
    await handler_tldr_slash_command(client, AsyncMock(), payload, say, user_id="foo123")
    say.assert_called()


@pytest.mark.asyncio
@patch("ossai.handlers.get_direct_message_channel_id")
@patch("ossai.handlers.get_channel_history")
@patch("ossai.handlers.get_parsed_messages")
@patch("ossai.handlers.analyze_topics_of_history")
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
    analyze_topics_of_history_mock.return_value = ("topic_overview", str(uuid.uuid4()))
    await handler_topics_slash_command(client, AsyncMock(), payload, say, user_id="foo123")
    say.assert_called()


@pytest.mark.asyncio
@patch("ossai.handlers.get_workspace_name")
@patch("ossai.handlers.summarize_slack_messages")
@patch("slack_sdk.WebClient.conversations_replies")
@patch("ossai.handlers.get_direct_message_channel_id")
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
    run_id = str(uuid.uuid4())
    get_direct_message_channel_id_mock.return_value = "dm_channel_id"
    conversations_replies_mock.return_value = {
        "ok": True,
        "messages": [{"text": "test message"}],
    }
    get_workspace_name_mock.return_value = "workspace_name"
    summarize_slack_messages_mock.return_value = ["summary"], run_id

    expected_blocks = [
        {'type': 'section', 'text': {'type': 'mrkdwn', 'text': '*Summary of <https://workspace_name.slack.com/archives/channel_id/pmessage_ts|message>:*\n>test message\n'}},
        {'type': 'section', 'text': {'type': 'mrkdwn', 'text': 'summary'}},
        {'type': 'actions', 'elements': [
            {'type': 'button', 'text': {'type': 'plain_text', 'text': ':-1: Not Helpful'}, 'action_id': 'not_helpful_button', 'value': run_id},
            {'type': 'button', 'text': {'type': 'plain_text', 'text': ':+1: Helpful'}, 'action_id': 'helpful_button', 'value': run_id},
            {'type': 'button', 'text': {'type': 'plain_text', 'text': ':tada: Very Helpful'}, 'action_id': 'very_helpful_button', 'value': run_id}
        ]}
    ]

    await handler_shortcuts(client, True, payload, say, user_id="foo123")
    say.assert_called_with(channel="dm_channel_id", text="summary", blocks=expected_blocks)


@pytest.mark.asyncio
@patch("ossai.handlers.get_direct_message_channel_id")
async def test_handler_tldr_slash_command_public(
    get_direct_message_channel_id_mock, client, say
):
    get_direct_message_channel_id_mock.return_value = "dm_channel_id"
    payload = {
        "text": "public",
        "channel_name": "channel_name",
        "channel_id": "channel_id",
    }
    await handler_tldr_slash_command(client, AsyncMock(), payload, say, user_id="foo123")
    say.assert_called()


@patch("ossai.handlers.Client")
@patch("os.environ.get")
def test_handler_feedback_not_helpful_button(env_get_mock, client_mock):
    # Arrange
    env_get_mock.return_value = "test_project_id"
    client_instance = client_mock.return_value
    body = {
        'actions': [{'value': '1234', 'action_id': 'not_helpful_button'}]
    }

    # Act
    handler_feedback(body)

    # Assert
    client_instance.create_feedback.assert_called_once_with(
        '1234',
        project_id='test_project_id',
        key='user_feedback',
        score=-1.0,
        comment='Feedback from action: not_helpful_button'
    )


@patch("ossai.handlers.Client")
@patch("os.environ.get")
def test_handler_feedback_helpful_button(env_get_mock, client_mock):
    # Arrange
    env_get_mock.return_value = "test_project_id"
    client_instance = client_mock.return_value
    body = {
        'actions': [{'value': '1234', 'action_id': 'helpful_button'}]
    }

    # Act
    handler_feedback(body)

    # Assert
    client_instance.create_feedback.assert_called_once_with(
        '1234',
        project_id='test_project_id',
        key='user_feedback',
        score=1.0,
        comment='Feedback from action: helpful_button'
    )


@patch("ossai.handlers.Client")
@patch("os.environ.get")
def test_handler_feedback_very_helpful_button(env_get_mock, client_mock):
    # Arrange
    env_get_mock.return_value = "test_project_id"
    client_instance = client_mock.return_value
    body = {
        'actions': [{'value': '1234', 'action_id': 'very_helpful_button'}]
    }

    # Act
    handler_feedback(body)

    # Assert
    client_instance.create_feedback.assert_called_once_with(
        '1234',
        project_id='test_project_id',
        key='user_feedback',
        score=2.0,
        comment='Feedback from action: very_helpful_button'
    )
