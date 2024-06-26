from unittest.mock import AsyncMock, MagicMock, patch
import uuid
import pytest
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from datetime import datetime, timezone

from ossai.handlers import (
    handler_shortcuts,
    handler_tldr_slash_command,
    handler_topics_slash_command,
    handler_feedback,
    handler_action_summarize_since_date,
    handler_tldr_since_slash_command,
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


@pytest.mark.asyncio
@patch('ossai.handlers.get_direct_message_channel_id')
@patch('ossai.utils.get_bot_id')
async def test_handler_shortcuts_channel_not_found_error(get_bot_id_mock, get_direct_message_channel_id_mock):
    # Setup
    client = MagicMock()
    client.bots_info.return_value = {'bot': {'name': 'TestBot'}}
    say = AsyncMock()
    get_direct_message_channel_id_mock.return_value = 'DM123'
    get_bot_id_mock.return_value = 'B123'
    client.conversations_replies.side_effect = SlackApiError(message="channel_not_found", response={"error": "channel_not_found"})
    
    # Execute
    await handler_shortcuts(client, is_private=False, payload={
        'channel': {'id': 'C123'},
        'message_ts': '1234567890.123456'
    }, say=say, user_id='U123')

    # Verify
    say.assert_called_with(channel='DM123', text="Sorry, couldn't find the channel. Have you added `@TestBot` to the channel?")


@pytest.mark.asyncio
@patch('ossai.handlers.get_channel_history')
@patch('ossai.handlers.get_user_context')
@patch('ossai.handlers.summarize_slack_messages')
@patch('ossai.handlers.get_text_and_blocks_for_say')
@patch('ossai.handlers.get_direct_message_channel_id')
async def test_handler_tldr_slash_command_non_public(get_direct_message_channel_id_mock, get_text_and_blocks_for_say_mock, summarize_slack_messages_mock, get_user_context_mock, get_channel_history_mock):
    # Setup
    client = AsyncMock()
    say = AsyncMock()
    get_direct_message_channel_id_mock.return_value = 'DM123'
    get_channel_history_mock.return_value = ['message1', 'message2']
    get_user_context_mock.return_value = {'user': 'info'}
    summarize_slack_messages_mock.return_value = ('summary', 'run_id')
    get_text_and_blocks_for_say_mock.return_value = ('text', 'blocks')

    # Execute
    await handler_tldr_slash_command(client, AsyncMock(), {
        # 'text': 'non-public',
        'channel_name': 'general',
        'channel_id': 'C123'
    }, say, 'U123')

    # Verify
    assert say.call_count == 2
    say.assert_called_with(channel='DM123', text='text', blocks='blocks')
    get_direct_message_channel_id_mock.assert_called_once_with(client, 'U123')


@pytest.mark.asyncio
@patch('ossai.handlers.get_channel_history')
@patch('ossai.handlers.get_user_context')
@patch('ossai.handlers.summarize_slack_messages')
@patch('ossai.handlers.get_text_and_blocks_for_say')
@patch('ossai.handlers.get_direct_message_channel_id')
async def test_handler_tldr_slash_command_public_extended(
    get_direct_message_channel_id_mock, 
    get_text_and_blocks_for_say_mock, 
    summarize_slack_messages_mock, 
    get_user_context_mock, 
    get_channel_history_mock
):
    # Setup
    client = AsyncMock()
    say = AsyncMock()
    get_channel_history_mock.return_value = ['message1', 'message2']
    get_user_context_mock.return_value = {'user': 'info'}
    summarize_slack_messages_mock.return_value = ('summary', 'run_id')
    get_text_and_blocks_for_say_mock.return_value = ('dummy text', 'blocks')

    # Execute
    await handler_tldr_slash_command(client, AsyncMock(), {
        'text': 'public',
        'channel_name': 'general',
        'channel_id': 'C123'
    }, say, 'U123')

    # Verify
    assert say.call_count == 2
    say.assert_called_with(channel=None, text='dummy text', blocks='blocks')
    get_direct_message_channel_id_mock.assert_not_called()


@pytest.mark.asyncio
@patch('ossai.handlers.get_channel_history')
@patch('ossai.handlers.get_user_context')
@patch('ossai.handlers.summarize_slack_messages')
@patch('ossai.handlers.get_text_and_blocks_for_say')
@patch('ossai.handlers.get_direct_message_channel_id')
async def test_handler_action_summarize_since_date(
    get_direct_message_channel_id_mock,
    get_text_and_blocks_for_say_mock,
    summarize_slack_messages_mock,
    get_user_context_mock,
    get_channel_history_mock
):
    # Setup
    client = AsyncMock()
    body = {
        'channel': {'name': 'general', 'id': 'C123'},
        'user': {'id': 'U123'},
        'actions': [{'action_id': 'summarize_since_preset', 'selected_option': {'value': '1676955600'}}],
        'response_url': 'http://example.com/response'
    }
    get_direct_message_channel_id_mock.return_value = 'DM123'
    get_channel_history_mock.return_value = ['message1', 'message2']
    get_user_context_mock.return_value = {'user': 'info'}
    summarize_slack_messages_mock.return_value = ('summary', 'run_id')
    get_text_and_blocks_for_say_mock.return_value = ('text', 'blocks')

    # Execute
    await handler_action_summarize_since_date(client, body)

    # Verify
    get_direct_message_channel_id_mock.assert_called_once_with(client, 'U123')
    get_channel_history_mock.assert_called_once_with(client, 'C123', since=datetime(2023, 2, 21, tzinfo=timezone.utc).date())
    get_user_context_mock.assert_called_once_with(client, 'U123')
    summarize_slack_messages_mock.assert_called_once_with(client, ['message2', 'message1'], 'C123', feature_name='summarize_since_preset', user={'user': 'info'})
    get_text_and_blocks_for_say_mock.assert_called_once_with(
        title='*Summary of #general* since Tuesday Feb 21, 2023 (2 messages)\n',
        run_id='run_id',
        messages='summary'
    )
    client.chat_postMessage.assert_called_with(channel='DM123', text='text', blocks='blocks')


@pytest.mark.asyncio
@patch('ossai.handlers.get_direct_message_channel_id')
@patch('ossai.handlers.get_since_timeframe_presets')
async def test_handler_tldr_since_slash_command_happy_path(get_since_timeframe_presets_mock, get_direct_message_channel_id_mock):
    # Setup
    client = AsyncMock()
    client.chat_postEphemeral = AsyncMock()
    say = AsyncMock()
    payload = {
        'user_id': 'U123',
        'channel_id': 'C123',
        'channel_name': 'general'
    }
    get_since_timeframe_presets_mock.return_value = {'foo': 'bar'}
    get_direct_message_channel_id_mock.return_value = 'DM123'

    # Execute
    await handler_tldr_since_slash_command(client, payload, say)

    # Verify
    client.chat_postEphemeral.assert_called_once_with(
        channel='C123',
        user='U123',
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
                            "emoji": True
                        },
                        "action_id": "summarize_since"
                    },
                ]
            }
        ]
    )
    say.assert_called_once_with(channel='DM123', text="In #general, choose a date or timeframe to get your summary")

