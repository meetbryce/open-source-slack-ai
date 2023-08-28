from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


async def get_channel_history(client: WebClient, channel_id: str) -> list:
    try:
        response = client.conversations_history(channel=channel_id, limit=1000)  # 1000 is the max limit
        # todo: remove TLDR bot messages
        return response["messages"]
    except SlackApiError as e:
        print(f"Error fetching history: {e.response['error']}")
        return []
