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

            # todo: format original message as a quote (need to get markdown formatting working first)

            # truncate the message if it's longer than 120 characters &/or it contains \n and append the link
            original_message = original_message.split('\n')
            thread_hint = original_message[0] if len(original_message) == 1 else f'{original_message[0]}...'
            thread_hint = thread_hint if len(thread_hint) <= 120 else thread_hint[:120] + '...'

            context_message = f'*Summary of thread:* {thread_hint} ({link})\n'
            summary = summarize_slack_messages(client, messages, context_message)
            try:
                return await say(channel=channel_id_for_say, text='\n'.join(summary))
            except SlackApiError as e:
                if e.response['error'] == 'channel_not_found':
                    return await say(channel=dm_channel_id, text='\n'.join(summary))

                raise e
        else:
            return await say(channel=channel_id_for_say, text="Sorry, couldn't fetch the message and its replies.")
    except SlackApiError as e:
        if e.response['error'] == 'channel_not_found':
            return await say(channel=dm_channel_id, text="Sorry, couldn't find the channel.")
        return await say(channel=dm_channel_id, text=f"Encountered an error: {e.response['error']}")
