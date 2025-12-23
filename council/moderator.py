"""主持人模組"""

import json
from typing import AsyncIterator, Callable

from models import ModeratorConfig, Message, MessageType
from services.openrouter import OpenRouterClient, SEARCH_TOOL
from services.search import SearchService
from council.prompts import (
    MODERATOR_SYSTEM_PROMPT,
    get_moderator_opening_prompt,
    get_select_speaker_prompt,
    get_round_summary_prompt,
    get_final_summary_prompt,
    get_after_speech_summary_prompt,
    get_provocative_summary_prompt,
)
import config


class Moderator:
    """討論主持人"""

    def __init__(
        self,
        moderator_config: ModeratorConfig,
        openrouter_client: OpenRouterClient,
        search_service: SearchService,
    ):
        self.config = moderator_config
        self.client = openrouter_client
        self.search = search_service

    @property
    def model_id(self) -> str:
        return self.config.model_id

    @property
    def display_name(self) -> str:
        return self.config.display_name

    @property
    def system_prompt(self) -> str:
        base = MODERATOR_SYSTEM_PROMPT
        if self.config.system_prompt:
            base = f"{self.config.system_prompt}\n\n{base}"
        return base

    async def opening(
        self,
        topic: str,
        member_names: list[str],
        max_tokens: int = config.DEFAULT_MAX_TOKENS,
        max_retries: int = 5,
    ) -> AsyncIterator[str]:
        """主持人開場（無搜尋）"""
        messages = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": get_moderator_opening_prompt(topic, member_names),
            },
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

    async def select_next_speaker(
        self,
        topic: str,
        history: list[Message],
        remaining_members: list[str],
        current_round: int,
        total_rounds: int,
    ) -> str:
        """
        選擇下一位發言者

        Returns:
            選中的成員名稱
        """
        history_summary = self._summarize_history(history)

        messages = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": get_select_speaker_prompt(
                    topic=topic,
                    history_summary=history_summary,
                    remaining_members=remaining_members,
                    current_round=current_round,
                    total_rounds=total_rounds,
                ),
            },
        ]

        response = await self.client.chat(
            model=self.model_id,
            messages=messages,
            max_tokens=50,  # 只需要名字
            temperature=0.3,  # 低溫度，更確定性
            stream=False,
        )

        selected = response.get("content", "").strip()

        # 驗證選擇是否有效
        for member in remaining_members:
            if member.lower() in selected.lower() or selected.lower() in member.lower():
                return member

        # 如果無法匹配，返回第一個
        return remaining_members[0] if remaining_members else ""

    async def round_summary(
        self,
        topic: str,
        round_num: int,
        round_history: list[Message],
        max_tokens: int = config.DEFAULT_MAX_TOKENS,
    ) -> AsyncIterator[str]:
        """輪次小結"""
        history_str = self._format_round_history(round_history)

        messages = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": get_round_summary_prompt(topic, round_num, history_str),
            },
        ]

        stream = await self.client.chat(
            model=self.model_id,
            messages=messages,
            max_tokens=max_tokens,
            stream=True,
        )
        async for chunk in stream:
            yield chunk

    async def after_speech_summary(
        self,
        topic: str,
        speaker_name: str,
        speaker_content: str,
        speaker_hat: dict[str, str] | None = None,
        previous_summary: str = "",
        current_round: int = 1,
        total_rounds: int = 3,
        hat_distribution: str = "",
        max_tokens: int = config.DEFAULT_MAX_TOKENS,
        max_retries: int = 5,
    ) -> AsyncIterator[str]:
        """
        成員發言後的小結（挑釁型）

        Args:
            topic: 討論主題
            speaker_name: 剛發言的成員名稱
            speaker_content: 該成員的發言內容
            speaker_hat: 該成員的帽子資訊
            previous_summary: 之前的小結（如有）
            current_round: 當前輪數
            total_rounds: 總輪數
            hat_distribution: 帽子分佈統計
            max_retries: 最大重試次數
        """
        # 使用挑釁型或一般型 Prompt
        if speaker_hat:
            user_prompt = get_provocative_summary_prompt(
                topic=topic,
                speaker_name=speaker_name,
                speaker_hat=speaker_hat,
                speaker_content=speaker_content,
                previous_summary=previous_summary,
                current_round=current_round,
                total_rounds=total_rounds,
                hat_distribution=hat_distribution,
            )
        else:
            # 向後相容：無帽子時使用原版 Prompt
            user_prompt = get_after_speech_summary_prompt(
                topic=topic,
                speaker_name=speaker_name,
                speaker_content=speaker_content,
                previous_summary=previous_summary,
            )

        messages = [
            {"role": "system", "content": self.system_prompt},
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

    async def final_summary(
        self,
        topic: str,
        full_history: list[Message],
        max_tokens: int = config.DEFAULT_SUMMARY_MAX_TOKENS,  # 總結需要更多 tokens
        on_search: Callable[[str, dict], None] | None = None,
        max_retries: int = 5,
    ) -> AsyncIterator[str]:
        """最終總結"""
        history_str = self._format_full_history(full_history)

        messages = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": get_final_summary_prompt(topic, history_str),
            },
        ]

        async for chunk in self._chat_with_optional_search(
            messages, max_tokens, on_search, max_retries
        ):
            yield chunk

    async def _chat_with_optional_search(
        self,
        messages: list[dict],
        max_tokens: int,
        on_search: Callable[[str, dict], None] | None,
        max_retries: int = 5,
    ) -> AsyncIterator[str]:
        """帶有可選搜尋功能的聊天"""
        # 先嘗試帶工具的請求
        response = await self.client.chat_with_tools(
            model=self.model_id,
            messages=messages,
            tools=[SEARCH_TOOL],
            max_tokens=max_tokens,
            max_retries=max_retries,
        )

        if response.get("tool_calls"):
            # 處理搜尋
            search_results = []
            for tc in response["tool_calls"]:
                if tc["name"] == "web_search":
                    args = json.loads(tc["arguments"])
                    query = args.get("query", "")
                    result = self.search.search(query)
                    if on_search:
                        on_search(query, result)
                    search_results.append((tc, self.search.format_results_for_ai(result)))

            # 加入搜尋結果重新生成
            messages.append({
                "role": "assistant",
                "content": response.get("content") or "",
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": tc["arguments"],
                        },
                    }
                    for tc in response["tool_calls"]
                ],
            })

            for tc, result in search_results:
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result,
                })

            stream = await self.client.chat(
                model=self.model_id,
                messages=messages,
                max_tokens=max_tokens,
                stream=True,
                max_retries=max_retries,
            )
            async for chunk in stream:
                yield chunk
        else:
            if response.get("content"):
                yield response["content"]

    def _summarize_history(self, history: list[Message]) -> str:
        """簡要摘要歷史（用於選擇發言者）"""
        if not history:
            return "討論剛開始"

        recent = history[-5:]  # 只看最近 5 條
        lines = []
        for msg in recent:
            if msg.speaker_name:
                content_preview = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
                lines.append(f"- {msg.speaker_name}: {content_preview}")

        return "\n".join(lines) if lines else "討論剛開始"

    def _format_round_history(self, history: list[Message]) -> str:
        """格式化單輪歷史"""
        lines = []
        for msg in history:
            if msg.message_type == MessageType.SPEECH:
                lines.append(f"**{msg.speaker_name}**：\n{msg.content}\n")
        return "\n".join(lines)

    def _format_full_history(self, history: list[Message]) -> str:
        """格式化完整歷史"""
        lines = []
        for msg in history:
            if msg.message_type == MessageType.OPENING:
                lines.append(f"**主持人開場**：\n{msg.content}\n")
            elif msg.message_type == MessageType.SPEECH:
                lines.append(f"**{msg.speaker_name}**：\n{msg.content}\n")
            elif msg.message_type == MessageType.ROUND_SUMMARY:
                lines.append(f"**小結**：\n{msg.content}\n")
        return "\n".join(lines)
