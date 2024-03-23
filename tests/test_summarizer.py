import runpy
from unittest.mock import patch, MagicMock

import pytest
from openai.error import RateLimitError

from hackathon_2023 import summarizer
from hackathon_2023.summarizer import get_config


def test_summarize():
    with patch('openai.ChatCompletion.create') as mock_create:
        mock_create.return_value = {
            "choices": [
                {
                    "message": {
                        'content': 'Summarized text'
                    }
                }
            ]
        }
        result = summarizer.summarize("Alice: Hi\nBob: Hello\nAlice: How are you?\nBob: I'm doing well, thanks.")
        assert result == 'Summarized text'


def test_estimate_openai_chat_token_count():
    result = summarizer.estimate_openai_chat_token_count("Hello, how are you?")
    assert result == 7


def test_split_messages_by_token_count():
    with patch('hackathon_2023.summarizer.get_parsed_messages') as mock_get_parsed_messages, \
            patch('hackathon_2023.summarizer.MAX_BODY_TOKENS', new=3):
        mock_get_parsed_messages.return_value = ['Hello', 'how', 'are', 'you']
        messages = [{'text': 'Hello'}, {'text': 'how'}, {'text': 'are'}, {'text': 'you'}]
        result = summarizer.split_messages_by_token_count(None, messages)
        assert result == [['Hello', 'how'], ['are', 'you']]


def test_missing_openai_api_key():
    with patch('os.getenv', side_effect=lambda k, default=None: "" if k == "OPEN_AI_TOKEN" else default):
        # Assert that calling get_config without OPEN_AI_TOKEN set raises ValueError
        with pytest.raises(ValueError) as e:
            get_config()
        assert str(e.value) == "OPEN_AI_TOKEN is not set in .env file"


def test_summarize_slack_messages():
    # Mock the client and messages
    mock_client = MagicMock()
    mock_messages = [{'text': 'Hello'}, {'text': 'how'}, {'text': 'are'}, {'text': 'you'}]
    context_message = "Context message"

    # Mock the split_messages_by_token_count function to return a fixed response
    with patch('hackathon_2023.summarizer.split_messages_by_token_count',
               return_value=[['Hello', 'how', 'are', 'you']]) as mock_split:
        # Mock the summarize function to return a fixed response
        with patch('hackathon_2023.summarizer.summarize', return_value='Summarized text') as mock_summarize:
            result = summarizer.summarize_slack_messages(mock_client, mock_messages, context_message)
            # Check that the split_messages_by_token_count function was called with the correct arguments
            mock_split.assert_called_once_with(mock_client, mock_messages)
            # Check that the summarize function was called with the correct arguments
            mock_summarize.assert_called_with("\n".join(['Hello', 'how', 'are', 'you']), summarizer.LANGUAGE)
            # Check that the result is as expected
            assert result == ['Context message', 'Summarized text']


def test_summarize_slack_messages_rate_limit_error():
    # Mock the client and messages
    mock_client = MagicMock()
    mock_messages = [{'text': 'Hello'}, {'text': 'how'}, {'text': 'are'}, {'text': 'you'}]
    context_message = "Context message"

    # Mock the split_messages_by_token_count function to return a fixed response
    with patch('hackathon_2023.summarizer.split_messages_by_token_count',
               return_value=[['Hello', 'how', 'are', 'you']]) as mock_split:
        # Mock the summarize function to raise a RateLimitError
        with patch('hackathon_2023.summarizer.summarize',
                   side_effect=RateLimitError('Rate limit exceeded')) as mock_summarize:
            result = summarizer.summarize_slack_messages(mock_client, mock_messages, context_message)
            # Check that the result is as expected
            assert result == ["Sorry, OpenAI rate limit exceeded..."]


def test_main_as_script(capfd):
    # Run the utils module as a script
    with patch.dict('os.environ', {'SLACK_BOT_TOKEN': 'test_token'}):
        runpy.run_module('hackathon_2023.summarizer', run_name='__main__')

    # Get the output from stdout and stderr
    out, err = capfd.readouterr()

    assert err == ''
    assert 'DEBUGGING' in out
