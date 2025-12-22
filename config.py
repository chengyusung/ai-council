"""設定管理模組"""

import os
from dotenv import load_dotenv

# 載入 .env 檔案
load_dotenv()


# API Keys
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

# OpenRouter 設定
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# 預設可選模型清單
AVAILABLE_MODELS = [
    {"id": "openai/gpt-5.2", "name": "GPT-5.2"},
    {"id": "anthropic/claude-sonnet-4.5", "name": "Claude Sonnet 4.5"},
    {"id": "google/gemini-3-pro-preview", "name": "Gemini 3 Pro"},
    {"id": "google/gemini-3-flash-preview", "name": "Gemini 3 Flash"},
    {"id": "x-ai/grok-4.1-fast", "name": "Grok 4.1 Fast"},
    {"id": "deepseek/deepseek-v3.2", "name": "DeepSeek V3.2"},
    {"id": "moonshotai/kimi-k2-thinking", "name": "Kimi K2 Thinking"},
    {"id": "allenai/olmo-3.1-32b-think:free", "name": "Olmo 3.1 32b Think"},
    {"id": "xiaomi/mimo-v2-flash:free", "name": "Mimo V2 Flash"},
    {"id": "mistralai/devstral-2512:free", "name": "Devstral 2512"},
    {"id": "openai/gpt-oss-120b:free", "name": "GPT-OSS 120b"},
    {"id": "z-ai/glm-4.5-air:free", "name": "GLM 4.5 Air"},
    {"id": "moonshotai/kimi-k2:free", "name": "Kimi K2"},
    {"id": "deepseek/deepseek-r1-0528:free", "name": "DeepSeek R1 0528"},
    {"id": "qwen/qwen3-coder:free", "name": "Qwen 3 Coder"},
]

# 預設設定
DEFAULT_MAX_TOKENS = 500
DEFAULT_ROUNDS = 3
DEFAULT_TEMPERATURE = 0.7

# 隨機名字列表（用於匿名化模型名稱）
RANDOM_NAMES = [
    "Alice", "Bob", "Carol", "David", "Eve",
    "Frank", "Grace", "Henry", "Iris", "Jack",
    "Kate", "Leo", "Mia", "Noah", "Olivia",
]

# 主持人名字
MODERATOR_NAME = "Max"


def get_model_name(model_id: str) -> str:
    """根據模型 ID 取得顯示名稱"""
    for model in AVAILABLE_MODELS:
        if model["id"] == model_id:
            return model["name"]
    return model_id


def validate_config() -> list[str]:
    """驗證設定，回傳錯誤訊息列表"""
    errors = []
    if not OPENROUTER_API_KEY:
        errors.append("請設定 OPENROUTER_API_KEY")
    if not TAVILY_API_KEY:
        errors.append("請設定 TAVILY_API_KEY（網路搜尋功能需要）")
    return errors
