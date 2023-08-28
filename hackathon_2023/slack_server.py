import os

from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from slack_bolt import App
from slack_bolt.adapter.starlette import SlackRequestHandler
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from starlette.requests import Request as StarletteRequest

from hackathon_2023.summarizer import summarize_slack_messages

load_dotenv()
app = App(token=os.environ["SLACK_BOT_TOKEN"])
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
        return response["messages"]
    except SlackApiError as e:
        print(f"Error fetching history: {e.response['error']}")
        return []


@fast_app.post("/slack/tldr")
async def handle_slash_command(request: Request):
    form_data = await request.form()
    text = form_data.get("text", None)  # any text passed with the slash command
    channel_name = form_data.get("channel_name")
    channel_id = form_data.get("channel_id")

    if text:
        return "Sorry, text argument(s) are not support yet."

    if not channel_id:
        raise HTTPException(status_code=400, detail="No channel_id provided")

    history = await get_channel_history(channel_id)
    summary = summarize_slack_messages(history)
    summary.insert(0, f'*Summary of #{channel_name}* (last {len(history)} messages)\n')

    return {
        "response_type": "in_channel",  # This makes the response visible to all in the channel
        "text": '\n'.join(summary)
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(fast_app, host="0.0.0.0", port=8000)
