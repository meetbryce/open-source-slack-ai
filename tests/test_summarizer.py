import re
import runpy
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from openai import RateLimitError

from ossai.summarizer import Summarizer, main as summarizer_main
from ossai.utils import get_llm_config


@pytest.fixture
def mock_slack_context():
    mock = MagicMock()
    mock.get_bot_id = AsyncMock(return_value="B12345")
    mock.get_channel_history = AsyncMock(return_value=[])
    mock.get_direct_message_channel_id = AsyncMock(return_value="D12345")
    mock.get_is_private_and_channel_name = MagicMock(return_value=(False, "general"))
    mock.get_name_from_id = MagicMock(return_value="John Doe")
    mock.get_parsed_messages = MagicMock(return_value=["John: Hello", "Jane: Hi"])
    mock.get_user_context = AsyncMock(return_value={"name": "John", "title": "Developer"})
    mock.get_workspace_name = MagicMock(return_value="My Workspace")
    return mock

def test_summarize_langchain(mock_slack_context):
    text = """\
    Bob: How are you?
    Jane: It's been so long. I've been great. I bought a house, started a business, and sold my left kidney.
    Bob: Well isn't that just wonderful. Did you mean to sell your kidney? I quite like having 2.
    Jane: I figured I had a spare and really wanted a Tesla. So, yeah. 
    """
    summarizer = Summarizer(mock_slack_context)
    result, run_id = summarizer.summarize(
        text, feature_name="unit_test", user="test_user", channel="test_channel"
    )
    assert "kidney" in result
    assert "Bob" in result
    assert "Jane" in result
    assert isinstance(run_id, str)
    assert (
        re.match(
            r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
            run_id,
        )
        is not None
    )


def test_estimate_openai_chat_token_count(mock_slack_context):
    summarizer = Summarizer(mock_slack_context)
    result = summarizer.estimate_openai_chat_token_count("Hello, how are you?")
    assert result == 7


def test_split_messages_by_token_count(mock_slack_context):
    with patch.dict("os.environ", {"MAX_BODY_TOKENS": "3"}):
        mock_slack_context.get_parsed_messages.return_value = ["Hello", "how", "are", "you"]
        messages = [
            {"text": "Hello"},
            {"text": "how"},
            {"text": "are"},
            {"text": "you"},
        ]
        summarizer = Summarizer(mock_slack_context)
        result = summarizer.split_messages_by_token_count(messages)
        assert result == [["Hello", "how"], ["are", "you"]]


def test_missing_openai_api_key():
    with patch(
        "os.getenv",
        side_effect=lambda k, default=None: "" if k == "OPENAI_API_KEY" else default,
    ):
        # Assert that calling get_llm_config without OPENAI_API_KEY set raises ValueError
        with pytest.raises(ValueError) as e:
            get_llm_config()
        assert str(e.value) == "OPENAI_API_KEY is not set in .env file"


def test_summarize_slack_messages(mock_slack_context):
    # Mock the client and messages
    mock_messages = [
        {"text": "Hello"},
        {"text": "how"},
        {"text": "are"},
        {"text": "you"},
    ]

    # Mock the conversations_info method to return a fixed response
    mock_slack_context.client.conversations_info.return_value = {
        "channel": {"name": "foo", "is_private": False}
    }
    mock_slack_context.get_is_private_and_channel_name.return_value = (False, "foo")

    # Create a Summarizer instance
    summarizer = Summarizer(mock_slack_context)

    # Mock the split_messages_by_token_count method
    with patch.object(
        summarizer,
        'split_messages_by_token_count',
        return_value=[["Hello", "how", "are", "you"]]
    ) as mock_split:
        # Mock the summarize method
        with patch.object(
            summarizer,
            'summarize',
            return_value=("Summarized text", "run_id")
        ) as mock_summarize:
            result, run_id = summarizer.summarize_slack_messages(
                mock_messages,
                channel_id="C1234567890",
                feature_name="unit_test",
                user="test_user",
            )
            # Check that the split_messages_by_token_count method was called with the correct arguments
            mock_split.assert_called_once_with(mock_messages)
            # Check that the summarize method was called with the correct arguments
            mock_summarize.assert_called_with(
                "\n".join(["Hello", "how", "are", "you"]),
                feature_name="unit_test",
                user="test_user",
                channel="foo",
                is_private=False,
            )
            # Check that the result is as expected
            assert result == ["Summarized text"]


def test_summarize_slack_messages_private_channel(mock_slack_context):
    # Mock the client and messages
    
    mock_messages = [
        {"text": "Hello"},
        {"text": "how"},
        {"text": "are"},
        {"text": "you"},
    ]

    # Mock the conversations_info method to return a fixed response
    mock_slack_context.client.conversations_info.return_value = {
        "channel": {"name": "foo", "is_private": True}
    }
    mock_slack_context.get_is_private_and_channel_name.return_value = (True, "foo")

    # Create a Summarizer instance
    summarizer = Summarizer(mock_slack_context)

    # Mock the split_messages_by_token_count method
    with patch.object(
        summarizer,
        'split_messages_by_token_count',
        return_value=[["Hello", "how", "are", "you"]]
    ) as mock_split:
        # Mock the summarize method
        with patch.object(
            summarizer,
            'summarize',
            return_value=("Summarized text", "run_id")
        ) as mock_summarize:
            result, run_id = summarizer.summarize_slack_messages(
                mock_messages,
                channel_id="C1234567890",
                feature_name="unit_test",
                user="test_user",
            )
            # Check that the split_messages_by_token_count method was called with the correct arguments
            mock_split.assert_called_once_with(mock_messages)
            # Check that the summarize method was called with the correct arguments
            mock_summarize.assert_called_with(
                "\n".join(["Hello", "how", "are", "you"]),
                feature_name="unit_test",
                user="test_user",
                channel="foo",
                is_private=True,
            )
            # Check that the result is as expected
            assert result == ["Summarized text"]


def test_summarize_slack_messages_rate_limit_error(mock_slack_context):
    # Mock the messages
    mock_messages = [
        {"text": "Hello"},
        {"text": "how"},
        {"text": "are"},
        {"text": "you"},
    ]

    # Create a Summarizer instance
    summarizer = Summarizer(mock_slack_context)

    # Mock the split_messages_by_token_count method
    with patch.object(
        summarizer,
        'split_messages_by_token_count',
        return_value=[["Hello", "how", "are", "you"]]
    ) as mock_split:
        # Mock the summarize method to raise a RateLimitError
        with patch.object(
            summarizer,
            'summarize',
            side_effect=RateLimitError(
                "Rate limit exceeded", response=MagicMock(), body={}
            )
        ) as mock_summarize:
            result, run_id = summarizer.summarize_slack_messages(
                mock_messages,
                channel_id="C1234567890",
                feature_name="unit_test",
                user="test_user",
            )
            # Check that the result is as expected
            assert result == ["Sorry, OpenAI rate limit exceeded..."]


def test_main_as_script():
    summarizer_main()
