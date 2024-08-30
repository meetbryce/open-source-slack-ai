from functools import wraps
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from ossai.logging_config import logger
from ossai.utils import get_bot_id, get_direct_message_channel_id


def catch_errors_dm_user(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        client = args[0]
        assert isinstance(client, WebClient), "client must be a Slack WebClient"

        try:
            payload = args[2]
        except IndexError:
            print("PAYLOAD ERROR! args:", args)
            raise

        user_id = payload.get("user_id") or payload.get("user").get("id")
        assert user_id, f"payload must contain 'user_id'. Payload: {payload}"

        channel_id = payload.get("channel_id") or payload.get("channel").get("id")
        assert channel_id, f"payload must contain 'channel_id'. Payload: {payload}"

        try:
            return await func(*args, **kwargs)
        except SlackApiError as e:
            logger.error("[Slack API error] A SLACK ERROR OCCURRED...")
            if (
                e.response["error"] == "not_in_channel"
                or e.response["error"] == "channel_not_found"
            ):
                # todo: use this in all handlers (and remove the util function)
                channel_id = await get_direct_message_channel_id(client, user_id)
                error_type = "Not in channel"
                bot_id = await get_bot_id(client)
                bot_info = client.bots_info(bot=bot_id)
                bot_name = bot_info["bot"]["name"]
                error_message = f"Sorry, couldn't find the channel. Have you added `@{bot_name}` to the channel?"
            else:
                error_type = "Slack API"
                error_message = f"Sorry, an unexpected error occurred. `{e.response['error']}`\n\n```{str(e)}```"

            await _send_error_message(
                client, channel_id, user_id, error_type, error_message
            )
        except Exception as e:
            error_type = type(e).__name__
            error_message = f"Sorry, an unknown error occurred. `{error_type}: {e}`\n\n```{str(e)}```"
            logger.error(f"[Unknown error] {e}.", exc_info=True)
            await _send_error_message(
                client, channel_id, user_id, error_type, error_message
            )

    return wrapper


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
