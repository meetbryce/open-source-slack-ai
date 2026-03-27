"""
Integration tests that make real API calls. Requires OPENAI_API_KEY to be set.
Run with: pytest -m integration
"""
from unittest.mock import MagicMock

import pytest

from ossai.summarizer import Summarizer


@pytest.fixture
def slack_context():
    mock = MagicMock()
    mock.get_is_private_and_channel_name.return_value = (False, "engineering")
    mock.workspace_name = "test-workspace"
    # Return messages formatted as "username: text", mirroring SlackContext.get_parsed_messages
    mock.get_parsed_messages.side_effect = lambda messages, **kwargs: [
        f"{m['username']}: {m['text']}" for m in messages
    ]
    return mock


@pytest.mark.integration
def test_summarize_slack_messages_includes_topic(slack_context):
    """Verify the summarizer correctly identifies the topic of a conversation.

    The conversation is unambiguously about migrating from MongoDB to PostgreSQL.
    We assert that the summary mentions the migration and both database names so
    we can catch any SDK version that breaks the actual OpenAI API integration.
    """
    messages = [
        {"text": "hey team — I think we need to talk seriously about moving off MongoDB", "username": "alice"},
        {"text": "agreed, we've been hitting document size limits and the lack of joins is killing us", "username": "bob"},
        {"text": "I've been prototyping a PostgreSQL schema for the events table and it's looking really clean", "username": "alice"},
        {"text": "nice! what's the plan for the migration? do we dual-write during the transition?", "username": "charlie"},
        {"text": "yeah dual-write is the safest path. write to both MongoDB and PostgreSQL, then read from Postgres once we've validated the data", "username": "alice"},
        {"text": "how long do we think the backfill will take? we have ~200M documents", "username": "bob"},
        {"text": "rough estimate is 3-4 days for the backfill job. we'll run it on a weekend to avoid load", "username": "alice"},
        {"text": "sounds good. let's get a migration RFC written up so we can align the team before we start", "username": "charlie"},
        {"text": "on it — I'll have a draft RFC in the shared doc by Thursday", "username": "alice"},
    ]

    summarizer = Summarizer(slack_context)
    result, run_id = summarizer.summarize_slack_messages(
        messages,
        channel_id="C123",
        feature_name="integration_test",
        user="U123",
    )

    assert isinstance(result, list)
    assert len(result) > 0
    full_summary = " ".join(result).lower()
    assert "mongodb" in full_summary or "mongo" in full_summary
    assert "postgresql" in full_summary or "postgres" in full_summary
    assert "migrat" in full_summary  # matches "migration", "migrating", "migrate"

    import re
    assert re.match(
        r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
        str(run_id),
    )
