import re
import runpy
from unittest.mock import patch, MagicMock

import pytest
from openai import RateLimitError

from ossai import summarizer
from ossai.summarizer import Summarizer
from ossai.utils import get_llm_config


# def test_summarize():
#     with patch('openai.ChatCompletion.create') as mock_create:
#         mock_create.return_value = {
#             "choices": [
#                 {
#                     "message": {
#                         'content': 'Summarized text'
#                     }
#                 }
#             ]
#         }
#         result = summarizer.summarize("Alice: Hi\nBob: Hello\nAlice: How are you?\nBob: I'm doing well, thanks.")
#         assert result == 'Summarized text'


def test_summarize_langchain():
    text = """\
    Bob: How are you?
    Jane: It's been so long. I've been great. I bought a house, started a business, and sold my left kidney.
    Bob: Well isn't that just wonderful. Did you mean to sell your kidney? I quite like having 2.
    Jane: I figured I had a spare and really wanted a Tesla. So, yeah. 
    """
    summarizer = Summarizer()
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


def test_estimate_openai_chat_token_count():
    summarizer = Summarizer()
    result = summarizer.estimate_openai_chat_token_count("Hello, how are you?")
    assert result == 7


def test_split_messages_by_token_count():
    with patch(
        "ossai.summarizer.get_parsed_messages"
    ) as mock_get_parsed_messages, patch.dict("os.environ", {"MAX_BODY_TOKENS": "3"}):
        mock_get_parsed_messages.return_value = ["Hello", "how", "are", "you"]
        messages = [
            {"text": "Hello"},
            {"text": "how"},
            {"text": "are"},
            {"text": "you"},
        ]
        summarizer = Summarizer()
        result = summarizer.split_messages_by_token_count(None, messages)
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


def test_summarize_slack_messages():
    # Mock the client and messages
    mock_client = MagicMock()
    mock_messages = [
        {"text": "Hello"},
        {"text": "how"},
        {"text": "are"},
        {"text": "you"},
    ]

    # Mock the conversations_info method to return a fixed response
    mock_client.conversations_info.return_value = {
        "channel": {"name": "foo", "is_private": False}
    }

    # Create a Summarizer instance
    summarizer = Summarizer()

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
                mock_client,
                mock_messages,
                channel_id="C1234567890",
                feature_name="unit_test",
                user="test_user",
            )
            # Check that the split_messages_by_token_count method was called with the correct arguments
            mock_split.assert_called_once_with(mock_client, mock_messages)
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


def test_summarize_slack_messages_private_channel():
    # Mock the client and messages
    mock_client = MagicMock()
    mock_messages = [
        {"text": "Hello"},
        {"text": "how"},
        {"text": "are"},
        {"text": "you"},
    ]

    # Mock the conversations_info method to return a fixed response
    mock_client.conversations_info.return_value = {
        "channel": {"name": "foo", "is_private": True}
    }

    # Create a Summarizer instance
    summarizer = Summarizer()

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
                mock_client,
                mock_messages,
                channel_id="C1234567890",
                feature_name="unit_test",
                user="test_user",
            )
            # Check that the split_messages_by_token_count method was called with the correct arguments
            mock_split.assert_called_once_with(mock_client, mock_messages)
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


def test_summarize_slack_messages_rate_limit_error():
    # Mock the client and messages
    mock_client = MagicMock()
    mock_messages = [
        {"text": "Hello"},
        {"text": "how"},
        {"text": "are"},
        {"text": "you"},
    ]

    # Create a Summarizer instance
    summarizer = Summarizer()

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
                mock_client,
                mock_messages,
                channel_id="C1234567890",
                feature_name="unit_test",
                user="test_user",
            )
            # Check that the result is as expected
            assert result == ["Sorry, OpenAI rate limit exceeded..."]


def test_main_as_script(capfd):
    # Run the utils module as a script
    with patch.dict("os.environ", {"SLACK_BOT_TOKEN": "test_token"}):
        runpy.run_module("ossai.summarizer", run_name="__main__")

    # Get the output from stdout and stderr
    out, err = capfd.readouterr()
    assert err == ""
    assert "DEBUGGING" in out
