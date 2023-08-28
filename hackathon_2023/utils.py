from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


async def get_channel_history(client: WebClient, channel_id: str) -> list:
    try:
        response = client.conversations_history(channel=channel_id, limit=1000)  # 1000 is the max limit
        bot_id = await get_bot_id(client)
        # todo: exclude messages that start with `/` (i.e. slash commands)
        # todo: support excluding other bots too
        return [msg for msg in response["messages"] if msg.get("bot_id") != bot_id]
    except SlackApiError as e:
        print(f"Error fetching history: {e.response['error']}")
        return []


async def get_bot_id(client) -> str:
    """
    Retrieves the bot ID using the provided Slack WebClient.

    Returns:
        str: The bot ID.
    """
    try:
        response = client.auth_test()
        return response["user_id"]
    except SlackApiError as e:
        print(f"Error fetching bot ID: {e.response['error']}")
        return 'None'
