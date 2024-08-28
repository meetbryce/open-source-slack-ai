from functools import wraps
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from ossai.logging_config import logger


def safe_slack_api_call(func):
    @wraps(func)
    async def wrapper(client: WebClient, *args, **kwargs):
        user_id = kwargs.get("user_id")
        channel_id = args[1].get("channel_id")
        assert channel_id, "payload must contain 'channel_id'"

        try:
            return await func(client, *args, **kwargs)
        except SlackApiError as e:
            logger.error("[Slack API error] A SLACK ERROR OCCURRED...")

            error_message = f"Sorry, an unexpected error occurred. `{e.response['error']}`\n\n```{str(e)}```"
            try:
                client.chat_postEphemeral(
                    channel=channel_id, user=user_id, text=error_message
                )
                logger.error(f"[Slack API error] Message sent to user. {error_message}")
            except Exception as message_error:
                logger.error(
                    f"[Slack API error] All hope is lost. Failed to send error message to user: `{message_error}`.",
                    exc_info=True,
                )

    return wrapper
