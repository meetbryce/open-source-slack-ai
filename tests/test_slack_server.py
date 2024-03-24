import os
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture
def mock_app():
    with patch('slack_bolt.App', new_callable=MagicMock) as mock:
        mock.return_value.get.return_value = {"status": 200, "message": "ok"}
        yield mock


@pytest.fixture
def mock_os_environ():
    with patch.dict(os.environ, {"SLACK_BOT_TOKEN": "xoxb-123", "SLACK_APP_TOKEN": "xapp-123"}):
        yield


def test_pulse(mock_app, mock_os_environ):
    from hackathon_2023 import slack_server
    result = slack_server.pulse()
    assert result == {"status": 200, "message": "ok"}
