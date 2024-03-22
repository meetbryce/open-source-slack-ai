import pytest

from unittest.mock import patch, MagicMock


@pytest.fixture
def mock_dependencies():
    with patch('slack_sdk.WebClient', new_callable=MagicMock) as mock_WebClient:
        mock_WebClient.return_value.chat_postMessage.return_value = {"ok": True}
        yield mock_WebClient


@pytest.fixture
def slack_server(mock_dependencies):
    from hackathon_2023 import slack_server
    return slack_server


def test_pass(slack_server, mock_dependencies):
    assert True
