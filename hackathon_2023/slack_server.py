import os

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_bolt.adapter.socket_mode.aiohttp import AsyncSocketModeHandler
from slack_bolt.adapter.starlette import SlackRequestHandler
from slack_bolt.async_app import AsyncApp
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from starlette.requests import Request as StarletteRequest

from hackathon_2023.summarizer import summarize_slack_messages
from hackathon_2023.utils import get_channel_history

load_dotenv()
app = App(token=os.environ["SLACK_BOT_TOKEN"])
async_app = AsyncApp(token=os.environ["SLACK_BOT_TOKEN"])
fast_app = FastAPI()
handler = SlackRequestHandler(app)
client = WebClient(token=os.environ["SLACK_BOT_TOKEN"])
socket_handler = AsyncSocketModeHandler(async_app, os.environ["SLACK_APP_TOKEN"])


@fast_app.get('/pulse')
def pulse():
    return {"status": 200, "message": "ok"}


@app.event("message")
async def handle_direct_message(event, say):
    if event.get("subtype") is None and event.get("channel_type") == "im":
        user_id = event["user"]
        text = event["text"]
        await say(f"Received direct message from user {user_id}: {text}")


@fast_app.post("/slack/events")
async def slack_events(request: Request):
    """
    Route for handling Slack events.
    This function passes the incoming HTTP request to the SlackRequestHandler for processing.

    Returns:
        Response: The result of handling the request.
    """
    starlette_request = StarletteRequest(request.scope, request.receive)
    return await handler.handle(starlette_request)


@fast_app.on_event("startup")
async def startup():
    await socket_handler.connect_async()  # todo: this is not ideal for # of workers > 1.


@fast_app.on_event("shutdown")
async def shutdown_event():
    await socket_handler.disconnect_async()


@async_app.command('/tldr')
async def handle_slash_command(ack, payload, say):
    await ack()
    await say('...')  # this is a hack to get the bot to not show an error message but work fine
    text = payload.get("text", None)
    channel_name = payload["channel_name"]
    channel_id = payload["channel_id"]

    if text:
        await say("ERROR: Sorry, text argument(s) aren't supported yet.")
        return

    if not channel_id:
        await say("ERROR: No channel_id provided.")
        return

    history = await get_channel_history(client, channel_id)
    history.reverse()
    summary = summarize_slack_messages(client, history)
    summary.insert(0, f'*Summary of #{channel_name}* (last {len(history)} messages)\n')

    return await say('\n'.join(summary))


@async_app.shortcut("thread")
async def handle_thread_shortcut(ack, payload, say):
    await ack()
    channel_id = payload['channel']['id']
    # fixme: summarize the thread (let people know if it's not a thread and summarize the message instead)
    return await say(channel=channel_id, text='Summarized it for you (but not really, lol)')


if __name__ == "__main__":
    import uvicorn

    socket_mode_handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    socket_mode_handler.start()

    uvicorn.run(fast_app, host="0.0.0.0", port=8000)
