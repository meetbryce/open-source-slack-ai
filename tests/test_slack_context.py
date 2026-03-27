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
    assert slack_context.get_name_from_id("U123")[0] == "Ashley Wang"


def test_get_name_from_id_bot_user(slack_context):
    slack_context.client.users_info.side_effect = lambda user: {
        "ok": False,
        "error": "user_not_found",
    }  # simulate user not found
    slack_context.client.bots_info.side_effect = lambda bot: {
        "ok": True,
        "bot": {"name": "Bender Bending Rodríguez"},
    }

    assert slack_context.get_name_from_id("B123")[0] == "Bender Bending Rodríguez"



def test_get_name_from_id_bot_user_error(slack_context):
    slack_context.client.users_info.side_effect = lambda user: {
        "ok": False,
        "error": "user_not_found",
    }
    slack_context.client.bots_info.side_effect = lambda bot: {
        "ok": False,
        "error": "bot_not_found",
    }

    assert slack_context.get_name_from_id("B456")[0] == "Someone"


def test_get_name_from_id_bot_user_exception(slack_context):
    slack_context.client.users_info.side_effect = lambda user: {
        "ok": False,
        "error": "user_not_found",
    }  # simulate user not found
    slack_context.client.bots_info.side_effect = SlackApiError(
        "bot fetch failed", {"error": "bot_not_found"}
    )

    assert slack_context.get_name_from_id("B456")[0] == "Someone"


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


def test_get_name_from_id_cache_hit(slack_context):
    """Cache hit should return stored value without calling the Slack API."""
    slack_context._id_name_cache["U123"] = ("Cached Name", False)
    result = slack_context.get_name_from_id("U123")
    assert result == ("Cached Name", False)
    slack_context.client.users_info.assert_not_called()


def test_get_parsed_messages_with_internal_external(slack_context):
    """with_internal_external=True prefixes messages with [internal] or [external]."""
    def users_info_side_effect(user):
        data = {
            "U123": {"ok": True, "user": {"real_name": "Ashley Wang", "name": "ashley.wang", "profile": {"real_name": "Ashley Wang", "title": "CEO"}, "is_restricted": False}},
            "U456": {"ok": True, "user": {"real_name": "Taylor Garcia", "name": "taylor.garcia", "profile": {"real_name": "Taylor Garcia", "title": "CTO"}, "is_restricted": True}},
        }
        return data.get(user, {"ok": False})

    slack_context.client.users_info.side_effect = users_info_side_effect
    messages = [
        {"text": "Hello", "user": "U123"},
        {"text": "Hi there", "user": "U456"},
    ]
    result = slack_context.get_parsed_messages(messages, with_internal_external=True)
    assert result[0].startswith("Ashley Wang [internal]:")
    assert result[1].startswith("Taylor Garcia [external]:")


@pytest.mark.asyncio
async def test_get_user_context_success(slack_context):
    """Happy path returns name and title from the Slack user profile."""
    result = await slack_context.get_user_context("U123")
    assert result == {"name": "ashley.wang", "title": "CEO"}


@pytest.mark.asyncio
async def test_get_user_context_slack_api_error_returns_empty_dict(slack_context):
    """SlackApiError during user lookup returns {} instead of propagating the exception."""
    slack_context.client.users_info.side_effect = SlackApiError(
        "error", {"error": "user_not_found", "headers": {}}
    )
    result = await slack_context.get_user_context("U999")
    assert result == {}


def test_get_rich_parsed_messages_include_threads(slack_context):
    """include_threads=True fetches replies and attaches them as reply_messages."""
    slack_context.client.conversations_replies.return_value = {
        "ok": True,
        "messages": [
            {"text": "parent", "ts": "1000.0", "user": "U123", "thread_ts": "1000.0"},
            {"text": "reply", "ts": "1001.0", "user": "U456"},
        ],
    }
    messages = [{"text": "parent", "ts": "1000.0", "user": "U123", "thread_ts": "1000.0"}]
    result = slack_context.get_rich_parsed_messages(messages, channel_id="C123", include_threads=True)
    assert len(result) == 1
    assert "reply_messages" in result[0]
    assert len(result[0]["reply_messages"]) == 1
    assert result[0]["author"] == "Ashley Wang"
    assert all(k in result[0]["trad_sentiment"] for k in ("neg", "neu", "pos", "compound"))


def test_get_rich_parsed_messages_thread_slack_api_error(slack_context):
    """SlackApiError fetching thread replies still returns the parent message."""
    slack_context.client.conversations_replies.side_effect = SlackApiError(
        "error", {"error": "channel_not_found", "headers": {}}
    )
    messages = [{"text": "hi", "ts": "1000.0", "user": "U123", "thread_ts": "1000.0"}]
    result = slack_context.get_rich_parsed_messages(messages, channel_id="C123", include_threads=True)
    assert len(result) == 1
    assert "reply_messages" not in result[0]
