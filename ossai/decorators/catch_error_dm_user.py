from functools import wraps
from typing import Optional, Union
from pydantic import BaseModel, Field, ValidationError
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from ossai.logging_config import logger
from ossai.utils import get_bot_id, get_direct_message_channel_id


class SlackPayload(BaseModel):
    user_id: Optional[str] = Field(None, description="User ID")
    channel_id: Optional[str] = Field(None, description="Channel ID")
    user: Optional[dict] = Field(None, description="User object")
    channel: Optional[dict] = Field(None, description="Channel object")

    def get_user_id(self) -> str:
        return self.user_id or (self.user or {}).get("id")

    def get_channel_id(self) -> str:
        return self.channel_id or (self.channel or {}).get("id")


def catch_errors_dm_user(func):
    @wraps(func)
    async def wrapper(client: WebClient, *args, **kwargs):
        assert isinstance(client, WebClient), "client must be a Slack WebClient"

        payload = None
        if args:
            payload_dict = args[1] if len(args) > 1 else {}
        else:
            payload_dict = kwargs

        try:
            payload = SlackPayload(**payload_dict)
        except ValidationError as e:
            logger.error(f"Invalid payload: {e}")
            # Continue execution even if validation fails

        try:
            return await func(client, *args, **kwargs)
        except SlackApiError as e:
            await _handle_slack_api_error(client, payload, payload_dict, e)
        except Exception as e:
            await _handle_unknown_error(client, payload, payload_dict, e)

    return wrapper


async def _handle_slack_api_error(
    client: WebClient,
    payload: Optional[SlackPayload],
    payload_dict: dict,
    error: SlackApiError,
):
    logger.error("[Slack API error] A SLACK ERROR OCCURRED...")
    if error.response["error"] in ("not_in_channel", "channel_not_found"):
        user_id = _get_user_id(payload, payload_dict)
        channel_id, error_type, error_message = await _handle_channel_error(
            client, user_id
        )
    else:
        channel_id = _get_channel_id(payload, payload_dict)
        error_type = "Slack API"
        error_message = f"Sorry, an unexpected error occurred. `{error.response['error']}`\n\n```{str(error)}```"

    user_id = _get_user_id(payload, payload_dict)
    await _send_error_message(client, channel_id, user_id, error_type, error_message)


async def _handle_channel_error(client: WebClient, user_id: str):
    channel_id = await get_direct_message_channel_id(client, user_id)
    error_type = "Not in channel"
    bot_id = await get_bot_id(client)
    bot_info = client.bots_info(bot=bot_id)
    bot_name = bot_info["bot"]["name"]
    error_message = f"Sorry, couldn't find the channel. Have you added `@{bot_name}` to the channel?"
    return channel_id, error_type, error_message


async def _handle_unknown_error(
    client: WebClient,
    payload: Optional[SlackPayload],
    payload_dict: dict,
    error: Exception,
):
    error_type = type(error).__name__
    error_message = f"Sorry, an unknown error occurred. `{error_type}: {error}`\n\n```{str(error)}```"
    logger.error(f"[Unknown error] {error}.", exc_info=True)
    channel_id = _get_channel_id(payload, payload_dict)
    user_id = _get_user_id(payload, payload_dict)
    await _send_error_message(client, channel_id, user_id, error_type, error_message)


async def _send_error_message(client, channel_id, user_id, error_type, error_message):
    logger.debug(
        f"running _send_error_message() with {channel_id=} {user_id=} {error_type=} {error_message=}"
    )
    try:
        # ? is this sometime async other times not?
        await client.chat_postEphemeral(
            channel=channel_id, user=user_id, text=error_message
        )
        logger.error(f"[{error_type} error] Message sent to user. {error_message}")
    except Exception as message_error:
        logger.error(
            f"[{error_type} error] All hope is lost. Failed to send error message to user: `{message_error}`.",
            exc_info=True,
        )


def _get_user_id(payload: Optional[SlackPayload], payload_dict: dict) -> str:
    if payload:
        return payload.get_user_id()
    return payload_dict.get("user_id") or payload_dict.get("user", {}).get("id")


def _get_channel_id(payload: Optional[SlackPayload], payload_dict: dict) -> str:
    if payload:
        return payload.get_channel_id()
    return payload_dict.get("channel_id") or payload_dict.get("channel", {}).get("id")
