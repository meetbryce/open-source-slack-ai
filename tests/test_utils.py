import runpy
from unittest.mock import ANY, patch, MagicMock
import time
import uuid
import pytest
from slack_sdk.errors import SlackApiError

from ossai import utils

@pytest.fixture
def mock_client():
    with patch("ossai.utils.WebClient") as mock_client:

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
        yield mock_client


@pytest.fixture
def mock_user_client():
    with patch(
        "slack_sdk.WebClient",
        return_value=MagicMock(auth_test=MagicMock(return_value={"user_id": "U123"})),
    ) as mock_client:
        yield mock_client


@pytest.mark.asyncio
async def test_get_bot_id(mock_client):
    mock_client.auth_test.return_value = {"bot_id": "B123"}
    assert await utils.get_bot_id(mock_client) == "B123"


@pytest.mark.asyncio
async def test_get_bot_id_with_exception(mock_client):
    mock_client.auth_test.side_effect = SlackApiError("error", {"error": "error"})
    assert await utils.get_bot_id(mock_client) == "None"


@pytest.mark.asyncio
async def test_get_channel_history(mock_client):
    mock_client.conversations_history.return_value = {"messages": [{"bot_id": "B123"}]}
    mock_client.auth_test.return_value = {"bot_id": "B123"}
    assert await utils.get_channel_history(mock_client, "C123") == []


@pytest.mark.asyncio
async def test_get_direct_message_channel_id(mock_client, mock_user_client):
    mock_client.conversations_open.return_value = {"channel": {"id": "C123"}}
    assert await utils.get_direct_message_channel_id(mock_client, "U123") == "C123"


@pytest.mark.asyncio
async def test_get_direct_message_channel_id_with_exception(mock_client):
    mock_client.conversations_open.side_effect = SlackApiError(
        "error", {"error": "error"}
    )
    with pytest.raises(SlackApiError) as e_info:
        await utils.get_direct_message_channel_id(mock_client, "U123")
        assert True


def test_get_name_from_id(mock_client):
    assert utils.get_name_from_id(mock_client, "U123") == "Ashley Wang"


def test_get_name_from_id_bot_user(mock_client):
    mock_client.users_info.side_effect = lambda user: {
        "ok": False,
        "error": "user_not_found",
    }  # simulate user not found
    mock_client.bots_info.side_effect = lambda bot: {
        "ok": True,
        "bot": {"name": "Bender Bending Rodríguez"},
    }

    assert utils.get_name_from_id(mock_client, "B123") == "Bender Bending Rodríguez"


def test_get_name_from_id_bot_user_error(mock_client):
    mock_client.users_info.side_effect = lambda user: {
        "ok": False,
        "error": "user_not_found",
    }
    mock_client.bots_info.side_effect = lambda bot: {
        "ok": False,
        "error": "bot_not_found",
    }

    assert utils.get_name_from_id(mock_client, "B456") == "Someone"


def test_get_name_from_id_bot_user_exception(mock_client):
    mock_client.users_info.side_effect = lambda user: {
        "ok": False,
        "error": "user_not_found",
    }  # simulate user not found
    mock_client.bots_info.side_effect = SlackApiError(
        "bot fetch failed", {"error": "bot_not_found"}
    )

    assert utils.get_name_from_id(mock_client, "B456") == "Someone"


def test_get_parsed_messages(mock_client):
    messages = [
        {"text": "Hello <@U456>", "user": "U123"},
        {"text": "nohello.net!!", "user": "U456"},
    ]
    assert utils.get_parsed_messages(mock_client, messages) == [
        "Ashley Wang: Hello Taylor Garcia",  # prefix with author's name & replace user ID with user's name
        "Taylor Garcia: nohello.net!!",  # prefix with author's name
    ]


def test_get_parsed_messages_without_names(mock_client):
    messages = [{"text": "Hello <@U456>", "user": "U123"}]

    # no author's name prefix & remove @mentions
    assert utils.get_parsed_messages(mock_client, messages, with_names=False) == [
        "Hello "
    ]


def test_get_parsed_messages_with_bot(mock_client):
    mock_client.users_info.side_effect = SlackApiError(
        "user fetch failed", {"error": "user_not_found"}
    )  # simulate user not found
    mock_client.bots_info.side_effect = lambda bot: {
        "ok": True,
        "bot": {"name": "Bender Bending Rodríguez"},
    }
    messages = [{"text": "I am <@B123>!", "bot_id": "B123"}]
    assert utils.get_parsed_messages(mock_client, messages) == [
        "Bender Bending Rodríguez: I am Bender Bending Rodríguez!",
    ]


def test_get_workspace_name(mock_client):
    mock_client.team_info.return_value = {"ok": True, "team": {"name": "Workspace"}}
    result = utils.get_workspace_name(mock_client)
    mock_client.team_info.assert_called_once()
    assert result == "Workspace"


def test_get_workspace_name_exception(mock_client):
    with patch.dict("os.environ", {"WORKSPACE_NAME_FALLBACK": ""}):
        mock_client.team_info.side_effect = SlackApiError("error", {"error": "error"})
        result = utils.get_workspace_name(mock_client)
        assert result == ""


