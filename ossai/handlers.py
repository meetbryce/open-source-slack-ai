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
    get_text_and_blocks_for_say,
    get_since_timeframe_presets,
)
from ossai.slack_context import SlackContext

_custom_prompt_cache = {}

# FIXME: basically, i need to have all handlers take `slack_context` not `client`

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
    slack_context: SlackContext, is_private: bool, payload, say, user_id: str
):
    client = slack_context.client
    channel_id = (
        payload["channel"]["id"] if payload["channel"]["id"] else payload["channel_id"]
    )
    dm_channel_id = await slack_context.get_direct_message_channel_id(user_id)
    channel_id_for_say = dm_channel_id if is_private else channel_id
    await say(channel=channel_id_for_say, text="...")

    response = slack_context.client.conversations_replies(
        channel=channel_id, ts=payload["message_ts"]
    )
    if response["ok"]:
        messages = response["messages"]
        original_message = messages[0]["text"]
        workspace_name = slack_context.get_workspace_name()
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
        user = await slack_context.get_user_context(user_id)
        summarizer = Summarizer(slack_context)
        summary, run_id = summarizer.summarize_slack_messages(
            messages, channel_id, feature_name="summarize_thread", user=user
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
    slack_context: SlackContext, ack, payload, say, user_id: str
):
    await ack()
    client = slack_context.client
    channel_name = payload["channel_name"]
    channel_id = payload["channel_id"]

    dm_channel_id = await slack_context.get_direct_message_channel_id(user_id)
    await say(channel=dm_channel_id, text="...")

    history = await slack_context.get_channel_history(channel_id)
    history.reverse()
    user = await slack_context.get_user_context(user_id)
    title = f"*Summary of #{channel_name}* (last {len(history)} messages)\n"
    custom_prompt = payload.get("text", None)
    summarizer = Summarizer(slack_context, custom_prompt=custom_prompt)
    summary, run_id = summarizer.summarize_slack_messages(
        history,
        channel_id,
        feature_name="summarize_channel_messages",
        user=user,
    )
    text, blocks = get_text_and_blocks_for_say(
        title=title, run_id=run_id, messages=summary, custom_prompt=custom_prompt
    )
    return await say(channel=dm_channel_id, text=text, blocks=blocks)


@catch_errors_dm_user
async def handler_topics_slash_command(
    slack_context: SlackContext, ack, payload, say, user_id: str
):
    await ack()
    client = slack_context.client
    channel_id = payload["channel_id"]
    dm_channel_id = await slack_context.get_direct_message_channel_id(user_id)
    await say(channel=dm_channel_id, text="...")

    history = await slack_context.get_channel_history(channel_id)
    history.reverse()

    messages = slack_context.get_parsed_messages(history, with_names=False)
    user = await slack_context.get_user_context(user_id)
    is_private, channel_name = slack_context.get_is_private_and_channel_name(channel_id)
    custom_prompt = payload.get("text", None)
    if custom_prompt:
        # todo: add support for custom prompts to /tldr
        await say(
            channel=dm_channel_id,
            text="Sorry, this command doesn't support custom prompts yet so I'm processing your request without it.",
        )

    topic_overview, run_id = await analyze_topics_of_history(
        channel_name, messages, user=user, is_private=is_private
    )
    title = f"*Channel Overview: #{channel_name}*\n\n"
    text, blocks = get_text_and_blocks_for_say(
        title=title, run_id=run_id, messages=[topic_overview]
    )
    return await say(channel=dm_channel_id, text=text, blocks=blocks)


@catch_errors_dm_user
async def handler_tldr_since_slash_command(slack_context: SlackContext, ack, payload, say):
    await ack()
    client = slack_context.client
    title = "Choose your summary timeframe."
    dm_channel_id = await slack_context.get_direct_message_channel_id(payload["user_id"])

    custom_prompt = payload.get("text", None)

    result = client.chat_postEphemeral(
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
                        "action_id": f"summarize_since",
                    },
                ],
            }
        ],
    )

    # get `custom_prompt` into handler_action_summarize_since_date()
    key = f"{result['message_ts']}__{payload['user_id']}"
    _custom_prompt_cache[key] = custom_prompt
    logger.debug(f"Storing `custom_prompt` at {key}: {custom_prompt}")

    await say(
        channel=dm_channel_id,
        text=f'In #{payload["channel_name"]}, choose a date or timeframe to get your summary',
    )
    return


