import calendar
import uuid
from time import gmtime, strptime
from typing import Union


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