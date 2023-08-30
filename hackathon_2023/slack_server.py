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

from hackathon_2023.handlers import handler_shortcuts, handler_tldr_slash_command, handler_topics_slash_command

load_dotenv()
app = App(token=os.environ["SLACK_BOT_TOKEN"])
async_app = AsyncApp(token=os.environ["SLACK_BOT_TOKEN"])
fast_app = FastAPI()
handler = SlackRequestHandler(app)
client = WebClient(token=os.environ["SLACK_BOT_TOKEN"])
socket_handler = AsyncSocketModeHandler(async_app, os.environ["SLACK_APP_TOKEN"])


@fast_app.get('/pulse')
def pulse():
    # todo: add some sort of health check for the websockets connection (or check this one when theres a sockets issue)
    return {"status": 200, "message": "ok"}


@fast_app.post("/slack/events")
async def slack_events(request: Request):
    starlette_request = StarletteRequest(request.scope, request.receive)
    return await handler.handle(starlette_request)


@fast_app.on_event("startup")
async def startup():
    await socket_handler.connect_async()  # todo: this is not ideal for # of workers > 1.


@fast_app.on_event("shutdown")
async def shutdown_event():
    await socket_handler.disconnect_async()


@async_app.command('/tldr')
async def handle_tldr_slash_command(ack, payload, say):
    return await handler_tldr_slash_command(client, ack, payload, say)


@async_app.command('/tldr_topics')
async def temp__handle_slash_command_topics(ack, payload, say):
    return await handler_topics_slash_command(client, ack, payload, say)


@async_app.shortcut("thread")
async def handle_thread_shortcut(ack, payload, say):
    await ack()
    await handler_shortcuts(client, False, payload, say)


@async_app.shortcut("thread_private")
async def handle_thread_private_shortcut(ack, payload, say):
    await ack()
    await handler_shortcuts(client, True, payload, say)


@app.event("message")
async def handle_message_events(body, logger):
    print(f'message {body=}')
    logger.info(body)


if __name__ == "__main__":
    import uvicorn

    socket_mode_handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    socket_mode_handler.start()

    uvicorn.run(fast_app, host="0.0.0.0", port=8000)
