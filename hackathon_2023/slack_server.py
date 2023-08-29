import os

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_bolt.adapter.socket_mode.aiohttp import AsyncSocketModeHandler
from slack_bolt.adapter.starlette import SlackRequestHandler
from slack_bolt.async_app import AsyncApp
from slack_sdk import WebClient
from starlette.requests import Request as StarletteRequest

from hackathon_2023.handlers import handler_shortcuts, handler_slash_commands
from hackathon_2023.topic_analysis import analyze_topics_of_history
from hackathon_2023.utils import get_channel_history, get_direct_message_channel_id, parse_messages

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
    return await handler_slash_commands(client, ack, payload, say)


# TODO: move to handlers.py -- likely as part of handler_slash_commands()
async def handler_topics(client, ack, payload, say):
    # START boilerplate
    await ack()
    dm_channel_id = await get_direct_message_channel_id(client)
    await say(channel=dm_channel_id, text='...')

    history = await get_channel_history(client, payload["channel_id"])
    history.reverse()
    # END boilerplate

    messages = parse_messages(client, history, with_names=False)
    topic_overview = await analyze_topics_of_history(payload['channel_name'], messages)
    return await say(channel=dm_channel_id, text=topic_overview)


@async_app.command('/tldr_topics')
async def temp__handle_slash_command_topics(ack, payload, say):
    return await handler_topics(client, ack, payload, say)


@async_app.shortcut("thread")
async def handle_thread_shortcut(ack, payload, say):
    await ack()
    await handler_shortcuts(client, False, payload, say)


@async_app.shortcut("thread_private")
async def handle_thread_private_shortcut(ack, payload, say):
    await ack()
    await handler_shortcuts(client, True, payload, say)


if __name__ == "__main__":
    import uvicorn

    socket_mode_handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    socket_mode_handler.start()

    uvicorn.run(fast_app, host="0.0.0.0", port=8000)
