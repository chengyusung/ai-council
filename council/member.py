"""討論成員模組"""

from typing import AsyncIterator

from models import MemberConfig
from services.openrouter import OpenRouterClient
from council.prompts import (
    MEMBER_DEFAULT_SYSTEM_PROMPT,
    get_member_speak_prompt,
    get_hat_aware_member_system_prompt,
    get_member_speak_prompt_with_hat,
)
from council.hats import HatColor
import config


class Member:
    """討論成員"""

    def __init__(
        self,
        member_config: MemberConfig,
        openrouter_client: OpenRouterClient,
    ):
        self.config = member_config
        self.client = openrouter_client

    @property
    def model_id(self) -> str:
        return self.config.model_id

    @property
    def display_name(self) -> str:
        return self.config.display_name

    @property
    def system_prompt(self) -> str:
        return self.config.system_prompt or MEMBER_DEFAULT_SYSTEM_PROMPT

    async def speak(
        self,
        topic: str,
        hat_info: dict[str, str] | None = None,
        previous_speaker_name: str = "",
        previous_speaker_content: str = "",
        previous_question: str = "",
        latest_summary: str = "",
        is_first_speaker: bool = False,
        max_tokens: int = config.DEFAULT_MAX_TOKENS,
        max_retries: int = 2,
        # 舊參數保留向後相容
        context: str = "",
    ) -> AsyncIterator[str]:
        """
        成員發言（streaming）

        Args:
            topic: 討論主題
            hat_info: 帽子資訊（如有）
            previous_speaker_name: 上一位發言者名稱
            previous_speaker_content: 上一位發言者內容
            previous_question: 上一位的蘇格拉底問題
            latest_summary: 最新的討論摘要
            is_first_speaker: 是否為第一位發言者
            max_tokens: 最大 token 數
            max_retries: 最大重試次數
            context: 舊版上下文（向後相容）

        Yields:
            發言內容的 streaming chunks
        """
        if hat_info:
            # 使用帽子版本的 Prompt
            hat_color = HatColor(hat_info.get('color', 'white'))
            system_prompt = get_hat_aware_member_system_prompt(hat_color)
            user_prompt = get_member_speak_prompt_with_hat(
                topic=topic,
                speaker_name=self.display_name,
                hat_info=hat_info,
                previous_speaker_name=previous_speaker_name,
                previous_speaker_content=previous_speaker_content,
                previous_question=previous_question,
                latest_summary=latest_summary,
                is_first_speaker=is_first_speaker,
            )
        else:
            # 舊版 Prompt（向後相容）
            system_prompt = self.system_prompt
            user_prompt = get_member_speak_prompt(
                topic=topic,
                speaker_name=self.display_name,
                history=context,
                custom_prompt=self.config.system_prompt,
            )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        stream = await self.client.chat(
            model=self.model_id,
            messages=messages,
            max_tokens=max_tokens,
            stream=True,
            max_retries=max_retries,
        )
        async for chunk in stream:
            yield chunk
