import os
import re
from time import mktime
from datetime import date
from typing import List

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from ossai.logging_config import logger

class SlackContext:
    def __init__(self, client: WebClient):
        self.client = client
        self._id_name_cache = {}
        self._bot_id = None
        self._workspace_name = None

    async def get_bot_id(self) -> str:
         # todo: refactor this to be an attribute getter i.e. slack_context.bot_id
        if self._bot_id is None:
            try:
                response = self.client.auth_test()
                self._bot_id = response["bot_id"]
            except SlackApiError as e:
                logger.error(f"Error fetching bot ID: {e.response['error']}")
                self._bot_id = "None"
        return self._bot_id

    async def get_channel_history(
        self,
        channel_id: str,
        since: date = None,
        since_ts: str = None,
        include_threads: bool = False,
    ) -> list:
        oldest_timestamp = since_ts if since_ts else (mktime(since.timetuple()) if since else 0)
        response = self.client.conversations_history(
            channel=channel_id, limit=1000, oldest=oldest_timestamp
        )
        bot_id = await self.get_bot_id()
        return [msg for msg in response["messages"] if msg.get("bot_id") != bot_id]

    async def get_direct_message_channel_id(self, user_id: str) -> str:
        try:
            response = self.client.conversations_open(users=user_id)
            return response["channel"]["id"]
        except SlackApiError as e:
            logger.error(f"Error fetching bot DM channel ID: {e.response['error']}")
            raise e

    def get_is_private_and_channel_name(self, channel_id: str) -> tuple[bool, str]:
        try:
            channel_info = self.client.conversations_info(channel=channel_id)
            channel_name = channel_info["channel"]["name"]
            is_private = channel_info["channel"]["is_private"]
        except Exception as e:
            logger.error(
                f"Error getting channel info for is_private, defaulting to private: {e}"
            )
            channel_name = "unknown"
            is_private = True
        return is_private, channel_name

    def get_name_from_id(self, user_or_bot_id: str, is_bot=False) -> tuple[str, bool]:
        """
        Returns a tuple of (name, is_internal)
        """
        if user_or_bot_id in self._id_name_cache:
            return self._id_name_cache[user_or_bot_id]

        try:
            user_response = self.client.users_info(user=user_or_bot_id)
            if user_response.get("ok"):
                name = user_response["user"].get(
                    "real_name", user_response["user"]["profile"]["real_name"]
                )
                is_internal = not user_response["user"].get("is_restricted", True)  # if is_restricted is not present, infers is_restricted=True
                self._id_name_cache[user_or_bot_id] = (name, is_internal)
                return name, is_internal
            else:
                logger.error("user fetch failed")
                raise SlackApiError("user fetch failed", user_response)
        except SlackApiError as e:
            if e.response["error"] == "user_not_found":
                try:
                    bot_response = self.client.bots_info(bot=user_or_bot_id)
                    if bot_response.get("ok"):
                        name = bot_response["bot"]["name"]
                        is_internal = True  # Bots are considered internal
                        self._id_name_cache[user_or_bot_id] = (name, is_internal)
                        return name, is_internal
                    else:
                        logger.error("bot fetch failed")
                        raise SlackApiError("bot fetch failed", bot_response)
                except SlackApiError as e2:
                    logger.error(
                        f"Error fetching name for bot {user_or_bot_id=}: {e2.response['error']}"
                    )
            logger.error(f"Error fetching name for {user_or_bot_id=} {is_bot=} {e=}")

        return "Someone", True  # Default to internal for unknown users

    def get_parsed_messages(self, messages, with_names=True, with_internal_external=False):
        
        def parse_message(msg):
            user_id = msg.get("user")
            if user_id is None:
                bot_id = msg.get("bot_id")
                name, is_internal = self.get_name_from_id(bot_id, is_bot=True)
            else:
                name, is_internal = self.get_name_from_id(user_id)

            parsed_message = re.sub(
                r"<@[UB]\w+>",
                lambda m: self.get_name_from_id(m.group(0)[2:-1])[0],
                msg["text"],
            )

            if not with_names:
                return re.sub(r"<@[UB]\w+>", lambda m: "", msg["text"])

            prefix = name
            if with_internal_external:
                status = "[internal]" if is_internal else "[external]"
                prefix = f"{name} {status}"

            return f"{prefix}: {parsed_message}"

        return [parse_message(message) for message in messages]
    
    def get_rich_parsed_messages(self, messages) -> List[dict]:
        def parse_message(msg):
            user_id = msg.get("user")
            if user_id is None:
                bot_id = msg.get("bot_id")
                name, is_internal = self.get_name_from_id(bot_id, is_bot=True)
            else:
                name, is_internal = self.get_name_from_id(user_id)

            rich_msg = msg.copy()
            rich_msg["author"] = name
            rich_msg["is_internal"] = is_internal
            rich_msg["timestamp"] = msg["ts"].split(".")[0]
            rich_msg["text"] = re.sub(
                r"<@[UB]\w+>",
                lambda m: self.get_name_from_id(m.group(0)[2:-1])[0],
                msg["text"],
            )  # replace mentions with names
            return rich_msg
        
        return [parse_message(message) for message in messages]


    async def get_user_context(self, user_id: str) -> dict:
        try:
            user_info = self.client.users_info(user=user_id)
            logger.debug(user_info)
            if user_info["ok"]:
                name = user_info["user"]["name"]
                title = user_info["user"]["profile"]["title"]
                return {"name": name, "title": title}
        except SlackApiError as e:
            logger.error(f"Failed to fetch username: {e}")
            return {}

    def get_workspace_name(self):
        # todo: refactor this to be an attribute getter i.e. slack_context.workspace_name
        if self._workspace_name is None:
            try:
                response = self.client.team_info()
                if response["ok"]:
                    self._workspace_name = response["team"]["name"]
                else:
                    logger.warning(
                        f"Error retrieving workspace name: {response['error']}. Falling back to WORKSPACE_NAME_FALLBACK."
                    )
                    self._workspace_name = os.getenv("WORKSPACE_NAME_FALLBACK", "")
            except SlackApiError as e:
                logger.error(f"Error retrieving workspace name: {e.response['error']}")
                self._workspace_name = os.getenv("WORKSPACE_NAME_FALLBACK", "")
        return self._workspace_name

