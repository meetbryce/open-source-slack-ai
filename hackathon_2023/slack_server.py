import os

from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from slack_bolt import App
from slack_bolt.adapter.starlette import SlackRequestHandler
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from starlette.requests import Request as StarletteRequest
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.socket_mode.response import SocketModeResponse
from slack_sdk.socket_mode.aiohttp import SocketModeClient
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.aiohttp import AsyncSocketModeHandler
from slack_bolt.adapter.socket_mode import SocketModeHandler

from hackathon_2023.summarizer import summarize_slack_messages

load_dotenv()
app = App(token=os.environ["SLACK_BOT_TOKEN"])
async_app = AsyncApp(token=os.environ["SLACK_BOT_TOKEN"])
fast_app = FastAPI()
handler = SlackRequestHandler(app)
client = WebClient(token=os.environ["SLACK_BOT_TOKEN"])


@fast_app.get('/pulse')
def pulse():
    return {"status": 200, "message": "ok"}


@app.event("message")
async def handle_direct_message(event, say):
    if event.get("subtype") is None and event.get("channel_type") == "im":
        user_id = event["user"]
        text = event["text"]
        # Handle the direct message event here
        # For example, you can send a response using the `say` method
        await say(f"Received direct message from user {user_id}: {text}")


@fast_app.post("/slack/events")
async def slack_events(request: Request):
    """
    Route for handling Slack events.
    This function passes the incoming HTTP request to the SlackRequestHandler for processing.

    Returns:
        Response: The result of handling the request.
    """
    # Convert FastAPI Request to Starlette Request as Slack Bolt expects it
    starlette_request = StarletteRequest(request.scope, request.receive)
    return await handler.handle(starlette_request)


async def get_channel_history(channel_id: str) -> list:
    try:
        response = client.conversations_history(channel=channel_id, limit=1000)  # 1000 is the max limit
        # todo: remove TLDR bot messages
        return response["messages"]
    except SlackApiError as e:
        print(f"Error fetching history: {e.response['error']}")
        return []


socket_handler = AsyncSocketModeHandler(async_app, os.environ["SLACK_APP_TOKEN"])


@fast_app.on_event("startup")
async def startup():
    # this is not ideal for # of workers > 1.
    await socket_handler.connect_async()


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

    history = await get_channel_history(channel_id)
    history.reverse()
    summary = summarize_slack_messages(history)
    summary.insert(0, f'*Summary of #{channel_name}* (last {len(history)} messages)\n')

    return await say('\n'.join(summary))


if __name__ == "__main__":
    import uvicorn

    socket_mode_handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    socket_mode_handler.start()

    uvicorn.run(fast_app, host="0.0.0.0", port=8000)
