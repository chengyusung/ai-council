"""資料模型定義"""

from enum import Enum
from pydantic import BaseModel, Field


class Role(str, Enum):
    """訊息角色"""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    MODERATOR = "moderator"  # 主持人
    MEMBER = "member"  # 討論成員


class MessageType(str, Enum):
    """訊息類型"""
    OPENING = "opening"  # 主持人開場
    SPEECH = "speech"  # 成員發言
    ROUND_SUMMARY = "round_summary"  # 發言後小結
    FINAL_SUMMARY = "final_summary"  # 最終總結
    SEARCH_RESULT = "search_result"  # 搜尋結果（最終總結時使用）


class Message(BaseModel):
    """對話訊息"""
    role: Role
    content: str
    speaker_name: str = ""  # 發言者名稱（用於顯示）
    model_id: str = ""  # 模型 ID
    message_type: MessageType = MessageType.SPEECH
    sources: list[str] = Field(default_factory=list)  # 來源連結
    # 六頂思考帽相關
    hat_color: str = ""  # 帽子顏色（white, red, black, yellow, green）
    hat_name: str = ""   # 帽子名稱（白帽, 紅帽, 黑帽, 黃帽, 綠帽）


class MemberConfig(BaseModel):
    """討論成員設定"""
    model_id: str  # e.g., "openai/gpt-4o"
    display_name: str  # e.g., "GPT-4o"
    system_prompt: str = ""  # 人設（選填）
    enabled: bool = True


class ModeratorConfig(BaseModel):
    """主持人設定"""
    model_id: str
    display_name: str
    system_prompt: str = ""


class SessionConfig(BaseModel):
    """會議設定"""
    topic: str  # 討論主題
    total_rounds: int = 3  # 總輪數
    max_tokens: int = 500  # 每次回答的 token 上限
    moderator: ModeratorConfig
    members: list[MemberConfig]


class SessionState(str, Enum):
    """會議狀態"""
    IDLE = "idle"  # 閒置
    RUNNING = "running"  # 進行中
    SUMMARIZING = "summarizing"  # 正在總結
    FINISHED = "finished"  # 結束
