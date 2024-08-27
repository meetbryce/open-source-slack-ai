import os
import runpy
from unittest.mock import ANY, patch, MagicMock, create_autospec, AsyncMock

import pytest
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from ossai.slack_server import handle_slash_command_sandbox


@pytest.fixture
def mock_app():
    with patch("slack_bolt.App", new_callable=MagicMock) as mock:
        mock.return_value.get.return_value = {"status": 200, "message": "ok"}
        yield mock


@pytest.fixture
def mock_app_advanced():
    with patch("slack_bolt.App") as mock_app_class:
        app = create_autospec(App)
        mock_app_class.return_value = app
        yield app


@pytest.fixture
def mock_os_environ():
    with patch.dict(
        os.environ, {"SLACK_BOT_TOKEN": "xoxb-123", "SLACK_APP_TOKEN": "xapp-123"}
    ):
        yield


@pytest.fixture
def mock_uvicorn():
    with patch("uvicorn.run", return_value=None) as mock:
        yield mock


def test_pulse(mock_app, mock_os_environ):
    from ossai import slack_server

    result = slack_server.pulse()
    assert result == {"status": 200, "message": "ok"}


def test_main_loads_as_script(mock_app_advanced, mock_uvicorn, mock_os_environ, capfd):
    runpy.run_module("ossai.slack_server", run_name="__main__")
    out, err = capfd.readouterr()
    assert err == ""
    assert mock_uvicorn.called


@pytest.mark.asyncio
@patch("ossai.slack_server.client")
@patch("ossai.slack_server.handler_sandbox_slash_command")
async def test_handle_slash_command_sandbox(
    mock_handler_sandbox_slash_command, mock_client
):
    # Setup
    mock_ack = AsyncMock()
    mock_user_id = "U123ABC"
    mock_payload = {"user_id": mock_user_id}
    mock_say = AsyncMock()

    mock_handler_sandbox_slash_command.return_value = ("test_text", "test_blocks")

    # Execute
    await handle_slash_command_sandbox(mock_ack, mock_payload, mock_say)

    # Assert
    mock_handler_sandbox_slash_command.assert_called_once_with(
        mock_client, mock_ack, mock_payload, mock_say, user_id=mock_user_id
    )
