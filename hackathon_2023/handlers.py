from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from hackathon_2023.summarizer import summarize_slack_messages
from hackathon_2023.utils import get_direct_message_channel_id


async def handler_shortcuts(client: WebClient, is_private, payload, say):
    channel_id = payload['channel']['id'] if payload['channel']['id'] else payload['channel_id']
    dm_channel_id = await get_direct_message_channel_id(client)
    # fixme: (let people know if it's not a thread and summarize the message instead)
    channel_id_for_say = dm_channel_id if is_private else channel_id

    try:
        response = client.conversations_replies(channel=channel_id, ts=payload['message_ts'])
        if response['ok']:
            messages = response['messages']
            original_message = messages[0]['text']
            workspace_name = 'tatari'  # todo: don't hardcode the workspace name
            link = f"https://{workspace_name}.slack.com/archives/{channel_id}/p{payload['message_ts'].replace('.', '')}"
            original_message += f' ({link})\n'
            summary = summarize_slack_messages(client, messages)
            summary.insert(0, original_message)
            print('made it this far', channel_id)
            try:
                return await say(channel=channel_id_for_say, text='\n'.join(summary))
            except SlackApiError as e:
                if e.response['error'] == 'channel_not_found':
                    print('attempting to DM instead')
                    return await say(channel=dm_channel_id, text='\n'.join(summary))

                raise e
        else:
            return await say(channel=channel_id_for_say, text="Sorry, couldn't fetch the message and its replies.")
    except SlackApiError as e:
        if e.response['error'] == 'channel_not_found':
            return await say(channel=dm_channel_id, text="Sorry, couldn't find the channel.")
        return await say(channel=dm_channel_id, text=f"Encountered an error: {e.response['error']}")
