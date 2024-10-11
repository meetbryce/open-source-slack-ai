import os
import re
import uuid
from time import mktime, gmtime, strptime
import calendar
from typing import Union

from datetime import date
from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from langchain.callbacks.tracers import LangChainTracer

from ossai.logging_config import logger

load_dotenv(override=True)
_id_name_cache = {}


class CustomLangChainTracer(LangChainTracer):
    def __init__(self, is_private=False, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.is_private = is_private

    def handleText(self, text, runId):
        if not self.is_private:
            logger.info("passing text")
            super().handleText(text, runId)
        else:
            logger.info("passing no text")
            super().handleText("", runId)


async def get_bot_id(client) -> str:
    """
    Retrieves the bot ID using the provided Slack WebClient.

    Returns:
        str: The bot ID.
    """
    try:
        response = client.auth_test()
        return response["bot_id"]
    except SlackApiError as e:
        logger.error(f"Error fetching bot ID: {e.response['error']}")
        return "None"


async def get_channel_history(
    client: WebClient,
    channel_id: str,
    since: date = None,
    include_threads: bool = False,
) -> list:
    # todo: if include_threads, recursively get messages from threads

    oldest_timestamp = mktime(since.timetuple()) if since else 0
    response = client.conversations_history(
        channel=channel_id, limit=1000, oldest=oldest_timestamp
    )  # 1000 is the max limit
    bot_id = await get_bot_id(client)
    # todo: (optional) excluding all other bots too
    # todo: (optional) exclude messages that start with `/` (i.e. slash commands)
    return [msg for msg in response["messages"] if msg.get("bot_id") != bot_id]


async def get_direct_message_channel_id(client: WebClient, user_id: str) -> str:
    """
    Get the direct message channel ID for the bot, so you can say() via direct message.
    :return str:
    """
    # todo: cache this sucker too
    try:
        response = client.conversations_open(users=user_id)
        return response["channel"]["id"]
    except SlackApiError as e:
        logger.error(f"Error fetching bot DM channel ID: {e.response['error']}")
        raise e


def get_is_private_and_channel_name(
    client: WebClient, channel_id: str
) -> tuple[bool, str]:
    try:
        channel_info = client.conversations_info(channel=channel_id)
        channel_name = channel_info["channel"]["name"]
        is_private = channel_info["channel"]["is_private"]
    except Exception as e:
        logger.error(
            f"Error getting channel info for is_private, defaulting to private: {e}"
        )
        channel_name = "unknown"
        is_private = True
    return is_private, channel_name


def get_langsmith_config(feature_name: str, user: dict, channel: str, is_private=False):
    run_id = str(uuid.uuid4())
    tracer = CustomLangChainTracer(
        is_private=is_private
    )  # FIXME: this doesn't add privacy like it should

    return {
        "run_id": run_id,
        "metadata": {
            "is_private": is_private,
            **({"user_name": user.get("name")} if "name" in user else {}),
            **({"user_title": user.get("title")} if "title" in user else {}),
            "channel": channel,
        },
        "tags": [feature_name],
        "callbacks": [tracer],
    }


def get_llm_config():
    chat_model = os.getenv("CHAT_MODEL", "gpt-3.5-turbo").strip()
    temperature = float(os.getenv("TEMPERATURE", 0.2))
    openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
    debug = bool(os.environ.get("DEBUG", False))
    max_body_tokens = int(os.getenv("MAX_BODY_TOKENS", 1000))
    language = os.getenv("LANGUAGE", "english")

    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY is not set in .env file")
    return {
        "chat_model": chat_model,
        "temperature": temperature,
        "OPENAI_API_KEY": openai_api_key,
        "debug": debug,
        "max_body_tokens": max_body_tokens,
        "language": language,
    }


def get_name_from_id(client: WebClient, user_or_bot_id: str, is_bot=False) -> str:
    """
    Retrieves the name associated with a user ID or bot ID.

    Args:
        client (WebClient): An instance of the Slack WebClient.
        user_or_bot_id (str): The user or bot ID.
        is_bot (bool): Whether the ID is a bot ID.

    Returns:
        str: The name associated with the ID.
    """
    if user_or_bot_id in _id_name_cache:
        return _id_name_cache[user_or_bot_id]

    try:
        user_response = client.users_info(user=user_or_bot_id)
        if user_response.get("ok"):
            name = user_response["user"].get(
                "real_name", user_response["user"]["profile"]["real_name"]
            )
            _id_name_cache[user_or_bot_id] = name
            return name
        else:
            logger.error("user fetch failed")
            raise SlackApiError("user fetch failed", user_response)
    except SlackApiError as e:
        if e.response["error"] == "user_not_found":
            try:
                bot_response = client.bots_info(bot=user_or_bot_id)
                if bot_response.get("ok"):
                    _id_name_cache[user_or_bot_id] = bot_response["bot"]["name"]
                    return bot_response["bot"]["name"]
                else:
                    logger.error("bot fetch failed")
                    raise SlackApiError("bot fetch failed", bot_response)
            except SlackApiError as e2:
                logger.error(
                    f"Error fetching name for bot {user_or_bot_id=}: {e2.response['error']}"
                )
        logger.error(f"Error fetching name for {user_or_bot_id=} {is_bot=} {e=}")

    return "Someone"


def get_parsed_messages(client, messages, with_names=True):
    def parse_message(msg):
        user_id = msg.get("user")
        if user_id is None:
            bot_id = msg.get("bot_id")
            name = get_name_from_id(client, bot_id, is_bot=True)
        else:
            name = get_name_from_id(client, user_id)

        # substitute @mentions with names
        parsed_message = re.sub(
            r"<@[UB]\w+>",
            lambda m: get_name_from_id(client, m.group(0)[2:-1]),
            msg["text"],
        )

        if not with_names:
            return re.sub(
                r"<@[UB]\w+>", lambda m: "", msg["text"]
            )  # remove @mentions + don't prepend author name

        return f"{name}: {parsed_message}"

    return [parse_message(message) for message in messages]


def get_text_and_blocks_for_say(
    title: str,
    run_id: Union[uuid.UUID, None],
    messages: list,
    custom_prompt: str = None,
) -> tuple[str, list]:
    CHAR_LIMIT = 3000
    text = "\n".join(messages)

    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": title,
            },
        },
    ]

    # Split text into multiple blocks if it exceeds 3000 characters
    remaining_text = text
    while len(remaining_text) > 0:
        chunk = remaining_text[:CHAR_LIMIT]
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": chunk,
                },
            }
        )
        remaining_text = remaining_text[CHAR_LIMIT:]

    if run_id is not None:
        blocks.append(
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": ":-1: Not Helpful"},
                        "action_id": "not_helpful_button",
                        "value": str(run_id),
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": ":+1: Helpful"},
                        "action_id": "helpful_button",
                        "value": str(run_id),
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": ":tada: Very Helpful"},
                        "action_id": "very_helpful_button",
                        "value": str(run_id),
                    },
                ],
            }
        )

    if custom_prompt:
        blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "plain_text",
                        "text": f"Custom Prompt: {custom_prompt}",
                        "emoji": True,
                    }
                ],
            }
        )

    return text.split("\n")[0], blocks