@catch_errors_dm_user
async def handler_action_summarize_since_date(slack_context: SlackContext, ack, body):
    """
    Provide a message summary of the channel since a given date.
    """
    await ack()
    client = slack_context.client
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

    dm_channel_id = await slack_context.get_direct_message_channel_id(user_id)
    client.chat_postMessage(channel=dm_channel_id, text="...")

    async with ClientSession() as session:
        await session.post(body["response_url"], json={"delete_original": "true"})

    history = await slack_context.get_channel_history(channel_id, since=since_datetime)
    history.reverse()
    user = await slack_context.get_user_context(user_id)
    custom_prompt = None
    if "container" in body and "message_ts" in body["container"]:
        key = f"{body['container']['message_ts']}__{user_id}"
        custom_prompt = _custom_prompt_cache.get(key, None)
    summarizer = Summarizer(slack_context, custom_prompt=custom_prompt)
    summary, run_id = summarizer.summarize_slack_messages(
        history, channel_id, feature_name=feature_name, user=user
    )
    text, blocks = get_text_and_blocks_for_say(
        title=f'*Summary of #{channel_name}* since {since_datetime.strftime("%A %b %-d, %Y")} ({len(history)} messages)\n',
        run_id=run_id,
        messages=summary,
        custom_prompt=custom_prompt,
    )
    # todo: somehow add date/preset choice to langsmith metadata
    #   feature_name: str -> feature: str || Tuple[str, List(Tuple[str, str])]
    return client.chat_postMessage(channel=dm_channel_id, text=text, blocks=blocks)


@catch_errors_dm_user
async def handler_sandbox_slash_command(
    slack_context: SlackContext, ack, payload, say, user_id: str
):
    logger.debug(f"Handling /sandbox command")
    await ack()
    
    import json
    import os
    from pathlib import Path

    client = slack_context.client
    channel_id = payload["channel_id"]
    channel_name = payload["channel_name"]
    
    # Create data/history directory if it doesn't exist
    history_dir = Path("data/history")
    history_dir.mkdir(parents=True, exist_ok=True)

    # Write messages to channel-specific jsonl file
    # FIXME: this just appends to the file, it doesn't overwrite it
    history_file = history_dir / f"{channel_name}.jsonl"
    
    # Get latest timestamp and total message count from existing file
    latest_ts = 0
    total_messages = 0
    if history_file.exists():
        with open(history_file, "r") as f:
            for line in f:
                msg = json.loads(line)
                latest_ts = max(latest_ts, float(msg["ts"]))
                total_messages += 1

    # Get oldest message from channel
    history = await slack_context.get_channel_history(channel_id, since_ts=latest_ts)
    history.reverse()
    messages = slack_context.get_rich_parsed_messages(history)
    
    # Only write messages newer than latest_ts
    new_messages = 0
    with open(history_file, "a") as f:
        for message in messages:
            if float(message["ts"]) > latest_ts:
                json.dump(message, f)
                f.write("\n")
                new_messages += 1

    dm_channel_id = await slack_context.get_direct_message_channel_id(user_id)

    # Upload file to Slack
    upload_response = client.files_upload_v2(
        channel=dm_channel_id,
        file=str(history_file),
        title=f"{channel_name} Message History",
        filename=f"{channel_name}_history.jsonl"
    )
    file_url = upload_response["file"]["permalink"]

    text = f"Saved {new_messages} new messages to #{channel_name} history (total: {total_messages + new_messages} messages archived)"
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": text
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"Download the full history <{file_url}|here>"
            }
        }
    ]
    return client.chat_postEphemeral(
        channel=channel_id,
        user=user_id,
        text=text,
        blocks=blocks
    )
    # TODO: this should be its own command e.g. /tldr_history
    # TODO: ideally this becomes a scheduled job that automatically runs periodically