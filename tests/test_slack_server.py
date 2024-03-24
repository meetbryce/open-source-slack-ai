import os
import runpy
from unittest.mock import patch, MagicMock, create_autospec

import pytest
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler


@pytest.fixture
def mock_app():
    with patch('slack_bolt.App', new_callable=MagicMock) as mock:
        mock.return_value.get.return_value = {"status": 200, "message": "ok"}
        yield mock


@pytest.fixture
def mock_app_advanced():
    with patch('slack_bolt.App') as mock_app_class:
        app = create_autospec(App)
        mock_app_class.return_value = app
        yield app


@pytest.fixture
def mock_os_environ():
    with patch.dict(os.environ, {"SLACK_BOT_TOKEN": "xoxb-123", "SLACK_APP_TOKEN": "xapp-123"}):
        yield


@pytest.fixture
def mock_socket_mode_handler():
    with patch.object(SocketModeHandler, 'start', return_value=None) as mock:
        yield mock


@pytest.fixture
def mock_uvicorn():
    with patch('uvicorn.run', return_value=None) as mock:
        yield mock


def test_pulse(mock_app, mock_os_environ):
    from hackathon_2023 import slack_server
    result = slack_server.pulse()
    assert result == {"status": 200, "message": "ok"}


def test_main_loads_as_script(mock_app_advanced, mock_socket_mode_handler, mock_uvicorn, mock_os_environ, capfd):
    runpy.run_module('hackathon_2023.slack_server', run_name='__main__')
    out, err = capfd.readouterr()
    assert err == ''
    assert mock_socket_mode_handler.called
    assert mock_uvicorn.called
