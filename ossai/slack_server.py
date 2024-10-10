import os
import asyncio
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slack_bolt.adapter.socket_mode.aiohttp import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp
from slack_sdk import WebClient

load_dotenv(override=True)

from ossai.handlers import (
    handler_shortcuts,
    handler_tldr_extended_slash_command,
    handler_topics_slash_command,
    handler_feedback,
    handler_tldr_since_slash_command,
    handler_action_summarize_since_date,
    handler_sandbox_slash_command,
)

app = FastAPI()
async_app = AsyncApp(token=os.environ["SLACK_BOT_TOKEN"])
client = WebClient(token=os.environ["SLACK_BOT_TOKEN"])
socket_handler = None


async def create_socket_handler():
    return AsyncSocketModeHandler(async_app, os.environ["SLACK_APP_TOKEN"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    global socket_handler
    socket_handler = await create_socket_handler()
    try:
        await socket_handler.connect_async()
        yield
    finally:
        if socket_handler:
            await socket_handler.disconnect_async()
            if hasattr(socket_handler, "client") and hasattr(
                socket_handler.client, "aiohttp_client_session"
            ):
                await socket_handler.client.aiohttp_client_session.close()

        # Cancel all running tasks
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


app = FastAPI(lifespan=lifespan)


@app.get("/pulse")
def pulse():
    # todo: add some sort of health check for the websockets connection (or check this one when theres a sockets issue)
    return {"status": 200, "message": "ok"}


@app.post("/slack/events")
async def slack_events(request: Request):
    event = await request.json()

    if event.get("type") == "url_verification":
        return {"challenge": event["challenge"]}

    return {"status": 401, "message": "Unauthorized"}


# MARK: - MIDDLEWARE

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # todo: tighten this up in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MARK: - SLASH COMMANDS


@async_app.command("/tldr_extended")
async def handle_tldr_extended_slash_command(ack, payload, say):
    return await handler_tldr_extended_slash_command(
        client, ack, payload, say, user_id=payload["user_id"]
    )


@async_app.command("/tldr")
async def handle_slash_command_topics(ack, payload, say):
    return await handler_topics_slash_command(
        client, ack, payload, say, user_id=payload["user_id"]
    )


@async_app.command("/sandbox")
async def handle_slash_command_sandbox(ack, payload, say):
    return await handler_sandbox_slash_command(
        client, ack, payload, say, user_id=payload["user_id"]
    )


@async_app.command("/tldr_since")
async def handle_slash_command_tldr_since(ack, payload, say):
    return await handler_tldr_since_slash_command(client, ack, payload, say)


# MARK: - ACTIONS


@async_app.action("summarize_since")
@async_app.action("summarize_since_preset")
async def handle_action_summarize_since_date(ack, body, logger):
    await ack()
    await handler_action_summarize_since_date(client, ack, body)
    return logger.info(body)


@async_app.action("not_helpful_button")
@async_app.action("helpful_button")
@async_app.action("very_helpful_button")
async def handle_feedback(ack, body, logger):
    await ack("...")
    handler_feedback(body)
    return logger.info(body)


# MARK: - SHORTCUTS


@async_app.shortcut("thread")
async def handle_thread_shortcut(ack, payload, say):
    await ack()
    await handler_shortcuts(client, False, payload, say, user_id=payload["user"]["id"])


@async_app.shortcut("thread_private")
async def handle_thread_private_shortcut(ack, payload, say):
    await ack()
    await handler_shortcuts(client, True, payload, say, user_id=payload["user"]["id"])


def main():
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