def test_get_workspace_name_failure(mock_client):
    with patch.dict("os.environ", {"WORKSPACE_NAME_FALLBACK": ""}):
        mock_client.team_info.return_value = {"ok": False, "error": "team_info error"}
        result = utils.get_workspace_name(mock_client)
        mock_client.team_info.assert_called_once()
        assert result == ""


def test_main_as_script(capfd):
    # Run the utils module as a script
    with patch.dict("os.environ", {"SLACK_BOT_TOKEN": "test_token"}):
        runpy.run_module("ossai.utils", run_name="__main__")

    # Get the output from stdout and stderr
    out, err = capfd.readouterr()

    assert err == ""
    assert "DEBUGGING" in out


def test_get_langsmith_config_happy_path():
    feature_name = "feature_test"
    user = {"name": "testuser", "title": "developer"}
    channel = "test_channel"
    is_private = False

    expected_config = {
        "run_id": ANY,  # We expect this to be a UUID, so we use ANY
        "metadata": {
            "is_private": is_private,
            "user_name": "testuser",
            "user_title": "developer",
            "channel": channel,
        },
        "tags": [feature_name],
        "callbacks": [
            ANY
        ],  # The callback is an instance of CustomLangChainTracer, so we use ANY
    }

    # Call the function with the test inputs
    config = utils.get_langsmith_config(feature_name, user, channel, is_private)

    # Check that the returned config matches the expected config
    assert config["metadata"] == expected_config["metadata"]
    assert config["tags"] == expected_config["tags"]
    assert isinstance(config["callbacks"][0], utils.CustomLangChainTracer)
    assert isinstance(config["run_id"], str)  # run_id should be a string UUID


@pytest.mark.asyncio
async def test_get_user_context_success(mock_client):
    result = await utils.get_user_context(mock_client, "U123")

    mock_client.users_info.assert_called_once_with(user="U123")
    assert result == {"name": "ashley.wang", "title": "CEO"}


# todo: test get_llm_config()

# todo: test get_is_private_and_channel_name()

# todo: test get_text_and_blocks_for_say()


@patch("ossai.utils.gmtime")
def test_get_since_timeframe_presets_structure(mock_gmtime):
    # Mock the current time to a fixed timestamp
    fixed_time = 1718825962  # This corresponds to 2024-06-19 19:39:22 UTC
    mock_gmtime.return_value = time.gmtime(fixed_time)

    presets = utils.get_since_timeframe_presets()
    assert isinstance(presets, dict)
    assert presets["type"] == "static_select"
    assert "options" in presets
    options = presets["options"]
    assert isinstance(options, list)
    assert len(options) == 7  # Expecting 7 time frame options


@patch("ossai.utils.gmtime")
def test_get_since_timeframe_presets_values(mock_gmtime):
    fixed_time = 1718825962  # This corresponds to 2024-06-19 19:39:22 UTC
    mock_gmtime.return_value = time.gmtime(fixed_time)

    presets = utils.get_since_timeframe_presets()
    values = presets["options"]

    expected_values = [
        ("Last 7 days", "1718150400"),  # Last 7 days
        ("Last 14 days", "1717545600"),  # Last 14 days
        ("Last 30 days", "1716163200"),  # Last 30 days
        ("This week", "1718582400"),  # This week (Monday at 00:00:00)
        ("Last week", "1717977600"),  # Last week (start of last week)
        ("This month", "1717200000"),  # This month (start of this month)
        ("Last month", "1714521600"),  # Last month (start of last month)
    ]

    # Check if all options have the correct structure and types
    for (expected_text, expected_value), actual in zip(expected_values, values):
        assert (
            expected_text == actual["text"]["text"]
        ), f"Expected text {expected_text}, got {actual['text']['text']}"
        assert (
            expected_value == actual["value"]
        ), f"'{expected_text}': Expected value {expected_value}, got {actual['value']}"


def test_get_text_and_blocks_for_say_block_size():
    title = "Test Title"
    run_id = uuid.uuid4()
    
    # Create a message that's longer than 3000 characters
    long_message = "A" * 4000
    messages = [long_message]

    _, blocks = utils.get_text_and_blocks_for_say(title, run_id, messages)

    # Check that the title is in the first block
    assert blocks[0]['text']['text'] == title

    # Check that each block's text is no longer than 3000 characters
    for block in blocks[1:-1]:  # Exclude the first (title) and last (buttons) blocks
        assert len(block['text']['text']) <= 3000, f"Block text exceeds 3000 characters: {len(block['text']['text'])}"

    # Check that all of the original message is included
    combined_text = ''.join(block['text']['text'] for block in blocks[1:-1])
    assert combined_text == long_message

    # Check that the last block contains the buttons
    assert blocks[-1]['type'] == 'actions'
    assert len(blocks[-1]['elements']) == 3  # Three buttons


def test_main_as_script():
    utils.main()
