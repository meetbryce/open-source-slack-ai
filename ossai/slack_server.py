import os

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from slack_bolt.adapter.socket_mode.aiohttp import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp
from slack_sdk import WebClient

from ossai.handlers import (
    handler_shortcuts,
    handler_tldr_slash_command,
    handler_topics_slash_command,
)

load_dotenv()
app = FastAPI()
async_app = AsyncApp(token=os.environ["SLACK_BOT_TOKEN"])
client = WebClient(token=os.environ["SLACK_BOT_TOKEN"])
socket_handler = AsyncSocketModeHandler(async_app, os.environ["SLACK_APP_TOKEN"])


@app.get("/pulse")
def pulse():
    # todo: add some sort of health check for the websockets connection (or check this one when theres a sockets issue)
    return {"status": 200, "message": "ok"}


@app.post("/slack/events")
async def slack_events(request: Request):
    event = await request.json()

    if event.get('type') == 'url_verification':
        return {'challenge': event['challenge']}
    
    return {"status": 401, "message": "Unauthorized"}


@app.on_event("startup")
async def startup():
    await socket_handler.connect_async()  # todo: this is not ideal for # of workers > 1.


@app.on_event("shutdown")
async def shutdown_event():
    await socket_handler.disconnect_async()


@async_app.command("/tldr_extended")
async def handle_tldr_slash_command(ack, payload, say):
    return await handler_tldr_slash_command(client, ack, payload, say, user_id=payload['user_id'])


@async_app.command("/tldr")
async def temp__handle_slash_command_topics(ack, payload, say):
    return await handler_topics_slash_command(client, ack, payload, say, user_id=payload['user_id'])


@async_app.shortcut("thread")
async def handle_thread_shortcut(ack, payload, say):
    await ack()
    await handler_shortcuts(client, False, payload, say, user_id=payload['user']['id'])


@async_app.shortcut("thread_private")
async def handle_thread_private_shortcut(ack, payload, say):
    await ack()
    await handler_shortcuts(client, True, payload, say, user_id=payload['user']['id'])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
