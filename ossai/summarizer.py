import os
from uuid import UUID
import re
import openai

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from ossai.logging_config import logger
from ossai.utils import (
    get_parsed_messages,
    get_langsmith_config,
    get_llm_config,
    get_is_private_and_channel_name,
)

load_dotenv(override=True)


class Summarizer:
    def __init__(self, custom_prompt: str | None = None):
        # todo: apply pydantic model
        self.config = get_llm_config()
        self.model = ChatOpenAI(
            model=self.config["chat_model"], temperature=self.config["temperature"]
        )
        self.parser = StrOutputParser()
        self.custom_prompt = custom_prompt

    def summarize(
        self,
        text: str,
        feature_name: str,
        user: str,
        channel: str,
        is_private: bool = False,
    ) -> tuple[str, UUID]:
        """
        Summarize a chat log in bullet points, in the specified language.

        Args:
            text (str): The chat log to summarize, in the format "Speaker: Message" separated by line breaks.
            feature_name (str): The name of the feature being used.
            user (str): The user requesting the summary.
            channel (str): The channel where the summary is requested.
            is_private (bool, optional): Whether the chat log is private. Defaults to False.

        Returns:
            tuple[str, UUID]: The summarized chat log in bullet point format and the run ID.

        Examples:
            # >>> summarizer = Summarizer()
            # >>> summarizer.summarize("Alice: Hi\nBob: Hello\nAlice: How are you?\nBob: I'm doing well, thanks.", "test", "user1", "general")
            '- Alice greeted Bob.\n- Bob responded with a greeting.\n- Alice asked how Bob was doing.
            \n- Bob replied that he was doing well.', UUID('...')
        """
        system_msg = """\
        You're a highly capable summarization expert who provides succinct summaries of Slack chat logs.
        The chat log format consists of one line per message in the format "Speaker: Message".
        The chat log lists the most recent messages first. Place more emphasis on recent messages.
        The `\\n` within the message represents a line break.
        Consider your summary as a whole and avoid repeating yourself unnecessarily.
        The user understands {language} only.
        So, The assistant needs to speak in {language}.
        """

        base_human_msg = """\
        Please summarize the following chat log to a flat markdown formatted bullet list.
        Do not write a line by line summary. Instead, summarize the overall conversation.
        Do not include greeting/salutation/polite expressions in summary.
        Make the summary easy to read while maintaining a conversational tone and retaining meaning.
        Write in conversational English.
        {custom_instructions}

        {text}
        """

        # todo: guard against prompt injection

        prompt_template = ChatPromptTemplate.from_messages(
            [("system", system_msg), ("user", base_human_msg)]
        )

        chain = prompt_template | self.model | self.parser

        # Attach the context to the chain invocation
        langsmith_config = get_langsmith_config(
            feature_name=feature_name,
            user=user,
            channel=channel,
            is_private=is_private,
        )
        logger.info(f"{langsmith_config=}")
        result = chain.invoke(
            {
                "text": text,
                "language": self.config["language"],
                "custom_instructions": (
                    f"\n\nAdditionally, please follow these specific instructions for this summary:\n{self.custom_prompt}"
                    if self.custom_prompt
                    else ""
                ),
            },
            config=langsmith_config,
        )
        return result, langsmith_config["run_id"]

    @staticmethod
    def estimate_openai_chat_token_count(text: str) -> int:
        """
        Estimate the number of OpenAI API tokens that would be consumed by sending the given text to the chat API.

        Args:
            text (str): The text to be sent to the OpenAI chat API.

        Returns:
            int: The estimated number of tokens that would be consumed by sending the given text to the OpenAI chat API.

        Examples:
            >>> Summarizer.estimate_openai_chat_token_count("Hello, how are you?")
            7
        """
        # todo: replace with `tiktoken`
        # Split the text into words and count the number of characters of each type
        pattern = re.compile(
            r"""(
                \d+       | # digits
                [a-z]+    | # alphabets
                \s+       | # whitespace
                .           # other characters
                )""",
            re.VERBOSE | re.IGNORECASE,
        )
        matches = re.findall(pattern, text)

        # based on https://help.openai.com/en/articles/4936856-what-are-tokens-and-how-to-count-them
        def counter(tok):
            if tok == " " or tok == "\n":
                return 0
            elif tok.isdigit() or tok.isalpha():
                return (len(tok) + 3) // 4
            else:
                return 1

        return sum(map(counter, matches))

    def split_messages_by_token_count(
        self, client, messages: list[dict]
    ) -> list[list[str]]:
        """
        Split a list of strings into sub lists with a maximum token count.

        Args:
            client: The Slack client.
            messages (list[dict]): A list of Slack messages to be split.

        Returns:
            list[list[str]]: A list of sub lists, where each sublist has a token count less than or equal to max_body_tokens
        """
        parsed_messages = get_parsed_messages(client, messages)

        body_token_counts = [
            self.estimate_openai_chat_token_count(msg) for msg in parsed_messages
        ]
        result = []
        current_sublist = []
        current_count = 0

        for message, count in zip(parsed_messages, body_token_counts):
            if current_count + count <= self.config["max_body_tokens"]:
                current_sublist.append(message)
                current_count += count
            else:
                result.append(current_sublist)
                current_sublist = [message]
                current_count = count

        result.append(current_sublist)
        return result

    def summarize_slack_messages(
        self,
        client,
        messages: list,
        channel_id: str,
        feature_name: str,
        user: str,
    ) -> tuple[list, UUID]:
        """
        Summarize a list of slack messages.

        This method takes a list of slack messages, a context message, and the channel ID, splits the
        messages into sublists based on token count, and then summarizes each sublist.
        The summary is returned as a list, with the context message as the first element.

        Args:
            client: The slack client.
            messages (list): A list of slack messages to be summarized.
            channel_id (str): The ID of the Slack channel.
            feature_name (str): The name of the feature being used.
            user (str): The user requesting the summary.

        Returns:
            tuple[list, UUID]: A list of summary text and the run ID.
        """
        # Determine if the channel is private
        is_private, channel_name = get_is_private_and_channel_name(client, channel_id)

        message_splits = self.split_messages_by_token_count(client, messages)
        logger.info(f"{len(message_splits)=}")
        result_text = []

        for message_split in message_splits:
            try:
                text, run_id = self.summarize(
                    "\n".join(message_split),
                    feature_name=feature_name,
                    user=user,
                    channel=channel_name,
                    is_private=is_private,
                )
            except openai.RateLimitError as e:
                logger.error(e)
                return [f"Sorry, OpenAI rate limit exceeded..."], None
            except openai.AuthenticationError as e:
                logger.error(e)
                return ["Sorry, unable to authenticate with OpenAI"], None
            result_text.append(text)

        return result_text, run_id


def main():
    logger.error("DEBUGGING")


if __name__ == "__main__":
    main()
