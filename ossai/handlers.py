import os
import uuid

from aiohttp import ClientSession
from datetime import datetime
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from langsmith import Client

from ossai.decorators.catch_error_dm_user import catch_errors_dm_user
from ossai.logging_config import logger
from ossai.summarizer import Summarizer
from ossai.topic_analysis import analyze_topics_of_history
from ossai.utils import (
    get_direct_message_channel_id,
    get_workspace_name,
    get_channel_history,
    get_parsed_messages,
    get_user_context,
    get_is_private_and_channel_name,
    get_text_and_blocks_for_say,
    get_since_timeframe_presets,
)


def handler_feedback(body):
    """
    Handler for the feedback buttons that passes the feedback to Langsmith.
    """
    client = Client()
    actions_data = body.get("actions")[0]
    run_id = actions_data.get("value")
    action_id = actions_data.get("action_id")

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
        comment=f"Feedback from action: {action_id}",
    )


@catch_errors_dm_user
async def handler_shortcuts(
    client: WebClient, is_private: bool, payload, say, user_id: str
):
    channel_id = (
        payload["channel"]["id"] if payload["channel"]["id"] else payload["channel_id"]
    )
    dm_channel_id = await get_direct_message_channel_id(client, user_id)
    channel_id_for_say = dm_channel_id if is_private else channel_id
    await say(channel=channel_id_for_say, text="...")

    response = client.conversations_replies(
        channel=channel_id, ts=payload["message_ts"]
    )
    if response["ok"]:
        messages = response["messages"]
        original_message = messages[0]["text"]
        workspace_name = get_workspace_name(client)
        link = f"https://{workspace_name}.slack.com/archives/{channel_id}/p{payload['message_ts'].replace('.', '')}"

        original_message = original_message.split("\n")
        thread_hint = (
            original_message[0]
            if len(original_message) == 1
            else f"{original_message[0]}..."
        )
        thread_hint = (
            thread_hint if len(thread_hint) <= 120 else thread_hint[:120] + "..."
        )

        title = f'*Summary of <{link}|{"thread" if len(messages) > 1 else "message"}>:*\n>{thread_hint}\n'
        user = await get_user_context(client, user_id)
        summarizer = Summarizer()
        summary, run_id = summarizer.summarize_slack_messages(
            client, messages, channel_id, feature_name="summarize_thread", user=user
        )
        text, blocks = get_text_and_blocks_for_say(
            title=title, run_id=run_id, messages=summary
        )
        return await say(channel=channel_id_for_say, text=text, blocks=blocks)
    else:
        return await say(
            channel=channel_id_for_say,
            text="Sorry, couldn't fetch the message and its replies.",
        )


@catch_errors_dm_user
async def handler_tldr_extended_slash_command(
    client: WebClient, ack, payload, say, user_id: str
):
    await ack()
    text = payload.get("text", None)
    channel_name = payload["channel_name"]
    channel_id = payload["channel_id"]
    dm_channel_id = None

    dm_channel_id = await get_direct_message_channel_id(client, user_id)
    await say(channel=dm_channel_id, text="...")

    if text:
        return await say("ERROR: custom prompt support coming soon!")

    history = await get_channel_history(client, channel_id)
    history.reverse()
    user = await get_user_context(client, user_id)
    title = f"*Summary of #{channel_name}* (last {len(history)} messages)\n"
    summarizer = Summarizer()
    summary, run_id = summarizer.summarize_slack_messages(
        client,
        history,
        channel_id,
        feature_name="summarize_channel_messages",
        user=user,
    )
    text, blocks = get_text_and_blocks_for_say(
        title=title, run_id=run_id, messages=summary
    )
    return await say(channel=dm_channel_id, text=text, blocks=blocks)


