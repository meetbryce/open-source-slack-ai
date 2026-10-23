import os

from dotenv import load_dotenv

load_dotenv(override=True)


def _supports_temperature(model: str) -> bool:
    """Reasoning-era OpenAI models (gpt-5+, o-series) reject any temperature
    other than the default. The gpt-*-chat variants still accept one."""
    if "chat" in model:
        return True
    return not (model.startswith(("gpt-5", "gpt-6", "o1", "o3", "o4")))


def get_llm_config():
    chat_model = os.getenv("CHAT_MODEL", "gpt-6-luna").strip()
    temperature = (
        float(os.getenv("TEMPERATURE", 0.2))
        if _supports_temperature(chat_model)
        else None
    )
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