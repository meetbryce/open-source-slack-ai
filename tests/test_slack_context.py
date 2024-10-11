import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from slack_sdk import WebClient
from ossai.slack_context import SlackContext
from slack_sdk.errors import SlackApiError

@pytest.fixture
def mock_web_client():
    with patch("slack_sdk.WebClient") as mock_client:
        def users_info_side_effect(user):
            users = {
                "U123": {
                    "ok": True,
                    "user": {
                        "real_name": "Ashley Wang",
                        "name": "ashley.wang",
                        "profile": {"real_name": "Ashley Wang", "title": "CEO"},
                    },
                },
                "U456": {
                    "ok": True,
                    "user": {
                        "real_name": "Taylor Garcia",
                        "name": "taylor.garcia",
                        "profile": {"real_name": "Taylor Garcia", "title": "CTO"},
                    },
                },
            }
            return users.get(user, {"ok": False})

        mock_client.users_info.side_effect = users_info_side_effect
        mock_client.auth_test = MagicMock(return_value={"bot_id": "B123"})
        mock_client.conversations_history = MagicMock(return_value={"messages": [{"bot_id": "B123"}]})
        mock_client.conversations_open = MagicMock(return_value={"channel": {"id": "C123"}})
        mock_client.team_info = MagicMock(return_value={"ok": True, "team": {"name": "Test Workspace"}})
        yield mock_client

@pytest.fixture
def slack_context(mock_web_client):
    return SlackContext(mock_web_client)


@pytest.mark.asyncio
async def test_get_bot_id(slack_context):
    assert await slack_context.get_bot_id() == "B123"

@pytest.mark.asyncio
async def test_get_bot_id_with_exception(slack_context):
    slack_context.client.auth_test.side_effect = SlackApiError("error", {"error": "error"})
    assert await slack_context.get_bot_id() == "None"


@pytest.mark.asyncio
async def test_get_channel_history(slack_context):
    slack_context.client.conversations_history.return_value = {"messages": [{"bot_id": "B123"}]}
    assert await slack_context.get_channel_history("C123") == []


@pytest.mark.asyncio
async def test_get_direct_message_channel_id(slack_context):
    slack_context.client.conversations_open.return_value = {"channel": {"id": "C123"}}
    assert await slack_context.get_direct_message_channel_id("U123") == "C123"


@pytest.mark.asyncio
async def test_get_direct_message_channel_id_with_exception(slack_context):
    slack_context.client.conversations_open.side_effect = SlackApiError(
        "error", {"error": "error"}
    )
    with pytest.raises(SlackApiError) as e_info:
        await slack_context.get_direct_message_channel_id("U123")
        assert True


def test_get_name_from_id(slack_context):
    assert slack_context.get_name_from_id("U123") == "Ashley Wang"


def test_get_name_from_id_bot_user(slack_context):
    slack_context.client.users_info.side_effect = lambda user: {
        "ok": False,
        "error": "user_not_found",
    }  # simulate user not found
    slack_context.client.bots_info.side_effect = lambda bot: {
        "ok": True,
        "bot": {"name": "Bender Bending Rodríguez"},
    }

    assert slack_context.get_name_from_id("B123") == "Bender Bending Rodríguez"



def test_get_name_from_id_bot_user_error(slack_context):
    slack_context.client.users_info.side_effect = lambda user: {
        "ok": False,
        "error": "user_not_found",
    }
    slack_context.client.bots_info.side_effect = lambda bot: {
        "ok": False,
        "error": "bot_not_found",
    }

    assert slack_context.get_name_from_id("B456") == "Someone"


def test_get_name_from_id_bot_user_exception(slack_context):
    slack_context.client.users_info.side_effect = lambda user: {
        "ok": False,
        "error": "user_not_found",
    }  # simulate user not found
    slack_context.client.bots_info.side_effect = SlackApiError(
        "bot fetch failed", {"error": "bot_not_found"}
    )

    assert slack_context.get_name_from_id("B456") == "Someone"


def test_get_parsed_messages(slack_context):
    messages = [
        {"text": "Hello <@U456>", "user": "U123"},
        {"text": "nohello.net!!", "user": "U456"},
    ]
    assert slack_context.get_parsed_messages(messages) == [
        "Ashley Wang: Hello Taylor Garcia",  # prefix with author's name & replace user ID with user's name
        "Taylor Garcia: nohello.net!!",  # prefix with author's name
    ]


def test_get_parsed_messages_without_names(slack_context):
    messages = [{"text": "Hello <@U456>", "user": "U123"}]

    # no author's name prefix & remove @mentions
    assert slack_context.get_parsed_messages(messages, with_names=False) == [
        "Hello "
    ]


def test_get_parsed_messages_with_bot(slack_context):
    slack_context.client.users_info.side_effect = SlackApiError(
        "user fetch failed", {"error": "user_not_found"}
    )  # simulate user not found
    slack_context.client.bots_info.side_effect = lambda bot: {
        "ok": True,
        "bot": {"name": "Bender Bending Rodríguez"},
    }
    messages = [{"text": "I am <@B123>!", "bot_id": "B123"}]
    assert slack_context.get_parsed_messages(messages) == [
        "Bender Bending Rodríguez: I am Bender Bending Rodríguez!",
    ]


def test_get_workspace_name(slack_context):
    slack_context.client.team_info.return_value = {"ok": True, "team": {"name": "Workspace"}}
    result = slack_context.get_workspace_name()
    slack_context.client.team_info.assert_called_once()
    assert result == "Workspace"


def test_get_workspace_name_exception(slack_context):
    with patch.dict("os.environ", {"WORKSPACE_NAME_FALLBACK": ""}):
        slack_context.client.team_info.side_effect = SlackApiError("error", {"error": "error"})
        result = slack_context.get_workspace_name()
        assert result == ""


def test_get_workspace_name_failure(slack_context):
    with patch.dict("os.environ", {"WORKSPACE_NAME_FALLBACK": ""}):
        slack_context.client.team_info.return_value = {"ok": False, "error": "team_info error"}
        result = slack_context.get_workspace_name()
        slack_context.client.team_info.assert_called_once()
        assert result == ""
