import os
import re

from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

load_dotenv()
_id_name_cache = {}


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
        print(f"Error fetching bot ID: {e.response['error']}")
        return 'None'


async def get_channel_history(client: WebClient, channel_id: str) -> list:
    response = client.conversations_history(channel=channel_id, limit=1000)  # 1000 is the max limit
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
        print(f"Error fetching bot DM channel ID: {e.response['error']}")
        raise e


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
            name = user_response["user"].get("real_name", user_response["user"]["profile"]["real_name"])
            _id_name_cache[user_or_bot_id] = name
            return name
        else:
            print('user fetch failed')
            raise SlackApiError("user fetch failed", user_response)
    except SlackApiError as e:
        if e.response["error"] == "user_not_found":
            try:
                bot_response = client.bots_info(bot=user_or_bot_id)
                if bot_response.get("ok"):
                    _id_name_cache[user_or_bot_id] = bot_response["bot"]["name"]
                    return bot_response["bot"]["name"]
                else:
                    print('bot fetch failed')
                    raise SlackApiError("bot fetch failed", bot_response)
            except SlackApiError as e2:
                print(f"Error fetching name for bot {user_or_bot_id=}: {e2.response['error']}")
        print(f"Error fetching name for {user_or_bot_id=} {is_bot=} {e=}")

    return 'Someone'


def get_parsed_messages(client, messages, with_names=True):
    def parse_message(msg):
        user_id = msg.get("user")
        if user_id is None:
            bot_id = msg.get("bot_id")
            name = get_name_from_id(client, bot_id, is_bot=True)
        else:
            name = get_name_from_id(client, user_id)

        # substitute @mentions with names
        parsed_message = re.sub(r'<@[UB]\w+>', lambda m: get_name_from_id(client, m.group(0)[2:-1]), msg["text"])

        if not with_names:
            return re.sub(r'<@[UB]\w+>', lambda m: '', msg["text"])  # remove @mentions + don't prepend author name

        return f'{name}: {parsed_message}'

    return [parse_message(message) for message in messages]


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
            print(f"Error retrieving workspace name: {response['error']}")
            return os.getenv("WORKSPACE_NAME_FALLBACK", "")
    except SlackApiError as e:
        print(f"Error retrieving workspace name: {e.response['error']}")
        return os.getenv("WORKSPACE_NAME_FALLBACK", "")  # None


def main():
    print('DEBUGGING')


if __name__ == '__main__':
    main()
