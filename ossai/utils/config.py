import os

from dotenv import load_dotenv

load_dotenv(override=True)


def get_llm_config():
    chat_model = os.getenv("CHAT_MODEL", "gpt-4.1").strip()
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