import os
import uuid
from time import gmtime, strptime
import calendar
from typing import Union

from dotenv import load_dotenv
from langchain_core.tracers import LangChainTracer

from ossai.logging_config import logger

load_dotenv(override=True)

class CustomLangChainTracer(LangChainTracer):
    def __init__(self, is_private=False, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.is_private = is_private

    def handleText(self, text, runId):
        if not self.is_private:
            logger.info("passing text")
            super().handleText(text, runId)
        else:
            logger.info("passing no text")
            super().handleText("", runId)

def get_langsmith_config(feature_name: str, user: dict, channel: str, is_private=False):
    run_id = str(uuid.uuid4())
    tracer = CustomLangChainTracer(
        is_private=is_private
    )  # FIXME: this doesn't add privacy like it should

    return {
        "run_id": run_id,
        "metadata": {
            "is_private": is_private,
            **({"user_name": user.get("name")} if "name" in user else {}),
            **({"user_title": user.get("title")} if "title" in user else {}),
            "channel": channel,
        },
        "tags": [feature_name],
        "callbacks": [tracer],
    }

def get_llm_config():
    chat_model = os.getenv("CHAT_MODEL", "gpt-3.5-turbo").strip()
    temperature = float(os.getenv("TEMPERATURE", 0.2))
    openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
    debug = bool(os.environ.get("DEBUG", False))
    max_body_tokens = int(os.getenv("MAX_BODY_TOKENS", 1000))
    language = os.getenv("LANGUAGE", "english")

    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY is not set in .env file")
    return {
        "chat_model": chat_model,
        "temperature": temperature,
        "OPENAI_API_KEY": openai_api_key,
        "debug": debug,
        "max_body_tokens": max_body_tokens,
        "language": language,
    }

def get_text_and_blocks_for_say(
    title: str,
    run_id: Union[uuid.UUID, None],
    messages: list,
    custom_prompt: str = None,
) -> tuple[str, list]:
    CHAR_LIMIT = 3000
    text = "\n".join(messages)

    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": title,
            },
        },
    ]

    # Split text into multiple blocks if it exceeds 3000 characters
    remaining_text = text
    while len(remaining_text) > 0:
        chunk = remaining_text[:CHAR_LIMIT]
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": chunk,
                },
            }
        )
        remaining_text = remaining_text[CHAR_LIMIT:]

    if run_id is not None:
        blocks.append(
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": ":-1: Not Helpful"},
                        "action_id": "not_helpful_button",
                        "value": str(run_id),
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": ":+1: Helpful"},
                        "action_id": "helpful_button",
                        "value": str(run_id),
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": ":tada: Very Helpful"},
                        "action_id": "very_helpful_button",
                        "value": str(run_id),
                    },
                ],
            }
        )

    if custom_prompt:
        blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "plain_text",
                        "text": f"Custom Prompt: {custom_prompt}",
                        "emoji": True,
                    }
                ],
            }
        )

    return text.split("\n")[0], blocks

def get_since_timeframe_presets():
    DAY_OF_SECONDS = 86400
    now = gmtime()
    today = calendar.timegm(
        strptime(f"{now.tm_year}-{now.tm_mon}-{now.tm_mday}", "%Y-%m-%d")
    )
    options = [
        ("Last 7 days", str(today - 7 * DAY_OF_SECONDS)),
        ("Last 14 days", str(today - 14 * DAY_OF_SECONDS)),
        ("Last 30 days", str(today - 30 * DAY_OF_SECONDS)),
        (
            "This week",
            str(today - (now.tm_wday * DAY_OF_SECONDS)),
        ),  # Monday at 00:00:00
        (
            "Last week",
            str(today - (now.tm_wday * DAY_OF_SECONDS) - 7 * DAY_OF_SECONDS),
        ),  # From the start of last week
        (
            "This month",
            str(
                calendar.timegm(strptime(f"{now.tm_year}-{now.tm_mon}-01", "%Y-%m-%d"))
            ),
        ),  # From the start of this month
        (
            "Last month",
            str(
                calendar.timegm(
                    strptime(
                        f"{now.tm_year if now.tm_mon > 1 else now.tm_year - 1}-{now.tm_mon - 1 if now.tm_mon > 1 else 12}-01",
                        "%Y-%m-%d",
                    )
                )
            ),
        ),  # From the start of last month
    ]
    return {
        "type": "static_select",
        "placeholder": {"type": "plain_text", "text": "Select a preset", "emoji": True},
        "action_id": "summarize_since_preset",
        "options": [
            {
                "text": {"type": "plain_text", "text": text, "emoji": True},
                "value": value,
            }
            for (text, value) in options
        ],
    }

def main():
    logger.error("DEBUGGING")

if __name__ == "__main__":
    main()