async def get_user_context(client: WebClient, user_id: str) -> dict:
    """
    Get the username and title for the given user ID.
    """
    try:
        user_info = client.users_info(user=user_id)
        logger.debug(user_info)
        if user_info["ok"]:
            name = user_info["user"]["name"]
            title = user_info["user"]["profile"]["title"]
            return {"name": name, "title": title}
    except SlackApiError as e:
        logger.error(f"Failed to fetch username: {e}")
        return {}


def get_workspace_name(client: WebClient):
    """
    Retrieve the workspace name using an instantiated Slack WebClient.

    Args:
    - client (WebClient): An instantiated Slack WebClient.

    Returns:
    - str: The workspace name if found, otherwise an empty string.
    """

    try:
        response = client.team_info()
        if response["ok"]:
            return response["team"]["name"]
        else:
            logger.warning(
                f"Error retrieving workspace name: {response['error']}. Falling back to WORKSPACE_NAME_FALLBACK."
            )
            return os.getenv("WORKSPACE_NAME_FALLBACK", "")
    except SlackApiError as e:
        logger.error(f"Error retrieving workspace name: {e.response['error']}")
        return os.getenv("WORKSPACE_NAME_FALLBACK", "")  # None


def get_since_timeframe_presets():
    DAY_OF_SECONDS = 86400
    now = gmtime()
    today = calendar.timegm(
        strptime(f"{now.tm_year}-{now.tm_mon}-{now.tm_mday}", "%Y-%m-%d")
    )
    options = [
        ("Last 7 days", str(today - 7 * DAY_OF_SECONDS)),
        ("Last 14 days", str(today - 14 * DAY_OF_SECONDS)),
        ("Last 30 days", str(today - 30 * DAY_OF_SECONDS)),
        (
            "This week",
            str(today - (now.tm_wday * DAY_OF_SECONDS)),
        ),  # Monday at 00:00:00
        (
            "Last week",
            str(today - (now.tm_wday * DAY_OF_SECONDS) - 7 * DAY_OF_SECONDS),
        ),  # From the start of last week
        (
            "This month",
            str(
                calendar.timegm(strptime(f"{now.tm_year}-{now.tm_mon}-01", "%Y-%m-%d"))
            ),
        ),  # From the start of this month
        (
            "Last month",
            str(
                calendar.timegm(
                    strptime(
                        f"{now.tm_year if now.tm_mon > 1 else now.tm_year - 1}-{now.tm_mon - 1 if now.tm_mon > 1 else 12}-01",
                        "%Y-%m-%d",
                    )
                )
            ),
        ),  # From the start of last month
    ]
    return {
        "type": "static_select",
        "placeholder": {"type": "plain_text", "text": "Select a preset", "emoji": True},
        "action_id": "summarize_since_preset",
        "options": [
            {
                "text": {"type": "plain_text", "text": text, "emoji": True},
                "value": value,
            }
            for (text, value) in options
        ],
    }


def main():
    logger.error("DEBUGGING")


if __name__ == "__main__":
    main()
