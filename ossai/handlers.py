import os

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from langsmith import Client

from ossai.summarizer import summarize_slack_messages
from ossai.topic_analysis import analyze_topics_of_history
from ossai.utils import (
    get_direct_message_channel_id,
    get_workspace_name,
    get_channel_history,
    get_parsed_messages,
    get_bot_id,
    get_user_context,
    get_is_private_and_channel_name,
    get_text_and_blocks_for_say
)


def handler_feedback(body):
    """
    Handler for the feedback buttons that passes the feedback to Langsmith.
    """
    client = Client()
    actions_data = body.get('actions')[0]
    run_id = actions_data.get('value')
    action_id = actions_data.get('action_id')

    score = 0.0

    if action_id == "not_helpful_button":
        score = -1.0
    elif action_id == "helpful_button":
        score = 1.0
    elif action_id == "very_helpful_button":
        score = 2.0

    client.create_feedback(
        run_id,
        project_id=os.environ.get("LANGSMITH_PROJECT_ID"),
        key="user_feedback",
        score=score,
        comment=f"Feedback from action: {action_id}"
    )
    

async def handler_shortcuts(client: WebClient, is_private: bool, payload, say, user_id: str):
    channel_id = payload['channel']['id'] if payload['channel']['id'] else payload['channel_id']
    dm_channel_id = await get_direct_message_channel_id(client, user_id)
    channel_id_for_say = dm_channel_id if is_private else channel_id
    await say(channel=channel_id_for_say, text='...')

    try:
        response = client.conversations_replies(channel=channel_id, ts=payload['message_ts'])
        if response['ok']:
            messages = response['messages']
            original_message = messages[0]['text']
            workspace_name = get_workspace_name(client)
            link = f"https://{workspace_name}.slack.com/archives/{channel_id}/p{payload['message_ts'].replace('.', '')}"

            # truncate the message if it's longer than 120 characters &/or it contains \n and append the link
            original_message = original_message.split('\n')
            thread_hint = original_message[0] if len(original_message) == 1 else f'{original_message[0]}...'
            thread_hint = thread_hint if len(thread_hint) <= 120 else thread_hint[:120] + '...'

            title = f'*Summary of <{link}|{"thread" if len(messages) > 1 else "message"}>:*\n>{thread_hint}\n'
            user = await get_user_context(client, user_id)
            summary, run_id = summarize_slack_messages(client, messages, channel_id, feature_name="summarize_thread", user=user)
            text, blocks = get_text_and_blocks_for_say(title=title, run_id=run_id, messages=summary)
            try:
                return await say(channel=channel_id_for_say, text=text, blocks=blocks)
            except SlackApiError as e:
                if e.response['error'] == 'channel_not_found':
                    return await say(channel=dm_channel_id, text=text, blocks=blocks)
                raise e
        else:
            return await say(channel=channel_id_for_say, text="Sorry, couldn't fetch the message and its replies.")
    except SlackApiError as e:
        if e.response['error'] == 'channel_not_found' or e.response['error'] == 'not_in_channel':
            bot_id = await get_bot_id(client)
            bot_info = client.bots_info(bot=bot_id)
            print(bot_info)
            bot_name = bot_info['bot']['name']
            return await say(channel=dm_channel_id,
                             text=f"Sorry, couldn't find the channel. Have you added `@{bot_name}` to the channel?")
        return await say(channel=dm_channel_id, text=f"Encountered an error: {e.response['error']}")


async def handler_tldr_slash_command(client: WebClient, ack, payload, say, user_id: str):
    await ack()  # fixme: this seemingly does nothing
    text = payload.get("text", None)
    channel_name = payload["channel_name"]
    channel_id = payload["channel_id"]
    dm_channel_id = None

    if text == 'public':
        await say('...')  # hack to get the bot to not show an error message but works fine
    else:
        dm_channel_id = await get_direct_message_channel_id(client, user_id)
        await say(channel=dm_channel_id, text='...')  # hack to get the bot to not show an error message but works fine

    if text and text != 'public':
        return await say("ERROR: Invalid command. Try /tldr or /tldr public.")
    try:
        history = await get_channel_history(client, channel_id)
        history.reverse()
        user = await get_user_context(client, user_id)
        title = f'*Summary of #{channel_name}* (last {len(history)} messages)\n'
        summary, run_id = summarize_slack_messages(client, history, channel_id, feature_name="summarize_channel_messages", user=user)
        text, blocks = get_text_and_blocks_for_say(title=title, run_id=run_id, messages=summary)
        if text == 'public':
            return await say(text=text, blocks=blocks)
        return await say(channel=dm_channel_id, text=text, blocks=blocks)
    except SlackApiError as e:
        if e.response['error'] == 'channel_not_found':
            return await say(channel=dm_channel_id,
                             text="Sorry, couldn't find the channel. Have you added 'me' to the channel?")
        return await say(channel=dm_channel_id, text=f"Encountered an error: {e.response['error']}")


async def handler_topics_slash_command(client: WebClient, ack, payload, say, user_id: str):
    # START boilerplate
    await ack()
    channel_id = payload["channel_id"]
    dm_channel_id = await get_direct_message_channel_id(client, user_id)
    await say(channel=dm_channel_id, text='...')

    history = await get_channel_history(client, channel_id)
    history.reverse()
    # END boilerplate

    messages = get_parsed_messages(client, history, with_names=False)
    user = await get_user_context(client, user_id)
    is_private, channel_name = get_is_private_and_channel_name(client, channel_id)
    topic_overview, run_id = await analyze_topics_of_history(channel_name, messages, user=user, is_private=is_private)
    title = f"*Channel Overview: #{channel_name}*\n\n"
    text, blocks = get_text_and_blocks_for_say(title=title, run_id=run_id, messages=[topic_overview])
    return await say(channel=dm_channel_id, text=text, blocks=blocks)
