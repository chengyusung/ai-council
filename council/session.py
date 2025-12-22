"""會議管理模組"""

import random
import re
from typing import AsyncIterator
from dataclasses import dataclass, field

from models import (
    SessionConfig,
    SessionState,
    Message,
    Role,
    MessageType,
)
from services.openrouter import OpenRouterClient
from services.search import SearchService
from council.member import Member
from council.moderator import Moderator
from council.hats import HatManager, HatColor
import config


@dataclass
class SessionEvent:
    """會議事件，用於 UI 更新"""
    event_type: str  # "moderator", "member", "system", "search"
    speaker_name: str = ""
    content: str = ""
    is_streaming: bool = False
    is_final: bool = False
    speech_index: int = 0
    search_query: str = ""
    search_sources: list[str] = field(default_factory=list)
    # 六頂思考帽相關
    hat_emoji: str = ""
    hat_name: str = ""


class Session:
    """討論會議管理"""

    def __init__(
        self,
        session_config: SessionConfig,
        openrouter_client: OpenRouterClient | None = None,
        search_service: SearchService | None = None,
    ):
        self.config = session_config
        self.client = openrouter_client or OpenRouterClient()
        self.search = search_service or SearchService()

        # 建立主持人
        self.moderator = Moderator(
            moderator_config=session_config.moderator,
            openrouter_client=self.client,
            search_service=self.search,
        )

        # 建立成員
        self.members: dict[str, Member] = {}
        for member_config in session_config.members:
            if member_config.enabled:
                member = Member(
                    member_config=member_config,
                    openrouter_client=self.client,
                )
                self.members[member.display_name] = member

        # 狀態
        self.state = SessionState.IDLE
        self.history: list[Message] = []
        self._stop_requested = False
        self._summary_requested = False
        self._speech_count = 0
        self._latest_summary = ""  # 最新的小結內容

        # 六頂思考帽
        self._hat_manager = HatManager()
        self._current_round = 1
        self._current_hat_info: dict | None = None  # 當前發言者的帽子資訊

    @property
    def topic(self) -> str:
        return self.config.topic

    @property
    def total_rounds(self) -> int:
        return self.config.total_rounds

    @property
    def max_tokens(self) -> int:
        return self.config.max_tokens

    @property
    def member_names(self) -> list[str]:
        return list(self.members.keys())

    def request_stop(self):
        """請求停止討論"""
        self._stop_requested = True

    def request_summary(self):
        """請求立即總結"""
        self._summary_requested = True

    async def run(self) -> AsyncIterator[SessionEvent]:
        """
        執行討論會議

        Yields:
            SessionEvent 用於 UI 更新
        """
        self.state = SessionState.RUNNING
        self._stop_requested = False
        self._summary_requested = False
        self._speech_count = 0
        self._latest_summary = ""
        self._hat_manager.reset()
        self._current_round = 1
        self._current_hat_info = None

        try:
            # 1. 主持人開場
            yield SessionEvent(
                event_type="system",
                content="討論開始",
            )

            async for event in self._moderator_opening():
                yield event
                if self._stop_requested:
                    return

            # 2. 建立發言順序（每輪隨機）
            total_speeches = len(self.member_names) * self.total_rounds
            speeches_per_round = len(self.member_names)
            speaking_order = []
            for round_num in range(self.total_rounds):
                round_order = list(self.member_names)
                random.shuffle(round_order)
                speaking_order.extend(round_order)

            # 3. 依序發言
            for i, member_name in enumerate(speaking_order):
                if self._stop_requested or self._summary_requested:
                    break

                # 更新當前輪數
                self._current_round = (i // speeches_per_round) + 1

                # 成員發言
                self._speech_count += 1
                speech_succeeded = False
                async for event in self._member_speak(member_name):
                    yield event
                    # 檢查是否成功完成發言
                    if event.is_final and event.event_type == "member":
                        speech_succeeded = True

                if self._stop_requested or self._summary_requested:
                    break

                # 發言後小結（最後一次發言不做小結，直接進最終總結）
                # 且只有在發言成功時才做小結
                if speech_succeeded and i < total_speeches - 1:
                    async for event in self._after_speech_summary():
                        yield event

            # 4. 最終總結
            async for event in self._final_summary():
                yield event

            self.state = SessionState.FINISHED

        except Exception as e:
            yield SessionEvent(
                event_type="system",
                content=f"發生錯誤: {str(e)}",
            )
            self.state = SessionState.IDLE

    async def _moderator_opening(self) -> AsyncIterator[SessionEvent]:
        """主持人開場"""
        content_parts = []
        mod_name = self.moderator.display_name

        yield SessionEvent(
            event_type="moderator",
            speaker_name=mod_name,
            content="",
            is_streaming=True,
        )

        async for chunk in self.moderator.opening(
            topic=self.topic,
            member_names=self.member_names,
            max_tokens=self.max_tokens,
        ):
            content_parts.append(chunk)
            yield SessionEvent(
                event_type="moderator",
                speaker_name=mod_name,
                content=chunk,
                is_streaming=True,
            )

        full_content = "".join(content_parts)
        self._add_message(
            role=Role.MODERATOR,
            content=full_content,
            speaker_name=mod_name,
            message_type=MessageType.OPENING,
        )

        yield SessionEvent(
            event_type="moderator",
            speaker_name=mod_name,
            content=full_content,
            is_streaming=False,
            is_final=True,
        )

    def _get_previous_speaker_info(self) -> tuple[str, str, str]:
        """
        取得上一位發言者的資訊

        Returns:
            tuple: (speaker_name, content, question)
        """
        last_speech = None
        for msg in reversed(self.history):
            if msg.message_type == MessageType.SPEECH:
                last_speech = msg
                break

        if not last_speech:
            return "", "", ""

        # 提取蘇格拉底問題
        question = self._extract_question(last_speech.content)

        return last_speech.speaker_name, last_speech.content, question

    def _extract_question(self, content: str) -> str:
        """從發言內容中提取蘇格拉底問題（最後一個問句）"""
        # 找到所有問號結尾的句子
        # 支持中文和英文問號
        sentences = re.split(r'(?<=[?？])', content)
        questions = [s.strip() for s in sentences if s.strip() and (s.strip().endswith('?') or s.strip().endswith('？'))]

        if questions:
            # 取最後一個問題，並清理前面的換行
            last_q = questions[-1]
            # 只取問題本身（可能有多行，取最後一行）
            lines = last_q.strip().split('\n')
            return lines[-1].strip()

        return ""

    async def _member_speak(self, member_name: str) -> AsyncIterator[SessionEvent]:
        """單一成員發言（帶帽子，失敗時跳過）"""
        member = self.members[member_name]

        # 分配帽子
        is_first = self._speech_count == 1
        assigned_hat = self._hat_manager.assign_hat(is_first_speaker=is_first)
        hat_info = self._hat_manager.get_hat_info(assigned_hat)
        self._current_hat_info = hat_info

        # 取得上一位發言者資訊
        prev_name, prev_content, prev_question = self._get_previous_speaker_info()

        yield SessionEvent(
            event_type="system",
            content=f"{member_name} {hat_info['emoji']} 開始發言（第 {self._speech_count} 次發言，{hat_info['name']}）",
            speech_index=self._speech_count,
            hat_emoji=hat_info['emoji'],
            hat_name=hat_info['name'],
        )

        content_parts = []

        yield SessionEvent(
            event_type="member",
            speaker_name=member_name,
            content="",
            is_streaming=True,
            speech_index=self._speech_count,
            hat_emoji=hat_info['emoji'],
            hat_name=hat_info['name'],
        )

        try:
            async for chunk in member.speak(
                topic=self.topic,
                hat_info=hat_info,
                previous_speaker_name=prev_name,
                previous_speaker_content=prev_content,
                previous_question=prev_question,
                latest_summary=self._latest_summary,
                is_first_speaker=is_first,
                max_tokens=self.max_tokens,
            ):
                content_parts.append(chunk)
                yield SessionEvent(
                    event_type="member",
                    speaker_name=member_name,
                    content=chunk,
                    is_streaming=True,
                    speech_index=self._speech_count,
                    hat_emoji=hat_info['emoji'],
                    hat_name=hat_info['name'],
                )
        except Exception as e:
            # API 失敗（重試後仍失敗），跳過此成員
            yield SessionEvent(
                event_type="system",
                content=f"⚠️ {member_name} 發言失敗，已跳過：{str(e)}",
                speech_index=self._speech_count,
            )
            self._current_hat_info = None
            return  # 不加入 history，直接返回

        full_content = "".join(content_parts)
        self._add_message(
            role=Role.MEMBER,
            content=full_content,
            speaker_name=member_name,
            model_id=member.model_id,
            message_type=MessageType.SPEECH,
            hat_color=hat_info['color'],
            hat_name=hat_info['name'],
        )

        yield SessionEvent(
            event_type="member",
            speaker_name=member_name,
            content=full_content,
            is_streaming=False,
            is_final=True,
            speech_index=self._speech_count,
            hat_emoji=hat_info['emoji'],
            hat_name=hat_info['name'],
        )

    async def _after_speech_summary(self) -> AsyncIterator[SessionEvent]:
        """發言後小結（挑釁型）"""
        # 取得剛才的發言
        last_speech = next(
            (m for m in reversed(self.history) if m.message_type == MessageType.SPEECH),
            None
        )

        if not last_speech:
            return

        content_parts = []
        mod_name = self.moderator.display_name

        # 取得帽子資訊和分佈
        speaker_hat = self._current_hat_info or {"emoji": "", "name": "", "color": ""}
        hat_distribution = self._hat_manager.get_distribution_summary()

        yield SessionEvent(
            event_type="moderator",
            speaker_name=mod_name,
            content="",
            is_streaming=True,
        )

        async for chunk in self.moderator.after_speech_summary(
            topic=self.topic,
            speaker_name=last_speech.speaker_name,
            speaker_content=last_speech.content,
            speaker_hat=speaker_hat,
            previous_summary=self._latest_summary,
            current_round=self._current_round,
            total_rounds=self.total_rounds,
            hat_distribution=hat_distribution,
        ):
            content_parts.append(chunk)
            yield SessionEvent(
                event_type="moderator",
                speaker_name=mod_name,
                content=chunk,
                is_streaming=True,
            )

        full_content = "".join(content_parts)

        # 更新最新小結
        self._latest_summary = full_content

        self._add_message(
            role=Role.MODERATOR,
            content=full_content,
            speaker_name=mod_name,
            message_type=MessageType.ROUND_SUMMARY,
        )

        yield SessionEvent(
            event_type="moderator",
            speaker_name=mod_name,
            content=full_content,
            is_streaming=False,
            is_final=True,
        )

    async def _final_summary(self) -> AsyncIterator[SessionEvent]:
        """最終總結"""
        self.state = SessionState.SUMMARIZING
        mod_name = self.moderator.display_name
        summary_name = f"{mod_name}（總結）"

        yield SessionEvent(
            event_type="system",
            content="進行最終總結",
        )

        content_parts = []

        yield SessionEvent(
            event_type="moderator",
            speaker_name=summary_name,
            content="",
            is_streaming=True,
        )

        async for chunk in self.moderator.final_summary(
            topic=self.topic,
            full_history=self.history,
            max_tokens=1000,
        ):
            content_parts.append(chunk)
            yield SessionEvent(
                event_type="moderator",
                speaker_name=summary_name,
                content=chunk,
                is_streaming=True,
            )

        full_content = "".join(content_parts)
        self._add_message(
            role=Role.MODERATOR,
            content=full_content,
            speaker_name=mod_name,
            message_type=MessageType.FINAL_SUMMARY,
        )

        yield SessionEvent(
            event_type="moderator",
            speaker_name=summary_name,
            content=full_content,
            is_streaming=False,
            is_final=True,
        )

    def _add_message(
        self,
        role: Role,
        content: str,
        speaker_name: str,
        message_type: MessageType,
        model_id: str = "",
        sources: list[str] | None = None,
        hat_color: str = "",
        hat_name: str = "",
    ) -> Message:
        """新增訊息到歷史"""
        msg = Message(
            role=role,
            content=content,
            speaker_name=speaker_name,
            model_id=model_id,
            message_type=message_type,
            sources=sources or [],
            hat_color=hat_color,
            hat_name=hat_name,
        )
        self.history.append(msg)
        return msg