@catch_errors_dm_user
async def handler_topics_slash_command(
    client: WebClient, ack, payload, say, user_id: str
):
    await ack()
    text = payload.get("text", None)
    if text:
        return await say("ERROR: custom prompt support coming soon!")
    channel_id = payload["channel_id"]
    dm_channel_id = await get_direct_message_channel_id(client, user_id)
    await say(channel=dm_channel_id, text="...")

    history = await get_channel_history(client, channel_id)
    history.reverse()

    messages = get_parsed_messages(client, history, with_names=False)
    user = await get_user_context(client, user_id)
    is_private, channel_name = get_is_private_and_channel_name(client, channel_id)
    topic_overview, run_id = await analyze_topics_of_history(
        channel_name, messages, user=user, is_private=is_private
    )
    title = f"*Channel Overview: #{channel_name}*\n\n"
    text, blocks = get_text_and_blocks_for_say(
        title=title, run_id=run_id, messages=[topic_overview]
    )
    return await say(channel=dm_channel_id, text=text, blocks=blocks)


@catch_errors_dm_user
async def handler_tldr_since_slash_command(client: WebClient, ack, payload, say):
    await ack()
    title = "Choose your summary timeframe."
    dm_channel_id = await get_direct_message_channel_id(client, payload["user_id"])
    text = payload.get("text", None)
    if text:
        return await say("ERROR: custom prompt support coming soon!")

    client.chat_postEphemeral(
        channel=payload["channel_id"],
        user=payload["user_id"],
        text=title,
        blocks=[
            {
                "type": "actions",
                "elements": [
                    get_since_timeframe_presets(),
                    {
                        "type": "datepicker",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Select a date",
                            "emoji": True,
                        },
                        "action_id": "summarize_since",
                    },
                ],
            }
        ],
    )

    await say(
        channel=dm_channel_id,
        text=f'In #{payload["channel_name"]}, choose a date or timeframe to get your summary',
    )


@catch_errors_dm_user
async def handler_action_summarize_since_date(client: WebClient, ack, body):
    """
    Provide a message summary of the channel since a given date.
    """
    await ack()
    channel_name = body["channel"]["name"]
    channel_id = body["channel"]["id"]
    user_id = body["user"]["id"]
    feature_name = body["actions"][0]["action_id"]

    # todo: make util function for testability
    # todo: account for the user's timezone :melt:
    if feature_name == "summarize_since_preset":
        since_datetime: datetime = datetime.fromtimestamp(
            int(body["actions"][0]["selected_option"]["value"])
        ).date()
    else:
        since_date = body["actions"][0]["selected_date"]
        since_datetime: datetime = datetime.strptime(since_date, "%Y-%m-%d").date()

    dm_channel_id = await get_direct_message_channel_id(client, user_id)
    client.chat_postMessage(channel=dm_channel_id, text="...")

    async with ClientSession() as session:
        await session.post(body["response_url"], json={"delete_original": "true"})

    history = await get_channel_history(client, channel_id, since=since_datetime)
    history.reverse()
    user = await get_user_context(client, user_id)
    summarizer = Summarizer()
    summary, run_id = summarizer.summarize_slack_messages(
        client, history, channel_id, feature_name=feature_name, user=user
    )
    text, blocks = get_text_and_blocks_for_say(
        title=f'*Summary of #{channel_name}* since {since_datetime.strftime("%A %b %-d, %Y")} ({len(history)} messages)\n',
        run_id=run_id,
        messages=summary,
    )
    # todo: somehow add date/preset choice to langsmith metadata
    #   feature_name: str -> feature: str || Tuple[str, List(Tuple[str, str])]
    return client.chat_postMessage(channel=dm_channel_id, text=text, blocks=blocks)


@catch_errors_dm_user
async def handler_sandbox_slash_command(
    client: WebClient, ack, payload, say, user_id: str
):
    text = payload.get("text", None)
    if text:
        return await say("ERROR: custom prompt support coming soon!")
    logger.debug(f"Handling /sandbox command")
    await ack()
    run_id = str(uuid.uuid4())
    run_id = None
    text = """-- Better error handling coming soon! Useful summary of content goes here -- (no run id)"""
    lines = text.strip().split("\n")
    title = "This is a test of the /sandbox command."
    text, blocks = get_text_and_blocks_for_say(
        title=title, run_id=run_id, messages=lines
    )
    return await say(text=text, blocks=blocks)
