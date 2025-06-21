import uuid

from langchain_core.tracers import LangChainTracer

from ossai.logging_config import logger


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